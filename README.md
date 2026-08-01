# 📺 YouTube Downloader

Baixe vídeos e áudios do YouTube e de dezenas de outras plataformas (TikTok, Instagram, Twitter/X, Facebook, Twitch, Vimeo, Dailymotion, Reddit, LinkedIn, SoundCloud, Pinterest, Bilibili, Bandcamp, VK, Rumble, Mixcloud, Niconico, TED, Streamable, Kick, Archive.org, Tumblr, OK.ru, PeerTube e outras) com qualidade total — de graça.

## ✨ Funcionalidades

- 🎬 **Vídeo** em MP4, WEBM ou MKV (até 4K)
- 🎵 **Áudio** MP3 (320kbps) com thumbnail e metadados embutidos
- 🔎 **Pesquisa integrada** no YouTube direto do programa
- 📋 **Fila de downloads** com reordenação e re-tentar
- 📜 **Histórico** com busca, re-download e limpeza
- 🏷️ **Legendas** (.srt) em vários idiomas, inclusive auto-geradas
- 🍪 **Cookies do navegador** para vídeos com restrição de idade/login
- 📂 **Playlists** completas ou com intervalo (início/fim)
- 🖼️ **Thumbnails** exibidas na interface
- 🖱️ **Drag & drop** de URLs direto para a janela (Windows)
- 🔔 **Notificações** nativas do Windows ao concluir
- 🚀 **Atualização do yt-dlp** em um clique (menu/CLI)
- 🖥️ **Interface gráfica** (Tkinter) e **CLI** (terminal colorido)
- 📦 **Instalador** e executável .exe (PyInstaller + Inno Setup)

## 🚀 Como usar

### Interface gráfica (recomendada)

```bash
python yt-downloader-gui.py
```

Ou, no Windows, basta dar dois cliques em **`YouTube Downloader.bat`**.

### Linha de comando

```bash
python yt-downloader.py                  # menu interativo
python yt-downloader.py "URL"            # download direto (mp4)
python yt-downloader.py "URL" mp3        # download direto (mp3)
```

## 📦 Instalação

Requisitos: **Python 3.9+**

```bash
pip install -r requirements.txt
```

