#!/usr/bin/env python3
"""
Ferramenta para publicar uma nova versao no servidor de atualizacoes (Render).

Uso (CLI):
    python publish_release.py --version 1.1.0 \
        --notes "Correcoes de bugs" \
        --windows-url https://github.com/user/repo/releases/download/v1.1.0/Setup.exe \
        --windows-sha256 <hash-do-arquivo> \
        --server https://SEU-SERVIDOR.onrender.com \
        --token SEU-ADMIN-TOKEN

Uso (API, reutilizado pelo pipeline release.py):
    from publish_release import publicar
    publicar(version="1.1.0", windows_url="...", windows_sha256="...",
             release_page="...", server="...", token="...")

Opcoes:
    --version          Versao a publicar (obrigatorio)
    --server           URL do servidor (padrao: UPDATE_URL em updater.py)
    --token            Token de administrador (variavel PUBLISH_TOKEN ou --token)
    --notes            Notas da versao
    --min-required     Versao minima exigida (padrao 1.0)
    --published-at     Data de publicacao ISO (padrao: agora)
    --release-page     URL da pagina da release (ex.: GitHub Releases)
    --mandatory        Marca a versao como obrigatoria
    --windows-url / --windows-sha256 / --windows-filename
    --macos-url / --linux-url   (opcionais)
    --no-commit        Nao faz commit/push do manifest local (server/releases.json)

Apos publicar, o manifest tambem e gravado em server/releases.json no repositorio
local e, se o diretorio for um repositorio git, um commit+push e feito para que
a Render (plano free, disco efemero) restaure o manifest no proximo deploy.
Use --no-commit para pular apenas o git (o arquivo local ainda e atualizado).

Se `--windows-sha256` nao for informado mas `--windows-url` apontar para um
arquivo local, o hash sera calculado automaticamente.
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional

# Permite importar updater.py da raiz
sys.path.insert(0, str(Path(__file__).parent))
from updater import UPDATE_URL  # noqa: E402

PROJECT_DIR = Path(__file__).parent
# Manifest de versoes versionado no repositorio. No plano free da Render o disco
# e efemero (dados somem a cada deploy/restart), entao este arquivo commitado e a
# fonte duravel: a Render redeploya sozinha no push e restaura o manifest.
MANIFEST_LOCAL = PROJECT_DIR / "server" / "releases.json"


def sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def atualizar_manifest_local(payload: Dict, manifest: Path = MANIFEST_LOCAL) -> bool:
    """Grava a release no server/releases.json do repositorio local.

    Usa o mesmo ReleaseManager do servidor para manter a ordenacao e o
    dedupe por versao. Assim o arquivo commitado fica sincronizado com o
    servidor e sobrevive aos redeploys da Render (plano free).
    """
    try:
        from server.release_manager import ReleaseManager
    except Exception:
        print("Aviso: nao foi possivel importar ReleaseManager; manifest local nao atualizado.")
        return False
    try:
        manager = ReleaseManager(manifest)
        manager.registrar(payload)
        return True
    except Exception as e:
        print(f"Aviso: falha ao atualizar manifest local ({manifest}): {e}")
        return False


def commit_push_manifest(versao: str, manifest: Path = MANIFEST_LOCAL) -> bool:
    """Faz git add/commit/push do manifest (se o repositorio for git).

    A Render (render.yaml com autoDeploy: true) redeploya sozinha apos o
    push, restaurando o manifest no servidor. Retorna True em caso de sucesso.

    Se nao houver nada para commitar (ex.: republish identico da mesma
    versao), considera sucesso sem commit.
    """
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       check=True, capture_output=True, cwd=str(PROJECT_DIR))
    except Exception:
        print("Aviso: nao ha repositorio git aqui; commit/push nao executado.")
        return False
    try:
        subprocess.run(["git", "add", "--", str(manifest)], check=True,
                       capture_output=True, cwd=str(PROJECT_DIR))
    except Exception as e:
        print(f"Aviso: falha no git add do manifest: {e}")
        return False

    # 0 = nada staged; 1 = ha mudancas a commitar; >1 = erro do git
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"],
                          capture_output=True, cwd=str(PROJECT_DIR))
    if diff.returncode == 0:
        return True  # Nada mudou (ex.: republish identico) — sucesso
    if diff.returncode != 1:
        print(f"Aviso: falha ao verificar mudancas (git diff retornou {diff.returncode}).")
        return False

    try:
        subprocess.run(
            ["git", "commit", "-m", f"release: v{versao} (manifest de atualizacoes)"],
            check=True, capture_output=True, cwd=str(PROJECT_DIR))
    except Exception as e:
        print(f"Aviso: falha no git commit do manifest: {e}")
        print("  Faca manualmente:")
        print(f"    git add server/releases.json")
        print(f"    git commit -m 'release: v{versao} (manifest)'")
        return False

    try:
        subprocess.run(["git", "push"], check=True, capture_output=True,
                       cwd=str(PROJECT_DIR))
    except Exception as e:
        print(f"Aviso: commit feito, mas o git push falhou: {e}")
        print("  O manifest ja esta commitado; faca o push manualmente:")
        print("    git push")
        return False
    return True


def publicar(
    version: str,
    server: str = UPDATE_URL,
    token: str = "",
    notes: str = "",
    min_required: str = "1.0",
    published_at: str = "",
    release_page: str = "",
    mandatory: bool = False,
    windows_url: str = "",
    windows_sha256: str = "",
    windows_filename: str = "",
    windows_signature: str = "",
    macos_url: str = "",
    linux_url: str = "",
    private_key: str = "",
    commit: bool = True,
) -> Dict:
    """Publica uma versao no servidor de atualizacoes.

    Se `private_key` (caminho do update_private.pem) for informado e houver
    sha256, a assinatura Ed25519 e calculada automaticamente.

    Apos publicar, o manifest tambem e gravado em server/releases.json no
    repositorio local e, se `commit` for True (padrao) e o diretorio for um
    repositorio git, um commit+push e feito para que a Render (plano free,
    disco efemero) restaure o manifest no proximo deploy automatico.

    Retorna o dict de resposta do servidor. Levanta RuntimeError em caso de
    falha (rede ou HTTP). Usada pela CLI e pelo pipeline release.py.
    """
    if not token:
        raise RuntimeError(
            "Informe --token ou defina a variavel PUBLISH_TOKEN."
        )

    # ─── Monta payload ─────────────────────────────────────────────────────
    platforms: Dict[str, dict] = {}

    def _assinar(chave, sha256):
        """Calcula a assinatura Ed25519 do digest, se possivel."""
        if not sha256 or not private_key:
            return ""
        if not os.path.isfile(private_key):
            print(f"Aviso: chave privada nao encontrada em {private_key}; release sem assinatura.")
            return ""
        try:
            from signing import assinar_sha256
            sig = assinar_sha256(sha256, caminho_privada=Path(private_key))
            print(f"  Assinatura Ed25519 ({chave}): {sig[:24]}...")
            return sig
        except Exception as e:
            print(f"Aviso: falha ao assinar ({chave}): {e}")
            return ""

    def _plataforma(chave, url, sha256, filename, signature=""):
        if not url:
            return
        if not sha256 and url.startswith(("http://", "https://")):
            print(f"Aviso: sem sha256 para {chave}; o app nao podera validar o arquivo.")
        elif not sha256 and os.path.isfile(url):
            sha256 = sha256_arquivo(url)
            print(f"  SHA-256 ({chave}): {sha256}")
        if not signature and sha256:
            signature = _assinar(chave, sha256)
        size = 0
        if not url.startswith(("http://", "https://")) and os.path.isfile(url):
            size = os.path.getsize(url)
        platforms[chave] = {
            "url": url,
            "sha256": sha256,
            "size": size,
            "filename": filename or os.path.basename(url.split("?")[0]),
            "signature": signature,
        }

    _plataforma("windows", windows_url, windows_sha256, windows_filename, windows_signature)
    _plataforma("macos", macos_url, "", "")
    _plataforma("linux", linux_url, "", "")

    if not platforms:
        raise RuntimeError(
            "Informe ao menos --windows-url (ou --macos-url/--linux-url)."
        )

    payload = {
        "version": version,
        "min_required_version": min_required,
        "published_at": published_at
        or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": notes,
        "release_page": release_page,
        "mandatory": mandatory,
        "platforms": platforms,
    }

    # ─── Envia ao servidor ─────────────────────────────────────────────────
    url = f"{server.rstrip('/')}/api/releases"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            corpo = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro HTTP {e.code}: {detalhe}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Falha de rede: {e}") from e

    print(f"OK! Versao {corpo.get('version')} publicada. Total: {corpo.get('total')}")

    # ─── Persistencia (plano free da Render: disco efemero) ────────────────
    if atualizar_manifest_local(payload):
        if commit:
            if commit_push_manifest(version):
                print("Manifest persistido em server/releases.json (git ok).")
            else:
                print("Manifest atualizado localmente; revise os avisos de git acima.")
        else:
            print(
                "Manifest atualizado em server/releases.json (nao commitado; "
                "commite e faca push para persistir na Render)."
            )

    return corpo


def main():
    parser = argparse.ArgumentParser(description="Publica uma versao no servidor de atualizacoes.")
    parser.add_argument("--version", required=True, help="Versao a publicar (ex.: 1.1.0)")
    parser.add_argument("--server", default=UPDATE_URL, help="URL base do servidor")
    parser.add_argument("--token", default=os.environ.get("PUBLISH_TOKEN", ""), help="Token admin")
    parser.add_argument("--notes", default="", help="Notas da versao")
    parser.add_argument("--min-required", default="1.0", help="Versao minima exigida")
    parser.add_argument("--published-at", default="", help="Data ISO (padrao: agora)")
    parser.add_argument("--release-page", default="", help="URL da pagina da release")
    parser.add_argument("--mandatory", action="store_true", help="Versao obrigatoria")

    parser.add_argument("--windows-url", default="")
    parser.add_argument("--windows-sha256", default="")
    parser.add_argument("--windows-filename", default="")
    parser.add_argument("--windows-signature", default="", help="Assinatura Ed25519 (base64) ja calculada")
    parser.add_argument("--macos-url", default="")
    parser.add_argument("--linux-url", default="")
    parser.add_argument("--private-key", default=os.environ.get("UPDATE_PRIVATE_KEY", "update_private.pem"),
                        help="Caminho da chave privada para assinar (padrao: update_private.pem)")
    parser.add_argument("--no-commit", action="store_true",
                        help="Nao faz commit/push do manifest local (server/releases.json)")
    args = parser.parse_args()

    try:
        publicar(
            version=args.version,
            server=args.server,
            token=args.token,
            notes=args.notes,
            min_required=args.min_required,
            published_at=args.published_at,
            release_page=args.release_page,
            mandatory=args.mandatory,
            windows_url=args.windows_url,
            windows_sha256=args.windows_sha256,
            windows_filename=args.windows_filename,
            windows_signature=args.windows_signature,
            macos_url=args.macos_url,
            linux_url=args.linux_url,
            private_key=args.private_key,
            commit=not args.no_commit,
        )
    except RuntimeError as e:
        print(f"Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
