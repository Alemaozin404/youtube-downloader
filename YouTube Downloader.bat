@echo off
title YouTube Downloader v1.2.0

:: Configura o console para UTF-8 (suporte a acentos e caracteres especiais)
chcp 65001 > nul

:: Vai para a pasta onde o .bat esta localizado
cd /d "%~dp0"

:: Limpa a tela
cls

:: Exibe cabecalho
echo.
echo  +======================================+
echo  ^|     YouTube Downloader v1.2.0        ^|
echo  ^|  Baixe videos e audios do YouTube!   ^|
echo  +======================================+
echo.

:: ========= Tenta executar versao compilada (.exe) primeiro =========
if exist "dist\YouTube Downloader.exe" (
    echo  Iniciando versao compilada GUI...
    echo.
    start "" /B /WAIT "dist\YouTube Downloader.exe"
    if %errorlevel% equ 0 exit /b 0
    echo  [AVISO] Versao GUI falhou (codigo: %errorlevel%). Tentando fallback...
    echo.
)

if exist "dist\YouTube Downloader CLI.exe" (
    echo  Iniciando versao compilada CLI...
    echo.
    start "" /B /WAIT "dist\YouTube Downloader CLI.exe"
    if %errorlevel% equ 0 exit /b 0
    echo  [AVISO] Versao CLI falhou (codigo: %errorlevel%). Tentando fallback...
    echo.
)

:: ========= Fallback: executa via Python =========
:: Verifica se o Python esta instalado
where python > nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRO] Python nao encontrado!
    echo  Instale Python em: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Verifica se o script existe
if not exist "yt-downloader.py" (
    echo  [ERRO] Arquivo yt-downloader.py nao encontrado!
    echo  Certifique-se de que o arquivo esta na mesma pasta que este .bat
    echo.
    pause
    exit /b 1
)

:: Executa o downloader
echo Iniciando o programa via Python...
echo.
python yt-downloader.py

:: Se houve erro, pausa para o usuario ver
if %errorlevel% neq 0 (
    echo.
    echo  [ERRO] O programa foi encerrado com erro (codigo: %errorlevel%)
    echo  Pressione Enter para fechar...
    pause > nul
)