O programa usa o executável **yt-dlp** e **ffmpeg**:
- **yt-dlp**: `pip install yt-dlp` (ou use o botão "Atualizar" do programa, que instala sozinho)
- **ffmpeg** (Windows): `winget install ffmpeg` ou baixe em [ffmpeg.org](https://ffmpeg.org/download.html)

> Dica: se o `yt-dlp` não estiver no PATH, o programa usa automaticamente `python -m yt_dlp`.

## 🗂️ Onde ficam os arquivos

| Item | Local |
|---|---|
| Downloads padrão | `~/Downloads/YouTube Downloads` |
| Configurações e histórico | `~/.youtube-downloader/config.json` |

## 🏗️ Gerar o executável (.exe)

```bash
python build_exe.py          # GUI
python build_exe.py --cli    # CLI
python build_exe.py --both   # os dois
```

O instalador é criado com o **Inno Setup** (`installer.iss`), que já inclui ícone, atalhos e desinstalação.

## 🧪 Testes

Testes unitários dos módulos `downloader.py` (motor compartilhado), `download_queue_manager.py` (fila), `updater.py` (atualização) e do servidor de atualizações, usando `unittest`:

```bash
python -m unittest discover -s tests -t . -v
```

## 🧰 Estrutura do projeto

| Arquivo | Descrição |
|---|---|
| `yt-downloader-gui.py` | Interface gráfica (Tkinter) |
| `yt-downloader.py` | Versão CLI interativa |
| `downloader.py` | **Motor compartilhado** (comandos yt-dlp, formatos, atualização) |
| `platforms.py` | Detecção de plataformas por URL |
| `config_manager.py` | Configurações e histórico persistentes |
| `download_queue_manager.py` | Fila de downloads (threads) |
| `drop_handler.py` | Drag & drop nativo do Windows (COM) |
| `gerar_icone.py` | Gera o ícone multi-resolução |
| `build_exe.py` | Script de build (PyInstaller) |
| `updater.py` | **Sistema de atualização** (cliente) — consulta o servidor e instala novas versões |
| `publish_release.py` | Publica novas versões no servidor de atualizações |
| `server/` | Servidor FastAPI de atualizações (deploy na Render) |
| `render.yaml` | Blueprint da Render para o servidor de atualizações |

## 🔄 Sistema de atualizações (servidor na Render)

O app possui um **servidor de atualizações** que informa quando existe uma nova versão, exibe as notas e permite **baixar e instalar** o novo instalador direto do app.

### Arquitetura

- **Servidor** (`server/`): API FastAPI que publica o *manifest* de versões (JSON) com a versão mais recente, notas e links dos instaladores por plataforma.
- **Binários (.exe)**: hospedados no **GitHub Releases** (CDN grátis e confiável). O servidor na Render só guarda os *links* — no plano grátis o disco é efêmero, então **não** envie os .exe para o servidor.
- **Cliente** (`updater.py`): módulo do app que consulta o servidor, compara versões, baixa o instalador, valida o SHA-256 e executa a instalação.

> ⚠️ **Plano free da Render — persistência do manifest**: no plano grátis o filesystem é efêmero (dados somem a cada redeploy, restart ou spin-down). Por isso o `server/releases.json` **versionado no repositório** é a fonte durável do manifest: o `publish_release.py` atualiza esse arquivo localmente e faz **commit + push** (com `render.yaml` usando `autoDeploy: true`, a Render redeploya sozinha e restaura o manifest). Se preferir, use `--no-commit` para pular apenas o git.

### 0. Preparar o repositório (se ainda não existir)

1. Crie um repositório no GitHub (público ou privado).
2. Suba o projeto:

```bash
git init
git add .
git commit -m "Inicial"
git branch -M main
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main
```

### 1. Deploy do servidor na Render

1. Em [render.com](https://render.com): **New → Blueprint** → selecione o repositório (a Render lê o `render.yaml`).
   - Ou **New → Web Service**: environment **Python 3**, build `pip install -r server/requirements.txt`, start `uvicorn server.app:app --host 0.0.0.0 --port $PORT`.
2. A Render gera um **ADMIN_TOKEN** automaticamente (variável de ambiente) — guarde-o.
3. Anote a URL do serviço (ex.: `https://seu-app.onrender.com`).

### 2. Configurar o app

A URL do servidor é resolvida nesta ordem de precedência:

1. **Variável de ambiente `UPDATE_URL`** (útil no build/empacotamento)
2. **`config.json` do usuário** → chave `update_url`
3. **Padrão no código** → `UPDATE_URL` em `updater.py` (troque aqui pela URL definitiva ao publicar)

> Placeholders antigos (`https://SEU-SERVIDOR.onrender.com`) salvos no `config.json` são
> tratados como "não configurado" e caem automaticamente no padrão atual.

Para configurar via `config.json`, edite `~/.youtube-downloader/config.json` (formato real do arquivo):

```json
{
  "config": {
    "update_url": "https://seu-app.onrender.com",
    "update_check_auto": true
  },
  "history": []
}
```

O app passa a verificar atualizações ao iniciar e mostra o botão **"Verificar Atualização"** no cabeçalho.

### 3. Publicar uma nova versão

#### 🔥 Pipeline completa (recomendado)

Com **um único comando** você faz o build (PyInstaller), gera o instalador (Inno Setup), cria o GitHub Release com o `.exe` e publica no servidor:

```bash
python release.py --version 1.1.0 \
    --notes "Correções de bugs e melhorias" \
    --repo usuario/repo \
    --server https://seu-app.onrender.com
```

Tokens (por flag ou variável de ambiente):
- GitHub: `--github-token` ou `GH_TOKEN`/`GITHUB_TOKEN`
- Servidor: `--token` ou `PUBLISH_TOKEN`

Flags de controle:
- `--skip-build` / `--skip-installer` — reutiliza `dist/` e `installer/` existentes
- `--skip-github` — não cria GitHub Release (útil para publicar via `publish_release.py` manualmente depois)
- `--skip-publish` — não publica no servidor
- `--no-commit` — não faz commit/push do `server/releases.json` (por padrão o manifest é commitado e enviado, persistindo no plano free)
- `--dry-run` — mostra tudo o que seria executado, sem fazer nada

> Para rodar apenas a parte manual (sem GitHub), use `--skip-github --skip-publish` e depois `python publish_release.py --windows-url <link> ...` com os mesmos `--version`/`--token`/`--server`.

> O `installer.iss` aceita a versão via `/DMyAppVersion=1.1.0`, e o `release.py` cuida disso automaticamente.

#### Manual (passo a passo)

1. Gere o instalador: `python build_exe.py` + Inno Setup (`installer.iss`).
2. Suba o `.exe` como asset de um **GitHub Release** (ex.: tag `v1.1.0`).
3. Copie o link direto do asset e publique no servidor:

```bash
python publish_release.py \
    --version 1.1.0 \
    --notes "Correções de bugs e melhorias" \
    --windows-url "https://github.com/user/repo/releases/download/v1.1.0/YouTube-Downloader-Setup-1.1.0.exe" \
    --release-page "https://github.com/user/repo/releases/tag/v1.1.0" \
    --server https://seu-app.onrender.com \
    --token SEU-ADMIN-TOKEN
```

> Dica: use `--windows-sha256` (ou aponte `--windows-url` para um arquivo local) para que o app valide a integridade do download. Se preferir, salve o token na variável `PUBLISH_TOKEN`.

> A publicação também grava a versão em `server/releases.json` no repositório local e faz **commit + push** (a Render redeploya sozinha e restaura o manifest — necessário no plano free). Para pular o git, use `--no-commit`.

### Endpoints do servidor

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/latest` | GET | Manifest da versão mais recente |
| `/api/releases` | GET | Lista de todas as versões |
| `/api/update/check?current_version=1.0&platform=windows` | GET | Consulta usada pelo app |
| `/api/releases` | POST | Registra versão (requer `Authorization: Bearer <ADMIN_TOKEN>`) |

---

## ⚠️ Aviso legal

Baixe apenas conteúdo que você tem direito de usar. Respeite os direitos autorais e os termos de serviço de cada plataforma.
