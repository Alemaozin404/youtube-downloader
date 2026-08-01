#!/usr/bin/env python3
"""
YouTube Downloader v1.2.0
Baixe videos e audios do YouTube facilmente!
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional
from platforms import validar_url, detectar_plataforma, nome_plataforma
from downloader import (
    formatar_duracao,
    montar_comando_download,
    obter_info_video as obter_info_ytdlp,
    verificar_ytdlp,
    verificar_ffmpeg,
    atualizar_ytdlp,
    localizar_ytdlp,
)

# ─── Configurar encoding para UTF-8 no Windows ──────────────────────────────
if sys.platform == "win32":
    try:
        # Tenta configurar o console para UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        # Python < 3.7
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    
    # Também tenta mudar a code page do console
    os.system("chcp 65001 > nul 2>&1")


# ─── Cores para o terminal ──────────────────────────────────────────────────
try:
    import colorama
    colorama.init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def c(text: str, *styles) -> str:
    """Aplica estilos ao texto. Remove ANSI se nao for TTY."""
    if not sys.stdout.isatty():
        return re.sub(r"\033\[[0-9;]*m", "", text)
    return "".join(styles) + text + Colors.RESET


# ─── Estado global ───────────────────────────────────────────────────────────
_DIRETORIO_ATUAL: Optional[Path] = None


# ─── Utilitarios ────────────────────────────────────────────────────────────

def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def pausar():
    input(f"\n{c('[Pressione Enter para continuar...]', Colors.DIM)}")


def obter_diretorio_downloads() -> Path:
    global _DIRETORIO_ATUAL
    if _DIRETORIO_ATUAL is not None:
        _DIRETORIO_ATUAL.mkdir(parents=True, exist_ok=True)
        return _DIRETORIO_ATUAL
    diretorio = Path.home() / "Downloads" / "YouTube Downloads"
    diretorio.mkdir(parents=True, exist_ok=True)
    return diretorio


def definir_diretorio_downloads(path: Path):
    global _DIRETORIO_ATUAL
    path.mkdir(parents=True, exist_ok=True)
    _DIRETORIO_ATUAL = path


# ─── Banner ──────────────────────────────────────────────────────────────────

def mostrar_banner():
    limpar_tela()
    print(f"""
  {c('+======================================+', Colors.BRIGHT_RED)}
  {c('|', Colors.BRIGHT_RED)}     {c('YouTube Downloader v1.2.0', Colors.BRIGHT_WHITE + Colors.BOLD)}     {c('|', Colors.BRIGHT_RED)}
  {c('|', Colors.BRIGHT_RED)}  {c('Baixe videos e audios do YouTube!', Colors.DIM)}  {c('|', Colors.BRIGHT_RED)}
  {c('+======================================+', Colors.BRIGHT_RED)}
    """)


# ─── Funcoes principais ──────────────────────────────────────────────────────

def obter_info_video(url: str) -> Optional[dict]:
    print(f"\n  {c('Obtendo informacoes do video...', Colors.CYAN)}\n")

    def _erro(msg: str):
        print(f"  {c('Erro:', Colors.RED)} {msg}")

    return obter_info_ytdlp(url, on_error=_erro)


def mostrar_info_video(info: dict):
    if info.get("is_playlist"):
        print(f"  {c('Playlist:', Colors.BRIGHT_MAGENTA)} {info.get('playlist_title', 'N/A')}")
        print(f"  {c('  Total de videos:', Colors.DIM)} {info.get('playlist_count', 'N/A')}")
        return

    titulo = info.get("title", "N/A")
    duracao = info.get("duration", 0)
    autor = info.get("uploader", "N/A")
    visualizacoes = info.get("view_count", 0)

    upload_date = info.get("upload_date", "")
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[:4]}"

    print(f"""
  {c('Video:', Colors.BRIGHT_CYAN)}
    {c('Titulo:', Colors.BOLD)} {titulo}
    {c('Autor:', Colors.DIM)} {autor}
    {c('Duracao:', Colors.DIM)} {formatar_duracao(duracao)}
    {c('Visualizacoes:', Colors.DIM)} {visualizacoes:,}
    {c('Data:', Colors.DIM)} {upload_date or 'N/A'}
    """)


def baixar_video(
    url: str,
    formato: str,
    qualidade: str = "best",
    diretorio: Optional[Path] = None,
    playlist_start: Optional[int] = None,
    playlist_end: Optional[int] = None
) -> bool:
    if diretorio is None:
        diretorio = obter_diretorio_downloads()

    diretorio.mkdir(parents=True, exist_ok=True)

    cmd = montar_comando_download(
        url, formato, qualidade, diretorio,
        playlist_start=playlist_start,
        playlist_end=playlist_end,
    )

    # ─── Rotulos para exibicao ─────────────────────────────────────────────
    if formato == "mp3":
        qual_label = "Melhor (320kbps)"
    else:
        qual_label = qualidade
    formato_label = formato.upper()

    # ─── Executa o download ─────────────────────────────────────────────────
    print(f"""
  {c('Iniciando download...', Colors.BRIGHT_CYAN)}
    {c('Formato:', Colors.DIM)} {formato_label}
    {c('Qualidade:', Colors.DIM)} {qual_label}
    {c('Destino:', Colors.DIM)} {diretorio}
    """)

    try:
        processo = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace"
        )

        for linha in processo.stdout:
            linha = linha.strip()
            if not linha:
                continue

            if linha.startswith("[youtube]") or linha.startswith("[info]") or linha.startswith("[debug]"):
                continue

            if "[download]" in linha and "%" in linha:
                match = re.search(r"(\d+\.?\d*)%", linha)
                if match:
                    pct = match.group(1)
                    print(f"\r  {c('Baixando...', Colors.CYAN)} {c(f'{pct}%', Colors.BRIGHT_GREEN)}", end="", flush=True)
            elif "has already been downloaded" in linha.lower():
                print(f"  {c('Ja baixado anteriormente!', Colors.YELLOW)}")
            elif "[download]" in linha and "100%" in linha:
                print(f"\r  {c('Download concluido!', Colors.GREEN)} {c('Processando...', Colors.DIM)}", end="", flush=True)
            elif "[ExtractAudio]" in linha:
                print(f"\r  {c('Convertendo audio...', Colors.MAGENTA)}", end="", flush=True)
            elif "[Merger]" in linha:
                print(f"\r  {c('Mesclando video+audio...', Colors.MAGENTA)}", end="", flush=True)
            elif "[Metadata]" in linha:
                print(f"\r  {c('Adicionando metadados...', Colors.MAGENTA)}", end="", flush=True)
            elif "[EmbedThumbnail]" in linha:
                print(f"\r  {c('Incorporando thumbnail...', Colors.MAGENTA)}", end="", flush=True)
            elif "[Fixup" in linha:
                print(f"\r  {c('Corrigindo arquivo...', Colors.MAGENTA)}", end="", flush=True)

        processo.wait()

        print()
        if processo.returncode == 0:
            print(f"\n  {c('Download concluido com sucesso!', Colors.GREEN)}")
            print(f"  {c('Salvo em:', Colors.DIM)} {diretorio}")
            return True
        else:
            print(f"  {c('Erro durante o download.', Colors.RED)}")
            return False

    except KeyboardInterrupt:
        print(f"\n  {c('Download interrompido pelo usuario.', Colors.YELLOW)}")
        return False
    except Exception as e:
        print(f"  {c(f'Erro: {e}', Colors.RED)}")
        return False


# ─── Menus interativos ───────────────────────────────────────────────────────

def menu_principal():
    while True:
        mostrar_banner()

        dir_atual = obter_diretorio_downloads()
        print(f"  {c('Diretorio de saida:', Colors.DIM)} {c(str(dir_atual), Colors.CYAN)}\n")

        print(f"  {c('1.', Colors.BRIGHT_YELLOW)} {c('Baixar video', Colors.BOLD)}")
        print(f"  {c('2.', Colors.BRIGHT_YELLOW)} {c('Baixar playlist', Colors.BOLD)}")
        print(f"  {c('3.', Colors.BRIGHT_YELLOW)} {c('Baixar apenas audio (MP3)', Colors.BOLD)}")
        print(f"  {c('4.', Colors.BRIGHT_YELLOW)} {c('Alterar diretorio de saida', Colors.BOLD)}")
        print(f"  {c('5.', Colors.BRIGHT_YELLOW)} {c('Ver formatos disponiveis', Colors.BOLD)}")
        print(f"  {c('6.', Colors.BRIGHT_YELLOW)} {c('Historico de downloads', Colors.BOLD)}")
        print(f"  {c('7.', Colors.BRIGHT_YELLOW)} {c('Limpar historico', Colors.BOLD)}")
        print(f"  {c('8.', Colors.BRIGHT_YELLOW)} {c('Atualizar yt-dlp', Colors.BOLD)}")
        print(f"  {c('0.', Colors.BRIGHT_RED)}  {c('Sair', Colors.RED)}\n")

        opcao = input(f"  {c('Escolha uma opcao:', Colors.CYAN)} ").strip()

        if opcao == "0":
            print(f"\n  {c('Ate logo!', Colors.MAGENTA)}\n")
            sys.exit(0)
        elif opcao == "1":
            menu_formato_video()
        elif opcao == "2":
            menu_playlist()
        elif opcao == "3":
            menu_mp3()
        elif opcao == "4":
            menu_diretorio()
        elif opcao == "5":
            menu_formatos_disponiveis()
        elif opcao == "6":
            menu_historico()
        elif opcao == "7":
            menu_limpar_historico()
        elif opcao == "8":
            menu_atualizar_ytdlp()
        else:
            print(f"\n  {c('Opcao invalida!', Colors.RED)}")
            pausar()


def menu_formato_video():
    url = obter_url()
    if not url:
        return

    info = obter_info_video(url)
    if not info:
        pausar()
        return

    mostrar_info_video(info)

    print(f"  {c('Selecione o formato:', Colors.BOLD)}")
    print(f"  {c('1.', Colors.BRIGHT_YELLOW)} MP4  {c('(Recomendado)', Colors.DIM)}")
    print(f"  {c('2.', Colors.BRIGHT_YELLOW)} WEBM {c('(Google/Web)', Colors.DIM)}")
    print(f"  {c('3.', Colors.BRIGHT_YELLOW)} MKV  {c('(Alta qualidade)', Colors.DIM)}")

    fmt_opcao = input(f"\n  {c('Formato:', Colors.CYAN)} ").strip()

    formato_map = {"1": "mp4", "2": "webm", "3": "mkv"}
    formato = formato_map.get(fmt_opcao, "mp4")

    qualidade = menu_qualidade()

    if baixar_video(url, formato, qualidade):
        pausar()


def menu_playlist():
    print(f"  {c('Playlist', Colors.BRIGHT_MAGENTA)}")
    url = obter_url()
    if not url:
        return

    info = obter_info_video(url)
    if not info:
        pausar()
        return

    if info.get("is_playlist"):
        print(f"\n  {c('Playlist:', Colors.BOLD)} {info.get('playlist_title', 'N/A')}")
        total = info.get("playlist_count", 0)
        print(f"  {c('Total de videos:', Colors.DIM)} {total}")
    else:
        print(f"\n  {c('Esta URL nao e uma playlist.', Colors.YELLOW)}")
        print(f"  {c('Dica:', Colors.CYAN)} Cole a URL de uma playlist do YouTube.")
        pausar()
        return

    print()
    inicio = input(f"  {c('Video inicial (Enter = 1):', Colors.CYAN)} ").strip()
    fim = input(f"  {c('Video final (Enter = todos):', Colors.CYAN)} ").strip()

    playlist_start = int(inicio) if inicio.isdigit() else None
    playlist_end = int(fim) if fim.isdigit() else None

    print(f"\n  {c('Selecione o formato:', Colors.BOLD)}")
    print(f"  {c('1.', Colors.BRIGHT_YELLOW)} MP4")
    print(f"  {c('2.', Colors.BRIGHT_YELLOW)} WEBM")
    print(f"  {c('3.', Colors.BRIGHT_YELLOW)} MKV")
    print(f"  {c('4.', Colors.BRIGHT_YELLOW)} MP3 (apenas audio)")

    fmt_opcao = input(f"\n  {c('Formato:', Colors.CYAN)} ").strip()

    formato_map = {"1": "mp4", "2": "webm", "3": "mkv", "4": "mp3"}
    formato = formato_map.get(fmt_opcao, "mp4")

    qualidade = menu_qualidade() if formato != "mp3" else "best"

    if baixar_video(url, formato, qualidade, playlist_start=playlist_start, playlist_end=playlist_end):
        pausar()


def menu_mp3():
    url = obter_url()
    if not url:
        return

    info = obter_info_video(url)
    if not info:
        pausar()
        return

    if not info.get("is_playlist"):
        mostrar_info_video(info)

    print(f"  {c('MP3 - Melhor qualidade (320kbps)', Colors.BRIGHT_MAGENTA)}")
    print(f"  {c('As thumbnails serao incorporadas ao arquivo.', Colors.DIM)}")

    if baixar_video(url, "mp3"):
        pausar()


def menu_qualidade() -> str:
    print(f"\n  {c('Selecione a qualidade:', Colors.BOLD)}")
    qualidades = [
        ("1", "Melhor disponivel", "best"),
        ("2", "4K (2160p)", "2160p"),
        ("3", "2K (1440p)", "1440p"),
        ("4", "Full HD (1080p)", "1080p"),
        ("5", "HD (720p)", "720p"),
        ("6", "SD (480p)", "480p"),
        ("7", "SD (360p)", "360p"),
    ]

    for num, label, _ in qualidades:
        rec = " (recomendado)" if num == "1" else ""
        print(f"  {c(f'{num}.', Colors.BRIGHT_YELLOW)} {label}{rec}")

    qual_opcao = input(f"\n  {c('Qualidade:', Colors.CYAN)} ").strip()
    qual_map = {n: q for n, _, q in qualidades}
    return qual_map.get(qual_opcao, "best")


def menu_diretorio():
    atual = obter_diretorio_downloads()
    print(f"\n  {c('Diretorio atual:', Colors.BOLD)}")
    print(f"  {c(atual, Colors.CYAN)}\n")

    print(f"  {c('Opcoes:', Colors.BOLD)}")
    print(f"  {c('1.', Colors.BRIGHT_YELLOW)} Usar diretorio padrao (Downloads/YouTube Downloads)")
    print(f"  {c('2.', Colors.BRIGHT_YELLOW)} Escolher novo diretorio")
    print(f"  {c('3.', Colors.BRIGHT_YELLOW)} Criar diretorio com data de hoje")

    opcao = input(f"\n  {c('Opcao:', Colors.CYAN)} ").strip()

    if opcao == "1":
        novo_dir = Path.home() / "Downloads" / "YouTube Downloads"
    elif opcao == "2":
        caminho = input(f"  {c('Caminho completo:', Colors.CYAN)} ").strip()
        if caminho:
            novo_dir = Path(caminho)
        else:
            print(f"  {c('Caminho invalido. Mantendo o atual.', Colors.YELLOW)}")
            pausar()
            return
    elif opcao == "3":
        hoje = datetime.now().strftime("%Y-%m-%d")
        novo_dir = Path.home() / "Downloads" / f"YouTube Downloads ({hoje})"
    else:
        print(f"  {c('Opcao invalida. Mantendo o atual.', Colors.YELLOW)}")
        pausar()
        return

    definir_diretorio_downloads(novo_dir)
    print(f"  {c('Diretorio alterado para:', Colors.GREEN)} {novo_dir}")
    pausar()


def menu_formatos_disponiveis():
    url = obter_url()
    if not url:
        return

    print(f"\n  {c('Buscando formatos disponiveis...', Colors.CYAN)}")

    try:
        cmd = localizar_ytdlp() + ["-F", "--no-warnings", url]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if resultado.returncode == 0 and resultado.stdout.strip():
            linhas = resultado.stdout.strip().split("\n")
            print(f"\n  {c('Formatos disponiveis:', Colors.BOLD)}")
            print(f"  {c('-' * 60, Colors.DIM)}")
            for linha in linhas:
                if linha.strip():
                    print(f"  {linha}")
            print(f"  {c('-' * 60, Colors.DIM)}")
        else:
            print(f"  {c('Nao foi possivel obter os formatos.', Colors.RED)}")
    except Exception as e:
        print(f"  {c(f'Erro: {e}', Colors.RED)}")

    pausar()


# ─── Input helpers ───────────────────────────────────────────────────────────

def obter_url() -> Optional[str]:
    print(f"\n  {c('Cole a URL do YouTube:', Colors.CYAN)}")
    url = input(f"  {c('>', Colors.BRIGHT_GREEN)} ").strip()

    if not url:
        print(f"  {c('URL nao pode estar vazia!', Colors.RED)}")
        pausar()
        return None

    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={url}"

    if not validar_url(url):
        print(f"  {c('URL invalida! Certifique-se de que e uma URL suportada.', Colors.RED)}")
        pausar()
        return None

    # Mostra plataforma detectada
    plat = detectar_plataforma(url)
    if plat:
        nome = plat["nome"]
        print(f"  {c(f'Plataforma: {nome}', Colors.DIM)}")

    return url


# ─── Ponto de entrada ────────────────────────────────────────────────────────

def main():
    try:
        erros = []

        if not verificar_ytdlp():
            erros.append("yt-dlp nao encontrado! Instale com: pip install yt-dlp")

        if not verificar_ffmpeg():
            erros.append(
                "ffmpeg nao encontrado! Necessario para processar audio/video.\n"
                "  Baixe em: https://ffmpeg.org/download.html\n"
                "  Ou instale com: winget install ffmpeg  (Windows 10/11)"
            )

        if erros:
            print(f"\n  {c('Erros de configuracao:', Colors.RED)}")
            for erro in erros:
                print(f"  {c('-', Colors.RED)} {erro}")
            print()
            input(f"  {c('[Pressione Enter para sair...]', Colors.DIM)}")
            sys.exit(1)

        # ─── Uso via linha de comando ──────────────────────────────────────
        if len(sys.argv) > 1:
            url = sys.argv[1]
            formato = sys.argv[2] if len(sys.argv) > 2 else "mp4"

            if not validar_url(url):
                print(f"{c('URL invalida!', Colors.RED)}")
                sys.exit(1)

            if formato not in ("mp4", "mp3", "webm", "mkv"):
                print(f"{c('Formato invalido! Use: mp4, mp3, webm ou mkv', Colors.RED)}")
                sys.exit(1)

            info = obter_info_video(url)
            if info:
                if not info.get("is_playlist"):
                    mostrar_info_video(info)
                baixar_video(url, formato)
            return

        # ─── Menu interativo ───────────────────────────────────────────────
        while True:
            try:
                menu_principal()
            except KeyboardInterrupt:
                print(f"\n\n  {c('Ate logo!', Colors.MAGENTA)}\n")
                sys.exit(0)

    except Exception as e:
        print(f"\n  {c(f'Erro inesperado: {e}', Colors.RED)}")
        sys.exit(1)


def menu_atualizar_ytdlp():
    """Atualiza o yt-dlp para a versao mais recente."""
    print(f"\n  {c('Atualizando yt-dlp...', Colors.CYAN)}")
    print(f"  {c('Isso pode levar alguns segundos. Aguarde...', Colors.DIM)}\n")

    ok, msg = atualizar_ytdlp()

    if ok:
        print(f"  {c(msg, Colors.GREEN)}")
    else:
        print(f"  {c(msg, Colors.RED)}")
    pausar()


def menu_historico():
    """Exibe historico de downloads no terminal."""
    from config_manager import get_config
    cfg = get_config()

    history = cfg.get_history(50)

    if not history:
        print(f"\n  {c('Nenhum download no historico.', Colors.YELLOW)}")
        pausar()
        return

    print(f"\n  {c('Historico de Downloads', Colors.BRIGHT_CYAN + Colors.BOLD)}")
    print(f"  {c(f'Total: {len(history)} registros', Colors.DIM)}")
    print(f"  {c('-' * 70, Colors.DIM)}")

    for i, entry in enumerate(history[:20]):
        titulo = entry.get("titulo", "Desconhecido")[:50]
        fmt = entry.get("formato", "-")
        data = entry.get("data", "-")

        print(f"  {c(f'{i+1}.', Colors.BRIGHT_YELLOW)} {c(titulo, Colors.BOLD)}")
        print(f"      {c(f'Formato: {fmt}', Colors.DIM)}  {c(f'Data: {data}', Colors.DIM)}")

    if len(history) > 20:
        print(f"  {c(f'... e mais {len(history) - 20} registros.', Colors.DIM)}")

    print(f"  {c('-' * 70, Colors.DIM)}")
    print(f"  {c('Digite o numero para re-baixar, ou 0 para voltar:', Colors.CYAN)}")

    try:
        choice = input(f"  {c('>', Colors.BRIGHT_GREEN)} ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(history):
                entry = history[idx]
                url = entry.get("url", "")
                if url:
                    fmt = entry.get("formato", "mp4").lower()
                    print(f"\n  {c('Re-baixando:', Colors.CYAN)} {entry.get('titulo', '')}")
                    info = obter_info_video(url)
                    if info:
                        mostrar_info_video(info)
                        baixar_video(url, fmt)
                    pausar()
    except (ValueError, IndexError):
        pass


def menu_limpar_historico():
    """Limpa todo o historico."""
    from config_manager import get_config
    cfg = get_config()

    confirm = input(f"\n  {c('Tem certeza? (s/N):', Colors.YELLOW)} ").strip().lower()
    if confirm == "s":
        cfg.clear_history()
        print(f"  {c('Historico limpo!', Colors.GREEN)}")
    else:
        print(f"  {c('Operacao cancelada.', Colors.DIM)}")
    pausar()


if __name__ == "__main__":
    main()
