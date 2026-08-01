#!/usr/bin/env python3
"""
Pipeline de Release Completa — YouTube Downloader
==================================================
Executa o fluxo inteiro de publicacao de uma nova versao com UM comando:

    1. Build PyInstaller (GUI + CLI) via build_exe.py
    2. Instalador Inno Setup (ISCC) com a versao da release
    3. Cria GitHub Release e envia o instalador como asset
    4. Publica a versao no servidor de atualizacoes (Render)

Uso:
    python release.py --version 1.1.0 --notes "Correcoes de bugs" \
        --repo usuario/repo --server https://SEU-APP.onrender.com

Tokens:
    --github-token   Token do GitHub (ou variavel GH_TOKEN / GITHUB_TOKEN)
    --token          Token admin do servidor (ou variavel PUBLISH_TOKEN)

Flags de controle (para rodar apenas parte do fluxo):
    --skip-build       Pula o PyInstaller (usa dist/ existente)
    --skip-installer   Pula o Inno Setup (usa installer/ existente)
    --skip-github      Pula GitHub Release (usa --windows-url fornecido)
    --skip-publish     Pula a publicacao no servidor
    --dry-run          Mostra o que faria sem executar nada

Requisitos: Python + PyInstaller + Inno Setup (ISCC.exe) + tokens.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

# Para testes com --dry-run sem precisar de rede/build
DRY_RUN = False

PROJECT_DIR = Path(__file__).parent
DIST_DIR = PROJECT_DIR / "dist"
INSTALLER_DIR = PROJECT_DIR / "installer"
ISS_SCRIPT = PROJECT_DIR / "installer.iss"
BUILD_SCRIPT = PROJECT_DIR / "build_exe.py"

GITHUB_API = "https://api.github.com"
GITHUB_UPLOADS = "https://uploads.github.com"

# Caminhos comuns do ISCC.exe (Inno Setup)
ISCC_CAMINHOS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    os.path.expandvars(r"%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"),
]


# ─── Utilitarios ────────────────────────────────────────────────────────────

def log(mensagem: str):
    print(mensagem)


def erro(mensagem: str) -> int:
    print(f"[ERRO] {mensagem}")
    return 1


def rodar(cmd: List[str], cwd: Path = PROJECT_DIR) -> int:
    """Executa um comando e retorna o codigo de saida (dry-run: 0)."""
    if DRY_RUN:
        log(f"  (dry-run) {subprocess.list2cmdline(cmd)}")
        return 0
    resultado = subprocess.run(cmd, cwd=cwd)
    return resultado.returncode


def sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def validar_versao(versao: str) -> bool:
    """Versao simples sem 'v': ex.: 1.0, 1.2.3, 1.2.3-beta.

    Aceita major.minor[.patch][-sufixo]. Rejeita '1.2.3.4', '1.2.x', 'v1.0'.
    """
    return bool(re.fullmatch(r"\d+\.\d+(\.\d+)?(?:-[a-zA-Z]\w*)?", versao or ""))


def encontrar_iscc() -> Optional[str]:
    """Localiza o ISCC.exe (Inno Setup) no sistema."""
    # 1. Variavel de ambiente ISCC
    env = os.environ.get("ISCC", "")
    if env and os.path.isfile(env):
        return env
    # 2. Caminhos comuns
    for caminho in ISCC_CAMINHOS:
        if os.path.isfile(caminho):
            return caminho
    # 3. PATH
    return shutil.which("ISCC.exe") or shutil.which("iscc")


def repo_do_git() -> str:
    """Tenta descobrir 'usuario/repo' a partir do git remote origin."""
    try:
        saida = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
        url = saida.stdout.strip()
        if not url:
            return ""
        # Formatos: git@github.com:user/repo.git, https://github.com/user/repo.git
        m = re.search(r"(?:github\.com[:/])([\w.-]+/[\w.-]+?)(?:\.git)?/?$", url)
        return m.group(1) if m else ""
    except Exception:
        return ""


def http_json(url: str, method: str = "GET", token: str = "", data=None,
              headers: Optional[Dict[str, str]] = None) -> Dict:
    """Faz requisicao HTTP e retorna o JSON (ou dict vazio)."""
    cabecalhos = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "YouTube-Downloader-Release",
    }
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    if headers:
        cabecalhos.update(headers)

    corpo = None
    if data is not None:
        corpo = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
        # Sem isso, o urllib envia application/x-www-form-urlencoded e a
        # GitHub API pode responder 415 ou interpretar o body errado.
        if not isinstance(data, bytes) and "Content-Type" not in cabecalhos:
            cabecalhos["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=corpo, headers=cabecalhos, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} em {url}: {detalhe[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Falha de rede em {url}: {e}") from e


# ─── Etapa 1: Build PyInstaller ─────────────────────────────────────────────

def etapa_build() -> int:
    log("\n[1/4] Build PyInstaller (GUI + CLI)...")
    return rodar([sys.executable, str(BUILD_SCRIPT), "--both"])


# ─── Etapa 2: Instalador Inno Setup ─────────────────────────────────────────

def etapa_instalador(versao: str, iscc: str) -> int:
    log("\n[2/4] Gerando instalador com Inno Setup...")
    if not os.path.isfile(iscc):
        return erro(
            f"ISCC.exe nao encontrado em '{iscc}'. Instale o Inno Setup ou "
            "informe --iscc <caminho>."
        )
    return rodar([iscc, f"/DMyAppVersion={versao}", str(ISS_SCRIPT)])


def localizar_instalador(versao: str) -> Path:
    """Retorna o caminho esperado do instalador gerado."""
    return INSTALLER_DIR / f"YouTube-Downloader-Setup-{versao}.exe"


# ─── Etapa 3: GitHub Release ────────────────────────────────────────────────

def criar_release_github(repo: str, versao: str, notes: str, token: str) -> Dict:
    """Cria a GitHub Release (tag v<versao>) e retorna o dict da release."""
    url = f"{GITHUB_API}/repos/{repo}/releases"
    payload = {
        "tag_name": f"v{versao}",
        "name": f"v{versao}",
        "body": notes or f"Release {versao}",
        "draft": False,
        "prerelease": False,
    }
    log(f"  Criando release v{versao} em {repo}...")
    return http_json(url, method="POST", token=token, data=payload)


def enviar_asset(repo: str, release_id: int, arquivo: Path, token: str) -> Dict:
    """Envia o instalador como asset da release e retorna o dict do asset."""
    nome = arquivo.name
    url = (
        f"{GITHUB_UPLOADS}/repos/{repo}/releases/{release_id}/assets"
        f"?name={urllib.parse.quote(nome)}"
    )
    log(f"  Enviando asset {nome} ({arquivo.stat().st_size // (1024 * 1024)} MB)...")
    with open(arquivo, "rb") as f:
        dados = f.read()
    return http_json(
        url, method="POST", token=token, data=dados,
        headers={"Content-Type": "application/octet-stream"},
    )


def etapa_github(repo: str, versao: str, notes: str, token: str, instalador: Path):
    """Retorna (url_download, url_pagina)."""
    log("\n[3/4] Criando GitHub Release e enviando asset...")
    release = criar_release_github(repo, versao, notes, token)
    release_id = release.get("id")
    if not release_id:
        raise RuntimeError(f"Falha ao criar release: {release}")

    if instalador.exists():
        asset = enviar_asset(repo, release_id, instalador, token)
        url_download = asset.get("browser_download_url", "")
    else:
        url_download = ""

    url_pagina = release.get("html_url", f"https://github.com/{repo}/releases/tag/v{versao}")
    log(f"  Pagina: {url_pagina}")
    if url_download:
        log(f"  Download direto: {url_download}")
    return url_download, url_pagina


# ─── Etapa 4: Publicar no servidor de atualizacoes ──────────────────────────

def etapa_publicar(versao: str, notes: str, url_download: str, url_pagina: str,
                   server: str, token: str, sha256: str, private_key: str = "",
                   commit: bool = True) -> int:
    log("\n[4/4] Publicando no servidor de atualizacoes...")
    from publish_release import publicar

    if DRY_RUN:
        log(
            f"  (dry-run) publicar(version={versao}, server={server}, "
            f"windows_url={url_download}, sha256={sha256[:12]}..., commit={commit})"
        )
        return 0

    try:
        publicar(
            version=versao,
            server=server,
            token=token,
            notes=notes,
            release_page=url_pagina,
            windows_url=url_download,
            windows_sha256=sha256,
            private_key=private_key,
            commit=commit,
        )
        return 0
    except RuntimeError as e:
        return erro(f"Falha ao publicar no servidor: {e}")


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    global DRY_RUN

    parser = argparse.ArgumentParser(
        description="Pipeline completa: build -> instalador -> GitHub -> servidor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Tokens:\n  GitHub: --github-token ou env GH_TOKEN/GITHUB_TOKEN\n  Servidor: --token ou env PUBLISH_TOKEN",
    )
    parser.add_argument("--version", required=True, help="Versao da release (ex.: 1.1.0)")
    parser.add_argument("--notes", default="", help="Notas da versao")
    parser.add_argument("--repo", default="", help="Repositorio 'usuario/repo' (padrao: git remote)")
    parser.add_argument("--server", default="", help="URL do servidor de atualizacoes")
    parser.add_argument("--iscc", default="", help="Caminho do ISCC.exe")

    parser.add_argument("--github-token", default=os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", "")), help="Token do GitHub")
    parser.add_argument("--token", default=os.environ.get("PUBLISH_TOKEN", ""), help="Token admin do servidor")
    parser.add_argument("--windows-url", default="", help="URL do instalador (usado com --skip-github)")
    parser.add_argument("--release-page", default="", help="URL da pagina da release (usado com --skip-github)")
    parser.add_argument("--private-key", default=os.environ.get("UPDATE_PRIVATE_KEY", "update_private.pem"),
                        help="Chave privada para assinar (padrao: update_private.pem)")

    parser.add_argument("--skip-build", action="store_true", help="Pula PyInstaller")
    parser.add_argument("--skip-installer", action="store_true", help="Pula Inno Setup")
    parser.add_argument("--skip-github", action="store_true", help="Pula GitHub Release")
    parser.add_argument("--skip-publish", action="store_true", help="Pula publicacao no servidor")
    parser.add_argument("--no-commit", action="store_true",
                        help="Nao faz commit/push do manifest local (server/releases.json)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que faria")
    args = parser.parse_args()

    DRY_RUN = args.dry_run

    if not validar_versao(args.version):
        return erro(f"Versao invalida: '{args.version}'. Use o formato 1.2.3 ou 1.0.")

    log("=" * 60)
    log(f"  Pipeline de Release v{args.version}")
    log("=" * 60)

    # ─── Etapa 1: Build ────────────────────────────────────────────────────
    if not args.skip_build:
        codigo_build = etapa_build()
        if codigo_build != 0 and not DRY_RUN:
            return erro("Build PyInstaller falhou.")
    else:
        log("[1/4] Build pulado (--skip-build)")

    # ─── Etapa 2: Instalador ───────────────────────────────────────────────
    iscc = args.iscc or encontrar_iscc() or ""
    if not args.skip_installer:
        if DRY_RUN:
            log(f"[2/4] (dry-run) ISCC /DMyAppVersion={args.version} installer.iss")
        elif etapa_instalador(args.version, iscc) != 0:
            return erro("Geracao do instalador falhou.")
    else:
        log("[2/4] Instalador pulado (--skip-installer)")

    instalador = localizar_instalador(args.version)
    sha256 = ""
    if instalador.exists():
        sha256 = sha256_arquivo(str(instalador))
        log(f"\n  Instalador: {instalador} ({instalador.stat().st_size // (1024 * 1024)} MB)")
        log(f"  SHA-256: {sha256}")
    elif not args.skip_installer and not DRY_RUN:
        log(f"  [aviso] instalador nao encontrado em {instalador}")

    # ─── Etapa 3: GitHub ───────────────────────────────────────────────────
    url_download, url_pagina = args.windows_url, args.release_page
    if not args.skip_github:
        repo = args.repo or repo_do_git()
        if not repo:
            return erro(
                "Nao foi possivel identificar o repositorio. Informe --repo usuario/repo."
            )
        if not args.github_token:
            return erro(
                "Informe --github-token ou defina a variavel GH_TOKEN/GITHUB_TOKEN."
            )
        try:
            url_download, url_pagina = etapa_github(
                repo, args.version, args.notes, args.github_token, instalador
            )
        except RuntimeError as e:
            return erro(f"Falha no GitHub: {e}")
    else:
        log("[3/4] GitHub Release pulado (--skip-github)")

    # ─── Etapa 4: Servidor ─────────────────────────────────────────────────
    if not args.skip_publish:
        if not url_download:
            return erro(
                "Sem URL de download. Gere o GitHub Release (sem --skip-github) "
                "ou informe --windows-url <link-do-instalador>."
            )
        if not args.server:
            return erro("Informe --server <URL-do-Render> ou use --skip-publish.")
        if not args.token:
            return erro("Informe --token <ADMIN> ou defina PUBLISH_TOKEN (ou use --skip-publish).")
        if etapa_publicar(
            args.version, args.notes, url_download, url_pagina,
            args.server, args.token, sha256, args.private_key,
            commit=not args.no_commit,
        ) != 0:
            return erro("Publicacao no servidor falhou.")
    else:
        log("[4/4] Publicacao no servidor pulada (--skip-publish)")

    log("\n" + "=" * 60)
    log(f"  Release v{args.version} concluida!")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
