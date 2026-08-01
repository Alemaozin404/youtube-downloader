#!/usr/bin/env python3
"""
Sistema de Atualizacao Automatica (cliente)
============================================
Modulo usado pelo app (GUI/CLI) para verificar, baixar e instalar
novas versoes publicadas no servidor (Render).

Uso (API):
    from updater import verificar_atualizacao, baixar_instalador, ...
    info = verificar_atualizacao("https://SEU-SERVIDOR.onrender.com", "1.0")
    if info:
        baixar_instalador(info.platform.url, caminho, reporthook=...)
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

# Versao atual do app (mantenha sincronizada com config_manager / installer.iss)
APP_VERSION = "1.0"

# URL padrao do servidor de atualizacoes (sobrescrita pela config do usuario)
UPDATE_URL = "https://SEU-SERVIDOR.onrender.com"

_TIMEOUT_PADRAO = 15


# ─── Comparacao de versoes ─────────────────────────────────────────────────

def comparar_versoes(a: str, b: str) -> int:
    """Compara duas versoes como '1.0', '1.2.3'. Retorna -1, 0 ou 1.

    '1.0' == '1.0.0' (zeros a direita sao ignorados).
    """
    def _tupla(v: str):
        partes = re.findall(r"\d+|[a-zA-Z]+", v or "0")
        return tuple(int(p) if p.isdigit() else p for p in partes)

    ta, tb = _tupla(a), _tupla(b)
    n = max(len(ta), len(tb))
    for i in range(n):
        x = ta[i] if i < len(ta) else 0
        y = tb[i] if i < len(tb) else 0
        if isinstance(x, int) and isinstance(y, int):
            if x != y:
                return 1 if x > y else -1
        elif isinstance(x, str) and isinstance(y, str):
            if x != y:
                return 1 if x > y else -1
        else:
            # Um e numero, outro e texto: texto conta como pre-release (menor)
            return -1 if isinstance(x, str) else 1
    return 0


def plataforma_atual() -> str:
    """Retorna a plataforma atual: 'windows', 'macos' ou 'linux'."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


# ─── Estruturas de dados ────────────────────────────────────────────────────

@dataclass
class ArquivoPlataforma:
    """Binario/instalador de uma versao para uma plataforma."""
    url: str = ""
    sha256: str = ""
    size: int = 0
    filename: str = ""
    signature: str = ""  # Assinatura Ed25519 (base64) do digest sha256


@dataclass
class AtualizacaoInfo:
    """Informacoes de uma versao disponivel no servidor."""
    version: str = ""
    min_required_version: str = ""
    published_at: str = ""
    notes: str = ""
    release_page: str = ""
    mandatory: bool = False
    platform: Optional[ArquivoPlataforma] = None


# ─── Consulta ao servidor ───────────────────────────────────────────────────

def verificar_atualizacao(
    update_url: str = UPDATE_URL,
    current_version: str = APP_VERSION,
    platform: str = "windows",
    timeout: int = _TIMEOUT_PADRAO,
) -> Optional[AtualizacaoInfo]:
    """Consulta o servidor e retorna AtualizacaoInfo ou None.

    Levanta urllib.error.URLError em caso de falha de rede.
    """
    base = update_url.rstrip("/")
    url = (
        f"{base}/api/update/check"
        f"?current_version={urllib.parse.quote(current_version)}"
        f"&platform={platform}"
    )
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        dados = json.loads(resp.read().decode("utf-8"))

    if not dados.get("update_available"):
        return None

    plat = dados.get("platform") or {}
    return AtualizacaoInfo(
        version=dados.get("latest_version", ""),
        min_required_version=dados.get("min_required_version", ""),
        published_at=dados.get("published_at", ""),
        notes=dados.get("notes", ""),
        release_page=dados.get("release_page", ""),
        mandatory=bool(dados.get("mandatory")),
        platform=ArquivoPlataforma(**plat) if plat else None,
    )


# ─── Download e verificacao ─────────────────────────────────────────────────

def baixar_instalador(
    url: str,
    destino: str,
    reporthook: Optional[Callable[[int, int, int], None]] = None,
    timeout: int = _TIMEOUT_PADRAO,
) -> str:
    """Baixa o arquivo para `destino`. reporthook(count, block_size, total)."""
    urllib.request.urlretrieve(url, destino, reporthook=reporthook)
    return destino


def calcular_sha256(caminho: str) -> str:
    """Calcula o SHA-256 de um arquivo."""
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def verificar_sha256(caminho: str, esperado: str) -> bool:
    """Verifica se o SHA-256 do arquivo bate com o esperado (case-insensitive)."""
    if not esperado:
        return True  # Sem hash esperado, considera ok
    return calcular_sha256(caminho).lower() == esperado.strip().lower()


def verificar_assinatura_instalador(caminho: str, plataforma: "ArquivoPlataforma") -> str:
    """Verifica a assinatura Ed25519 do instalador baixado (autenticidade).

    Retorna:
      "ok"             - assinatura valida
      "invalida"       - assinatura presente mas NAO confere (perigo: adulterado)
      "sem_assinatura" - servidor nao assina ou app sem chave/cryptography (legado)
    """
    if not plataforma or not plataforma.signature:
        return "sem_assinatura"
    try:
        from signing import carregar_chave_publica, verificar_assinatura
    except ImportError:
        return "sem_assinatura"  # cryptography ausente: nao ha como verificar
    chave = carregar_chave_publica()
    if chave is None:
        return "sem_assinatura"  # app compilado sem chave embutida (build antigo)
    sha = calcular_sha256(caminho)
    ok = verificar_assinatura(sha, plataforma.signature, chave_publica=chave)
    return "ok" if ok else "invalida"


# ─── Instalacao ─────────────────────────────────────────────────────────────

def executar_instalador(caminho: str) -> bool:
    """Executa o instalador baixado (Windows) ou abre-o (outros SOs)."""
    if not os.path.exists(caminho):
        return False
    try:
        if sys.platform == "win32":
            # Inno Setup: instala em silencio se possivel
            subprocess.Popen([caminho], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho], shell=False)
        else:
            subprocess.Popen(["xdg-open", caminho], shell=False)
        return True
    except Exception:
        return False


def caminho_instalador_temp(versao: str) -> str:
    """Retorna um caminho temporario para o instalador de uma versao."""
    pasta = os.path.join(tempfile.gettempdir(), "yt-downloader-updates")
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, f"YouTube-Downloader-Setup-{versao}.exe")


# ─── Teste rapido ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import urllib.error

    versao_local = sys.argv[1] if len(sys.argv) > 1 else APP_VERSION
    url_servidor = sys.argv[2] if len(sys.argv) > 2 else UPDATE_URL
    try:
        info = verificar_atualizacao(url_servidor, versao_local)
        if info:
            print(f"Nova versao disponivel: {info.version}")
            print(f"Notas: {info.notes or 'Sem notas'}")
            print(f"Arquivo: {info.platform.filename if info.platform else 'N/A'}")
        else:
            print("Nenhuma atualizacao disponivel.")
    except urllib.error.URLError as e:
        print(f"Falha ao consultar o servidor: {e}")
