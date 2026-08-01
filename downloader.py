#!/usr/bin/env python3
"""
downloader.py - Motor compartilhado de downloads (yt-dlp).
Centraliza a construcao de comandos, mapas de formato/qualidade, informacoes
de video, verificacao de ambiente e atualizacao do yt-dlp.
Usado tanto pela GUI (yt-downloader-gui.py) quanto pelo CLI (yt-downloader.py).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


# ─── Constantes ──────────────────────────────────────────────────────────────

FORMATOS_VALIDOS = ["mp4", "mp3", "webm", "mkv"]

QUALIDADE_LABELS = [
    "Melhor disponivel",
    "4K (2160p)",
    "2K (1440p)",
    "Full HD (1080p)",
    "HD (720p)",
    "SD (480p)",
    "SD (360p)",
]

QUALIDADE_MAP: Dict[str, str] = {
    "Melhor disponivel": "best",
    "4K (2160p)": "2160p",
    "2K (1440p)": "1440p",
    "Full HD (1080p)": "1080p",
    "HD (720p)": "720p",
    "SD (480p)": "480p",
    "SD (360p)": "360p",
}

# Navegadores suportados para --cookies-from-browser
NAVEGADORES_COOKIES = [
    "chrome",
    "firefox",
    "edge",
    "opera",
    "brave",
    "vivaldi",
    "chromium",
]


# ─── Utilitarios ─────────────────────────────────────────────────────────────

def formatar_duracao(segundos: float) -> str:
    """Formata duracao em segundos para exibicao amigavel."""
    h, r = divmod(int(segundos), 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h}h {m:02d}min {s:02d}s"
    return f"{m}min {s:02d}s"


def localizar_ytdlp() -> List[str]:
    """
    Retorna a lista de argumentos para invocar o yt-dlp.
    Prioriza o executavel no PATH; caso contrario, tenta 'python -m yt_dlp'.
    """
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return []


def verificar_ytdlp() -> bool:
    """Retorna True se o yt-dlp estiver disponivel (PATH ou modulo)."""
    return bool(localizar_ytdlp())


def localizar_ffmpeg_dir() -> Optional[Path]:
    """
    Retorna o diretorio que contem ffmpeg.exe/ffprobe.exe empacotados, ou None.

    Prioridade:
      1. Pasta 'ffmpeg' junto ao executavel (instalador/{app}/ffmpeg, dist/ffmpeg)
      2. Pasta 'ffmpeg' na raiz do projeto (execucao como script)

    Retorna None se o ffmpeg estiver apenas no PATH do sistema (nao precisa
    de --ffmpeg-location) ou ausente.
    """
    candidatos: List[Path] = []

    if getattr(sys, "frozen", False):
        candidatos.append(Path(sys.executable).parent / "ffmpeg")
        candidatos.append(Path(sys.executable).parent)
    else:
        candidatos.append(Path(__file__).parent / "ffmpeg")

    for d in candidatos:
        if (d / "ffmpeg.exe").is_file() and (d / "ffprobe.exe").is_file():
            return d
    return None


def verificar_ffmpeg() -> bool:
    """Retorna True se o ffmpeg estiver disponivel (empacotado ou no PATH)."""
    if localizar_ffmpeg_dir():
        return True
    return shutil.which("ffmpeg") is not None


# ─── Construcao de comando de download ───────────────────────────────────────

def _mapa_qualidade(formato: str) -> Dict[str, str]:
    """Mapa de qualidade -> format selecionada do yt-dlp por container."""
    if formato == "mp4":
        return {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "2160p": "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160][ext=mp4]/best",
            "1440p": "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440][ext=mp4]/best",
            "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
            "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
            "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best",
        }
    if formato == "webm":
        return {
            "best": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
            "2160p": "bestvideo[height<=2160][ext=webm]+bestaudio[ext=webm]/best[height<=2160][ext=webm]/best",
            "1440p": "bestvideo[height<=1440][ext=webm]+bestaudio[ext=webm]/best[height<=1440][ext=webm]/best",
            "1080p": "bestvideo[height<=1080][ext=webm]+bestaudio[ext=webm]/best[height<=1080][ext=webm]/best",
            "720p": "bestvideo[height<=720][ext=webm]+bestaudio[ext=webm]/best[height<=720][ext=webm]/best",
            "480p": "bestvideo[height<=480][ext=webm]+bestaudio[ext=webm]/best[height<=480][ext=webm]/best",
            "360p": "bestvideo[height<=360][ext=webm]+bestaudio[ext=webm]/best[height<=360][ext=webm]/best",
        }
    # mkv (e qualquer outro container)
    return {
        "best": "bestvideo+bestaudio/best",
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    }


def montar_comando_download(
    url: str,
    formato: str,
    qualidade: str = "best",
    diretorio: Optional[Path] = None,
    playlist_start: Optional[int] = None,
    playlist_end: Optional[int] = None,
    subs: bool = False,
    subs_auto: bool = False,
    subs_idioma: str = "pt",
    navegador_cookies: Optional[str] = None,
) -> List[str]:
    """
    Monta o comando yt-dlp completo para download.
    Ponto unico de configuracao de formato/qualidade/playlist/legendas/cookies.
    """
    if diretorio is None:
        diretorio = Path.home() / "Downloads" / "YouTube Downloads"
    diretorio = Path(diretorio)

    cmd = localizar_ytdlp() + [
        "--no-warnings",
        "--progress",
        "--no-playlist",
        "-o", str(diretorio / "%(title)s.%(ext)s"),
    ]

    # ─── ffmpeg empacotado (instalador/dist) ──────────────────────────────
    ffmpeg_dir = localizar_ffmpeg_dir()
    if ffmpeg_dir:
        cmd.extend(["--ffmpeg-location", str(ffmpeg_dir)])

    # ─── Configuracao por formato ──────────────────────────────────────────
    if formato == "mp3":
        cmd.extend([
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--add-metadata",
        ])
    elif formato in ("mp4", "webm", "mkv"):
        cmd.extend([
            "--merge-output-format", formato,
            "--embed-chapters",
            "--embed-metadata",
        ])
        qual_map = _mapa_qualidade(formato)
        cmd.extend(["-f", qual_map.get(qualidade, qual_map["best"])])

    # ─── Opcoes de playlist ────────────────────────────────────────────────
    if playlist_start is not None or playlist_end is not None:
        if "--no-playlist" in cmd:
            cmd.remove("--no-playlist")
        if playlist_start is not None:
            cmd.extend(["--playlist-start", str(playlist_start)])
        if playlist_end is not None:
            cmd.extend(["--playlist-end", str(playlist_end)])

    # ─── Legendas ──────────────────────────────────────────────────────────
    if subs:
        cmd.extend([
            "--write-subs",
            "--sub-langs", subs_idioma,
            "--sub-format", "srt",
            "--convert-subs", "srt",
        ])
        if subs_auto:
            cmd.extend(["--write-auto-subs"])

    # ─── Cookies (acesso a videos com restricao/login) ────────────────────
    if navegador_cookies:
        cmd.extend(["--cookies-from-browser", navegador_cookies])

    return cmd


# ─── Informacoes do video ────────────────────────────────────────────────────

def obter_info_video(
    url: str,
    timeout: int = 30,
    on_error: Optional[Callable[[str], None]] = None,
) -> Optional[dict]:
    """
    Obtem informacoes do video via yt-dlp --dump-json.
    Retorna o dicionario de info ou None em caso de erro.
    on_error: callback opcional recebendo a mensagem de erro.
    """
    try:
        cmd = localizar_ytdlp() + [
            "--dump-json",
            "--no-warnings",
            "--flat-playlist",
            url,
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if resultado.returncode != 0:
            if on_error:
                on_error(resultado.stderr.strip() or "Erro ao obter informacoes.")
            return None

        linhas = resultado.stdout.strip().split("\n")
        if not linhas or not linhas[0]:
            if on_error:
                on_error("Nenhum dado encontrado.")
            return None

        info = json.loads(linhas[0])

        if info.get("playlist_count", 0) > 1:
            info["is_playlist"] = True

        return info

    except subprocess.TimeoutExpired:
        if on_error:
            on_error("Tempo limite excedido ao obter informacoes.")
        return None
    except json.JSONDecodeError:
        if on_error:
            on_error("Erro ao processar resposta do yt-dlp.")
        return None
    except Exception as e:
        if on_error:
            on_error(str(e))
        return None


# ─── Atualizacao do yt-dlp ───────────────────────────────────────────────────

def atualizar_ytdlp() -> Tuple[bool, str]:
    """
    Atualiza o yt-dlp para a versao mais recente.
    Tenta via pip; se falhar, tenta 'yt-dlp -U'.
    Retorna (sucesso, mensagem).
    """
    erro_pip = ""

    # 1) Tenta via pip
    try:
        resultado = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True, text=True, timeout=120,
        )
        if resultado.returncode == 0:
            return True, "yt-dlp atualizado com sucesso!"
        erro_pip = (resultado.stderr or resultado.stdout).strip()
    except Exception as e:
        erro_pip = str(e)

    # 2) Tenta atualizacao interna do yt-dlp
    try:
        base = localizar_ytdlp()
        if not base:
            return False, "yt-dlp nao encontrado. Instale com: pip install yt-dlp"
        cmd = base + ["-U"]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if resultado.returncode == 0:
            return True, "yt-dlp atualizado com sucesso!"
        msg = (resultado.stderr or resultado.stdout).strip() or "Falha ao atualizar."
        return False, f"{msg} (via pip: {erro_pip})"
    except Exception as e:
        return False, f"Falha ao atualizar o yt-dlp: {e} (via pip: {erro_pip})"


if __name__ == "__main__":
    # Teste rapido
    print("Teste do motor compartilhado:")
    print(f"  yt-dlp encontrado: {verificar_ytdlp()}")
    print(f"  ffmpeg encontrado: {verificar_ffmpeg()}")
    print(f"  formatar_duracao(3661) = {formatar_duracao(3661)}")
    cmd = montar_comando_download(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "mp4", "1080p",
        subs=True, subs_idioma="pt", navegador_cookies="chrome",
        playlist_start=2, playlist_end=5,
    )
    print("  comando montado:")
    print("   ", " ".join(cmd))
