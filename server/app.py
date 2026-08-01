#!/usr/bin/env python3
"""
Servidor de Atualizacoes — YouTube Downloader
=============================================
API para o sistema de atualizacao do aplicativo.

Endpoints publicos:
    GET  /                        -> status e versao mais recente
    GET  /api/latest              -> manifest completo da versao mais recente
    GET  /api/releases            -> lista de todas as versoes
    GET  /api/update/check        -> checa se ha atualizacao (usado pelo app)

Endpoints administrativos (exigem header `Authorization: Bearer <ADMIN_TOKEN>`):
    POST /api/releases            -> registra uma nova versao

Deploy na Render (plano free):
    Start Command:
        uvicorn server.app:app --host 0.0.0.0 --port $PORT
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.models import ArquivoPlataforma, CheckAtualizacao, RegistroRelease
from server.release_manager import ReleaseManager, comparar_versoes

if os.environ.get("RELEASES_FILE"):
    manager = ReleaseManager(Path(os.environ["RELEASES_FILE"]))
else:
    manager = ReleaseManager()

app = FastAPI(
    title="YouTube Downloader — Servidor de Atualizacoes",
    description="API de manifest de versoes para o sistema de auto-atualizacao.",
    version="1.0.0",
)

# Libera CORS para qualquer origem (nao faz mal para o desktop app).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_NAME = "YouTube Downloader"

TOKEN_ENV = "ADMIN_TOKEN"


def _token_valido(authorization: Optional[str]) -> bool:
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        return False
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    return authorization.split(" ", 1)[1].strip() == token


def _exigir_admin(authorization: Optional[str] = Header(None)):
    if not os.environ.get(TOKEN_ENV):
        raise HTTPException(
            status_code=503,
            detail=f"Variavel de ambiente {TOKEN_ENV} nao configurada no servidor.",
        )
    if not _token_valido(authorization):
        raise HTTPException(status_code=401, detail="Token de administrador invalido.")


# ─── Endpoints publicos ─────────────────────────────────────────────────────

@app.get("/")
def raiz():
    latest = manager.mais_recente()
    return {
        "app": APP_NAME,
        "status": "ok",
        "latest_version": latest["version"] if latest else None,
    }


@app.get("/api/latest")
def latest():
    latest = manager.mais_recente()
    if not latest:
        raise HTTPException(status_code=404, detail="Nenhuma versao publicada ainda.")
    return latest


@app.get("/api/releases")
def listar_releases():
    return {"app": APP_NAME, "total": len(manager.listar()), "releases": manager.listar()}


@app.get("/api/update/check", response_model=CheckAtualizacao)
def check(current_version: str, platform: str = "windows"):
    """Endpoint chamado pelo app para verificar se ha atualizacao."""
    latest = manager.mais_recente()

    # Nenhuma versao publicada -> sem atualizacao
    if not latest:
        return CheckAtualizacao(
            update_available=False,
            app=APP_NAME,
            current_version=current_version,
        )

    # Versao atual >= mais recente -> sem atualizacao
    if comparar_versoes(current_version, latest["version"]) >= 0:
        return CheckAtualizacao(
            update_available=False,
            app=APP_NAME,
            current_version=current_version,
            latest_version=latest["version"],
        )

    plat = latest.get("platforms", {}).get(platform)
    return CheckAtualizacao(
        update_available=True,
        app=APP_NAME,
        current_version=current_version,
        latest_version=latest["version"],
        mandatory=bool(latest.get("mandatory")),
        min_required_version=latest.get("min_required_version"),
        published_at=latest.get("published_at"),
        notes=latest.get("notes"),
        release_page=latest.get("release_page"),
        platform=ArquivoPlataforma(**plat) if plat else None,
    )


# ─── Endpoints administrativos ──────────────────────────────────────────────

@app.post("/api/releases", status_code=201, dependencies=[Depends(_exigir_admin)])
def registrar_release(payload: RegistroRelease):
    """Registra ou substitui uma versao no manifest."""
    release = manager.registrar(payload.model_dump())
    return {"ok": True, "version": release["version"], "total": len(manager.listar())}
