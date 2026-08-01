#!/usr/bin/env python3
"""
Script para compilar o YouTube Downloader GUI em um executavel .exe
Usa PyInstaller para empacotar tudo em um unico arquivo.

Uso:
    python build_exe.py          # Compila a versao GUI
    python build_exe.py --cli    # Compila a versao CLI
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


# --- Configuracoes -----------------------------------------------------------
PROJECT_DIR = Path(__file__).parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
ICON_PATH = PROJECT_DIR / "youtube_icon.ico"

# Modulos Python customizados que o PyInstaller precisa incluir
HIDDEN_IMPORTS = [
    "config_manager",
    "download_queue_manager",
    "downloader",
    "platforms",
    "drop_handler",
    "updater",
    "signing",
    "update_public_key",
    "PIL",
    "PIL._tkinter_finder",
]


def obter_versao_pyinstaller() -> str:
    """Retorna a versao do PyInstaller instalado."""
    try:
        import PyInstaller
        return getattr(PyInstaller, "__version__", "desconhecida")
    except ImportError:
        return "nao instalado"


def limpar_cache():
    """Remove pastas de build anteriores."""
    for pasta in [DIST_DIR, BUILD_DIR]:
        if pasta.exists():
            shutil.rmtree(pasta)
            print(f"  Removido: {pasta}")


def montar_cmd_base(nome, entry_point, windowed=True):
    """Monta a lista de comandos base do PyInstaller."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", nome,
        "--noconfirm",
        "--clean",
    ]

    if windowed:
        cmd.append("--windowed")

    # Icone (se existir)
    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])

    # Hidden imports
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    # Caminho de busca para modulos locais
    cmd.extend(["--paths", str(PROJECT_DIR)])

    # Arquivo principal
    cmd.append(str(entry_point))

    return cmd


def compilar_gui():
    """Compila a versao GUI."""
    print("=" * 60)
    print("  Compilando YouTube Downloader GUI...")
    print("=" * 60)

    cmd = montar_cmd_base(
        nome="YouTube Downloader",
        entry_point=PROJECT_DIR / "yt-downloader-gui.py",
        windowed=True,
    )

    print(f"\n  Executando PyInstaller (GUI)...\n")
    resultado = subprocess.run(cmd, cwd=PROJECT_DIR)

    if resultado.returncode == 0:
        print(f"\n  Sucesso! Executavel criado em:")
        print(f"     {DIST_DIR / 'YouTube Downloader.exe'}")
    else:
        print(f"\n  Erro durante a compilacao (codigo: {resultado.returncode})")

    return resultado.returncode


def compilar_cli():
    """Compila a versao CLI."""
    print("=" * 60)
    print("  Compilando YouTube Downloader CLI...")
    print("=" * 60)

    cmd = montar_cmd_base(
        nome="YouTube Downloader CLI",
        entry_point=PROJECT_DIR / "yt-downloader.py",
        windowed=False,
    )

    print(f"\n  Executando PyInstaller (CLI)...\n")
    resultado = subprocess.run(cmd, cwd=PROJECT_DIR)

    if resultado.returncode == 0:
        print(f"\n  Sucesso! Executavel criado em:")
        print(f"     {DIST_DIR / 'YouTube Downloader CLI.exe'}")
    else:
        print(f"\n  Erro durante a compilacao (codigo: {resultado.returncode})")

    return resultado.returncode


def main():
    """Funcao principal."""
    versao_pi = obter_versao_pyinstaller()

    print("  " + "=" * 50)
    print("  YouTube Downloader - Build Script")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  PyInstaller: {versao_pi}")
    print("  " + "=" * 50)
    print()

    # Verifica PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("  Erro: PyInstaller nao instalado!")
        print("  Instale com: pip install pyinstaller")
        sys.exit(1)

    # Verifica argumentos
    modo = "gui"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--cli", "-c"):
            modo = "cli"
        elif arg in ("--both", "-b"):
            modo = "both"

    # Limpa build anterior
    limpar_cache()
    print()

    # Compila
    if modo in ("gui", "both"):
        code = compilar_gui()
        if code != 0:
            sys.exit(code)

    if modo in ("cli", "both"):
        code = compilar_cli()
        if code != 0:
            sys.exit(code)

    print()
    print("  " + "=" * 50)
    print("  Build concluido!")
    print(f"  Pasta de saida: {DIST_DIR}")
    print("  " + "=" * 50)


if __name__ == "__main__":
    main()
