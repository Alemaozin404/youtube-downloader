#!/usr/bin/env python3
"""
YouTube Downloader GUI v1.3.0
Interface grafica para baixar videos e audios do YouTube.
"""

import os
import sys
import re
import json
import base64
import tempfile
import atexit
import subprocess
import threading
import queue
from pathlib import Path
from datetime import datetime
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from typing import Optional
import urllib.request
import io

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config_manager import get_config
from download_queue_manager import DownloadQueueManager, QueueItem, STATUS_PENDING
from platforms import (
    detectar_plataforma, validar_url,
    nome_plataforma, cor_plataforma, get_platform_ids,
    formatos_para_plataforma, qualidades_para_plataforma,
)

# Suporte a arrastar e soltar (drag & drop) - Windows nativo
if sys.platform == "win32":
    try:
        from drop_handler import DropHandler
        HAS_DROP_HANDLER = True
    except ImportError:
        HAS_DROP_HANDLER = False
else:
    HAS_DROP_HANDLER = False

# Motor compartilhado de downloads (tambem usado pelo CLI)
from downloader import (
    formatar_duracao,
    montar_comando_download,
    atualizar_ytdlp,
    localizar_ytdlp,
    verificar_ytdlp,
    verificar_ffmpeg,
    NAVEGADORES_COOKIES,
)

# Sistema de atualizacao automatica do app
from updater import (
    APP_VERSION,
    plataforma_atual,
    verificar_atualizacao,
    baixar_instalador,
    verificar_sha256,
    executar_instalador,
    caminho_instalador_temp,
    AtualizacaoInfo,
)

# ─── Configurar encoding para UTF-8 no Windows ──────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    os.system("chcp 65001 > nul 2>&1")


# ─── Configuracao de tema e cores ───────────────────────────────────────────
COR_PRIMARIA = "#e74c3c"       # Vermelho YouTube
COR_PRIMARIA2 = "#c0392b"       # Vermelho escuro
COR_SECUNDARIA = "#3498db"      # Azul
COR_FUNDO = "#1a1a2e"           # Azul escuro (fundo)
COR_FUNDO2 = "#16213e"          # Azul medio
COR_CARD = "#0f3460"            # Azul card
COR_TEXTO = "#ecf0f1"           # Texto claro
COR_TEXTO2 = "#95a5a6"          # Texto secundario
COR_SUCESSO = "#2ecc71"         # Verde
COR_AVISO = "#f39c12"           # Laranja
COR_ERRO = "#e74c3c"            # Vermelho
COR_PROGRESSO = "#e74c3c"       # Barra progresso
COR_PROGRESSO_BG = "#34495e"    # Fundo barra progresso

# ─── Cores de navegacao ──────────────────────────────────────────────────────
COR_NAV_FUNDO = "#101024"      # Fundo da barra de navegacao
COR_NAV_ATIVO = "#e74c3c"      # Aba ativa
COR_NAV_HOVER = "#2a2a4a"      # Hover da aba




# =============================================================================
# CLASSE PRINCIPAL - YouTube Downloader GUI
# =============================================================================

class YouTubeDownloaderGUI:
    """Interface grafica para download de videos do YouTube."""

    def __init__(self, root: Tk):
        self.root = root
        self.root.title(f"YouTube Downloader v{APP_VERSION}")
        self.root.configure(bg=COR_FUNDO)

        # ─── Carrega configuracoes persistentes ───────────────────────────
        self.config = get_config()
        self._carregando_config = True  # Evita salvar durante carregamento inicial

        # ─── Define o icone da janela ────────────────────────────────────────
        self.definir_icone()

        # ─── Janela responsiva ─────────────────────────────────────────────
        geo_largura = self.config.get("janela_largura", 850)
        geo_altura = self.config.get("janela_altura", 700)
        self.root.minsize(780, 620)
        self.root.geometry(f"{geo_largura}x{geo_altura}")

        # Centralizar na tela
        self.centralizar_janela()

        # ─── Variaveis de estado ───────────────────────────────────────────
        self.info_video: Optional[dict] = None
        self.diretorio_saida = self.config.get_diretorio()
        self.diretorio_saida.mkdir(parents=True, exist_ok=True)
        self.download_em_andamento = False
        self.processando = False
        self._atualizando_ytdlp = False
        self.fila_log = queue.Queue()

        # ─── Thumbnail ────────────────────────────────────────────────────
        self.thumbnail_img: Optional[object] = None  # ImageTk.PhotoImage
        self.thumbnail_url: str = ""
        self._aviso_pillow: bool = False

        # ─── Fila de downloads ────────────────────────────────────────────
        self.fila_manager = DownloadQueueManager()
        self.fila_manager.set_on_status_change(self._atualizar_indicador_fila)
        self.fila_manager.set_on_queue_complete(self._fila_concluida)

        # ─── Drag & Drop (Windows nativo) ─────────────────────────────────
        self.drop_handler: Optional[object] = None  # DropHandler instance
        self.label_drop_zone: Optional[Label] = None
        self._url_card: Optional[Frame] = None  # Card URL para destaque drag
        self._drop_wrapper: Optional[Frame] = None  # Wrapper ao redor do card
        self._drop_canvas: Optional[Canvas] = None  # Canvas para borda pontilhada
        self._dashed_rect_id: Optional[int] = None  # ID do retangulo no Canvas

        # ─── Constroi a interface ──────────────────────────────────────────
        self.construir_interface()

        # ─── Aplica configuracoes salvas aos widgets ──────────────────────
        self.aplicar_config_salva()

        # ─── Fim do carregamento de config ───────────────────────────────
        self._carregando_config = False

        # ─── Inicia verificacao da fila de log ────────────────────────────
        self.verificar_fila_log()

        # ─── Verifica ambiente ao iniciar ─────────────────────────────────
        self.root.after(500, self.verificar_ambiente)

        # ─── Verifica atualizacoes do app ao iniciar ─────────────────────
        self.root.after(1500, self.verificar_atualizacao_app)

        # ─── Inicializa drag & drop (Windows) ────────────────────────────
        self.root.after(100, self._iniciar_drop_handler)

        # ─── Atalhos de teclado ───────────────────────────────────────────
        self.root.bind("<Control-d>", lambda e: self.mostrar_pagina("download"))
        self.root.bind("<Control-f>", lambda e: self._focar_pesquisa())
        self.root.bind("<Control-Return>", lambda e: self.iniciar_download())
        self.root.bind("<Control-l>", lambda e: self.limpar_tudo())

        # ─── Salva config ao fechar ───────────────────────────────────────
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ─── Icone embutido em base64 ──────────────────────────────────────────
    ICONE_BASE64 = (
        "AAABAAEAICAAAAEAIAD8AAAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAAgAAAAIAgGAAAA"
        "c3p69AAAAMNJREFUeJzd18ENgCAMBVDmYAg5eXD/EZzBOTQeTEwtbSktVZtw5T+qEEjp"
        "i5XztGMjJNQdAyfelpkcppCWYArSFY5NvpaCDgpiEl4L5iBNCCxcGkxBRAgu/CxXBATA"
        "ya7SIkiApPX3Mu8Ct3oI0CJIAPfjYaXtQvPqawAN4tGFXoAU4QqQIP4NCP0EJlsxdBu+"
        "5iAKPYolXdCEi1Yv7UJPuNmdwDWcQgy7knGIIZdSiAi5lmOI4Q8TCjLsadaCcQ31qgP8"
        "1QDX0wI2OAAAAABJRU5ErkJggg=="
    )

    def definir_icone(self):
        """Define o icone da janela usando dados embutidos em base64."""
        try:
            dados = base64.b64decode(self.ICONE_BASE64)
            # Salva em arquivo temporario (deleta=False para poder usar o caminho)
            with tempfile.NamedTemporaryFile(suffix='.ico', delete=False) as f:
                f.write(dados)
                caminho_temp = f.name
            self.root.iconbitmap(caminho_temp)
            # Limpa o arquivo temporario quando o programa encerrar
            atexit.register(self._limpar_icone_temp, caminho_temp)
        except Exception:
            pass  # Se falhar, continua sem icone

    @staticmethod
    def _limpar_icone_temp(caminho: str):
        """Remove o arquivo temporario do icone (chamado no exit)."""
        try:
            if os.path.exists(caminho):
                os.unlink(caminho)
        except Exception:
            pass

    def centralizar_janela(self):
        """Centraliza a janela na tela."""
        self.root.update_idletasks()
        largura = self.root.winfo_width()
        altura = self.root.winfo_height()
        if largura < 100:
            largura = 850
            altura = 700
        x = (self.root.winfo_screenwidth() // 2) - (largura // 2)
        y = (self.root.winfo_screenheight() // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

    # =========================================================================
    # CONSTRUCAO DA INTERFACE
    # =========================================================================

    def construir_interface(self):
        """Constroi todos os elementos da interface."""
        self.configurar_estilos()
        self.criar_cabecalho()
        self.criar_nav()
        self.criar_paginas()
        self.aplicar_bordas_cards()
        self.mostrar_pagina("download")

    def configurar_estilos(self):
        """Configura estilos ttk para a interface."""
        style = ttk.Style()
        style.theme_use("clam")

        # Estilos personalizados
        style.configure("TFrame", background=COR_FUNDO)
        style.configure("Card.TFrame", background=COR_CARD, relief="flat")
        style.configure("Header.TLabel",
                        background=COR_FUNDO,
                        foreground=COR_TEXTO,
                        font=("Segoe UI", 14, "bold"))
        style.configure("Subtitle.TLabel",
                        background=COR_FUNDO,
                        foreground=COR_TEXTO2,
                        font=("Segoe UI", 9))
        style.configure("Info.TLabel",
                        background=COR_CARD,
                        foreground=COR_TEXTO,
                        font=("Segoe UI", 10))
        style.configure("Status.TLabel",
                        background=COR_CARD,
                        foreground=COR_TEXTO2,
                        font=("Segoe UI", 9))
        style.configure("Value.TLabel",
                        background=COR_CARD,
                        foreground=COR_SECUNDARIA,
                        font=("Segoe UI", 10, "bold"))

        # Botao primario (vermelho YouTube)
        style.configure("Primary.TButton",
                        background=COR_PRIMARIA,
                        foreground="white",
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0,
                        padding=10)
        style.map("Primary.TButton",
                  background=[("active", COR_PRIMARIA2), ("disabled", "#7f8c8d")])

        # Botao secundario
        style.configure("Secondary.TButton",
                        background=COR_SECUNDARIA,
                        foreground="white",
                        font=("Segoe UI", 9),
                        borderwidth=0,
                        padding=8)
        style.map("Secondary.TButton",
                  background=[("active", "#2980b9"), ("disabled", "#7f8c8d")])

        # Botao de sucesso (verde)
        style.configure("Success.TButton",
                        background=COR_SUCESSO,
                        foreground="white",
                        font=("Segoe UI", 12, "bold"),
                        borderwidth=0,
                        padding=12)
        style.map("Success.TButton",
                  background=[("active", "#27ae60"), ("disabled", "#7f8c8d")])

        # Progressbar
        style.configure("Custom.Horizontal.TProgressbar",
                        background=COR_PROGRESSO,
                        troughcolor=COR_PROGRESSO_BG,
                        bordercolor=COR_PROGRESSO_BG,
                        lightcolor=COR_PROGRESSO,
                        darkcolor=COR_PROGRESSO,
                        thickness=20)

        # Entrada de texto
        style.configure("Custom.TEntry",
                        fieldbackground=COR_FUNDO2,
                        foreground=COR_TEXTO,
                        bordercolor=COR_CARD,
                        lightcolor=COR_CARD,
                        darkcolor=COR_CARD,
                        padding=8)

        # Combobox
        style.configure("Custom.TCombobox",
                        fieldbackground=COR_FUNDO2,
                        foreground=COR_TEXTO,
                        background=COR_CARD,
                        arrowcolor=COR_TEXTO,
                        padding=5)
        style.map("Custom.TCombobox",
                  fieldbackground=[("readonly", COR_FUNDO2)],
                  foreground=[("readonly", COR_TEXTO)])

        # LabelFrame
        style.configure("Custom.TLabelframe",
                        background=COR_CARD,
                        foreground=COR_TEXTO,
                        relief="flat",
                        bordercolor="#1a3a6a")
        style.configure("Custom.TLabelframe.Label",
                        background=COR_CARD,
                        foreground=COR_TEXTO,
                        font=("Segoe UI", 9, "bold"))

    # ─── CABECALHO ──────────────────────────────────────────────────────────

    def criar_cabecalho(self):
        """Cria o cabecalho com titulo e descricao."""
        header = Frame(self.root, bg=COR_FUNDO2, height=70)
        header.pack(fill=X, pady=(0, 10))
        header.pack_propagate(False)

        # Barra vermelha decorativa
        barra = Frame(header, bg=COR_PRIMARIA, height=4)
        barra.pack(fill=X, side=BOTTOM)

        # Conteudo do cabecalho
        conteudo = Frame(header, bg=COR_FUNDO2)
        conteudo.pack(expand=True, fill=BOTH, padx=20)

        Label(conteudo,
              text="YouTube Downloader",
              bg=COR_FUNDO2,
              fg=COR_TEXTO,
              font=("Segoe UI", 18, "bold")).pack(side=LEFT, anchor="w")

        Label(conteudo,
              text=f"v{APP_VERSION}",
              bg=COR_FUNDO2,
              fg=COR_TEXTO2,
              font=("Segoe UI", 10)).pack(side=LEFT, padx=(8, 0), anchor="w")

        Button(conteudo,
               text="Verificar Atualizacao",
               command=self.verificar_atualizacao_app,
               bg=COR_FUNDO2,
               fg=COR_SECUNDARIA,
               font=("Segoe UI", 8, "bold"),
               relief="flat",
               bd=0,
               padx=8,
               pady=4,
               cursor="hand2",
               activebackground=COR_PRIMARIA,
               activeforeground="white").pack(side=RIGHT, padx=(0, 10))

        Label(conteudo,
              text="Baixe videos e audios do YouTube com qualidade!",
              bg=COR_FUNDO2,
              fg=COR_TEXTO2,
              font=("Segoe UI", 10)).pack(side=RIGHT, anchor="e")

    # ─── NAVEGACAO (abas) ───────────────────────────────────────────────────

    def criar_nav(self):
        """Cria a barra de navegacao com as abas principais."""
        self.frame_nav = Frame(self.root, bg=COR_NAV_FUNDO)
        self.frame_nav.pack(fill=X, pady=(0, 10))

        self.botoes_nav = {}
        # Texto puro (sem emoji) para garantir renderizacao em qualquer Windows
        itens = [
            ("download", "[ Download ]"),
            ("pesquisar", "[ Pesquisar ]"),
            ("fila", "[ Fila ]"),
            ("historico", "[ Historico ]"),
            ("sobre", "[ Sobre ]"),
        ]

        for chave, texto in itens:
            btn = Button(
                self.frame_nav,
                text=texto,
                command=lambda c=chave: self._acao_nav(c),
                bg=COR_NAV_FUNDO,
                fg=COR_TEXTO2,
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                bd=0,
                padx=12,
                pady=6,
                cursor="hand2",
                activebackground=COR_NAV_HOVER,
                activeforeground="white",
            )
            btn.pack(side=LEFT, padx=(0, 6))
            self.botoes_nav[chave] = btn

    def _acao_nav(self, chave: str):
        """Acao ao clicar em uma aba da navegacao."""
        if chave == "fila":
            self.abrir_fila()
        elif chave == "historico":
            self.abrir_historico()
        else:
            self.mostrar_pagina(chave)

    def criar_paginas(self):
        """Cria o container de paginas e constroi cada uma."""
        self.container_paginas = Frame(self.root, bg=COR_FUNDO)
        self.container_paginas.pack(fill=BOTH, expand=True)

        self.paginas = {}

        # ─── Pagina Download ──────────────────────────────────────────────
        self.pagina_download = Frame(self.container_paginas, bg=COR_FUNDO)
        self.paginas["download"] = self.pagina_download

        # ─── Pagina Pesquisar ─────────────────────────────────────────────
        self.pagina_pesquisa = Frame(self.container_paginas, bg=COR_FUNDO)
        self.paginas["pesquisar"] = self.pagina_pesquisa

        # ─── Pagina Sobre ─────────────────────────────────────────────────
        self.pagina_sobre = Frame(self.container_paginas, bg=COR_FUNDO)
        self.paginas["sobre"] = self.pagina_sobre

        # Constroi o conteudo de cada pagina
        self.criar_frame_url()
        self.criar_pesquisa_youtube()
        self.criar_frame_info()
        self.criar_frame_opcoes()
        self.criar_frame_download()
        self.criar_frame_log()
        self.criar_pagina_sobre()

    def mostrar_pagina(self, nome: str):
        """Mostra a pagina indicada e oculta as demais."""
        for chave, pagina in self.paginas.items():
            if chave == nome:
                pagina.pack(fill=BOTH, expand=True)
            else:
                pagina.pack_forget()

        # Atualiza o estilo das abas
        for chave, btn in self.botoes_nav.items():
            if chave == nome:
                btn.config(bg=COR_NAV_ATIVO, fg="white")
            else:
                btn.config(bg=COR_NAV_FUNDO, fg=COR_TEXTO2)

        # Status do ambiente sempre fresco ao abrir a pagina Sobre
        if nome == "sobre":
            self._atualizar_status_sobre()

    def _focar_pesquisa(self):
        """Foca o campo de pesquisa e abre a pagina."""
        self.mostrar_pagina("pesquisar")
        self.entry_pesquisa.focus_set()

    # ─── FRAME URL ──────────────────────────────────────────────────────────

    def criar_frame_url(self):
        """Cria o frame com campo de URL e botoes."""
        frame = Frame(self.pagina_download, bg=COR_FUNDO)
        frame.pack(fill=X, padx=15, pady=(0, 10))

        # ─── Wrapper para borda pontilhada de drag & drop ────────────────
        self._drop_wrapper = Frame(frame, bg=COR_CARD, highlightthickness=0, bd=0)
        self._drop_wrapper.pack(fill=X)

        # Canvas para desenhar a borda pontilhada (sobreposta ao card)
        self._drop_canvas = Canvas(
            self._drop_wrapper,
            bg=COR_CARD,
            highlightthickness=0,
            bd=0
        )
        self._drop_canvas.place(relwidth=1, relheight=1)
        # `lower()` de Canvas e comando de item (exige tagOrId); usar nivel de widget:
        self._drop_canvas.tk.call('lower', self._drop_canvas._w)  # Fica atras do card
        self._dashed_rect_id = None

        # Redesenha a borda pontilhada quando a janela redimensionar
        self._drop_wrapper.bind("<Configure>", self._redraw_drop_border)

        # Card
        card = Frame(self._drop_wrapper, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=X, padx=0, pady=0)
        self.aplicar_borda_card(card)
        self._url_card = card

        conteudo = Frame(card, bg=COR_CARD)
        conteudo.pack(fill=X, padx=15, pady=12)

        # ─── Linha de rotulos: Plataforma + URL ────────────────────────────
        linha_rotulos = Frame(conteudo, bg=COR_CARD)
        linha_rotulos.pack(fill=X)

        Label(linha_rotulos,
              text="Plataforma:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              anchor="w").pack(side=LEFT, padx=(0, 8))

        self.plataforma_var = StringVar(value="youtube")
        self.combo_plataforma = ttk.Combobox(linha_rotulos,
                                              textvariable=self.plataforma_var,
                                              values=get_platform_ids(),
                                              state="readonly",
                                              width=14,
                                              style="Custom.TCombobox")
        self.combo_plataforma.pack(side=LEFT, padx=(0, 10))
        self.combo_plataforma.bind("<<ComboboxSelected>>", self._ao_mudar_plataforma)

        self.label_plataforma_detectada = Label(
            linha_rotulos,
            text="",
            bg=COR_CARD,
            fg=COR_TEXTO2,
            font=("Segoe UI", 9)
        )
        self.label_plataforma_detectada.pack(side=LEFT)

        # ─── Label URL ────────────────────────────────────────────────────
        Label(conteudo,
              text="URL:",
              bg=COR_CARD,
              fg=COR_TEXTO,
              font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 0))

        # Linha: entrada URL + botoes
        linha_url = Frame(conteudo, bg=COR_CARD)
        linha_url.pack(fill=X, pady=(6, 0))

        self.entry_url = Entry(linha_url,
                               bg=COR_FUNDO2,
                               fg=COR_TEXTO,
                               insertbackground=COR_TEXTO,
                               font=("Segoe UI", 11),
                               relief="flat",
                               bd=0,
                               highlightthickness=1,
                               highlightbackground=COR_CARD,
                               highlightcolor=COR_SECUNDARIA)
        self.entry_url.pack(side=LEFT, fill=X, expand=True, ipady=8, padx=(0, 8))
        self.entry_url.bind("<Return>", lambda e: self.buscar_info())
        self.entry_url.bind("<Control-v>", lambda e: self.root.after(10, self.buscar_info_auto))
        self.entry_url.bind("<Button-3>", self.menu_contexto_url)
        self.entry_url.bind("<KeyRelease>", self._detectar_plataforma_auto)

        # ─── Indicador de drop zone ───────────────────────────────────────
        self.label_drop_zone = Label(
            linha_url,
            text="",
            bg=COR_CARD,
            fg=COR_TEXTO2,
            font=("Segoe UI", 8),
            padx=6
        )
        self.label_drop_zone.pack(side=LEFT, padx=(0, 2))

        # Botoes
        btn_buscar = Button(linha_url,
                            text="Buscar",
                            command=self.buscar_info,
                            bg=COR_SECUNDARIA,
                            fg="white",
                            font=("Segoe UI", 9, "bold"),
                            relief="flat",
                            bd=0,
                            padx=12,
                            pady=8,
                            cursor="hand2",
                            activebackground="#2980b9",
                            activeforeground="white")
        btn_buscar.pack(side=LEFT, padx=(0, 4))

        btn_add_fila = Button(linha_url,
                              text="+ Fila",
                              command=self.adicionar_fila,
                              bg=COR_SECUNDARIA,
                              fg="white",
                              font=("Segoe UI", 9, "bold"),
                              relief="flat",
                              bd=0,
                              padx=10,
                              pady=8,
                              cursor="hand2",
                              activebackground="#2980b9",
                              activeforeground="white")
        btn_add_fila.pack(side=LEFT, padx=(0, 4))

        # Indicador da fila (mostra quantos itens)
        self.label_fila_count = Label(
            linha_url,
            text="",
            bg=COR_CARD,
            fg=COR_TEXTO2,
            font=("Segoe UI", 9),
            cursor="hand2"
        )
        self.label_fila_count.pack(side=LEFT, padx=(0, 4))
        self.label_fila_count.bind("<Button-1>", lambda e: self.abrir_fila())

        btn_fila = Button(linha_url,
                          text="Fila",
                          command=self.abrir_fila,
                          bg=COR_CARD,
                          fg=COR_TEXTO,
                          font=("Segoe UI", 9),
                          relief="flat",
                          bd=0,
                          padx=10,
                          pady=8,
                          cursor="hand2",
                          activebackground=COR_SECUNDARIA,
                          activeforeground="white")
        btn_fila.pack(side=LEFT, padx=(0, 4))

        btn_historico = Button(linha_url,
                               text="Historico",
                               command=self.abrir_historico,
                               bg=COR_CARD,
                               fg=COR_TEXTO,
                               font=("Segoe UI", 9),
                               relief="flat",
                               bd=0,
                               padx=10,
                               pady=8,
                               cursor="hand2",
                               activebackground=COR_SECUNDARIA,
                               activeforeground="white")
        btn_historico.pack(side=LEFT, padx=(0, 4))

        btn_limpar = Button(linha_url,
                            text="Limpar",
                            command=self.limpar_tudo,
                            bg="#7f8c8d",
                            fg="white",
                            font=("Segoe UI", 9),
                            relief="flat",
                            bd=0,
                            padx=10,
                            pady=8,
                            cursor="hand2",
                            activebackground="#95a5a6",
                            activeforeground="white")
        btn_limpar.pack(side=LEFT)

        btn_atualizar = Button(linha_url,
                               text="Atualizar",
                               command=self.atualizar_ytdlp,
                               bg="#8e44ad",
                               fg="white",
                               font=("Segoe UI", 9),
                               relief="flat",
                               bd=0,
                               padx=10,
                               pady=8,
                               cursor="hand2",
                               activebackground="#9b59b6",
                               activeforeground="white")
        btn_atualizar.pack(side=LEFT, padx=(4, 0))

    def _detectar_plataforma_auto(self, event=None):
        """Detecta automaticamente a plataforma ao digitar a URL."""
        url = self.entry_url.get().strip()
        if not url:
            self.label_plataforma_detectada.config(text="")
            return

        plat = detectar_plataforma(url)
        if plat:
            self.label_plataforma_detectada.config(
                text=f"Detectado: {plat['nome']}",
                fg=plat["cor"]
            )
            self.plataforma_var.set(plat["id"])
            self._adaptar_opcoes_por_plataforma(plat["id"])
        else:
            self.label_plataforma_detectada.config(
                text="URL nao reconhecida",
                fg=COR_ERRO
            )

    def _ao_mudar_plataforma(self, event=None):
        """Chamado quando o usuario seleciona manualmente a plataforma."""
        plat_id = self.plataforma_var.get()
        self._adaptar_opcoes_por_plataforma(plat_id)
        # Atualiza o label de deteccao se estiver em branco
        if not self.label_plataforma_detectada.cget("text"):
            self.label_plataforma_detectada.config(
                text=f"Manual: {nome_plataforma(plat_id)}",
                fg=cor_plataforma(plat_id)
            )

    def _adaptar_opcoes_por_plataforma(self, platform_id: str):
        """Adapta as opcoes de formato e qualidade para a plataforma."""
        formatos_disp = formatos_para_plataforma(platform_id)
        qualidades_disp = qualidades_para_plataforma(platform_id)

        # Habilita/desabilita formatos de acordo com a plataforma
        formato_atual = self.formato_var.get()
        if formato_atual not in formatos_disp:
            self.formato_var.set(formatos_disp[0])

        for child in self._frame_formatos.winfo_children():
            if isinstance(child, Radiobutton):
                valor = child.cget("value")
                estado = "normal" if valor in formatos_disp else "disabled"
                child.config(state=estado)

        # Adapta a combo de qualidade
        QUAL_LABELS = [
            "Melhor disponivel", "4K (2160p)", "2K (1440p)",
            "Full HD (1080p)", "HD (720p)", "SD (480p)", "SD (360p)"
        ]
        qual_compat = []
        for ql in QUAL_LABELS:
            if any(res in ql or (res == "best" and "Melhor" in ql) for res in qualidades_disp):
                qual_compat.append(ql)

        # Se a qualidade atual nao e suportada, muda para padrao
        qual_atual = self.qualidade_var.get()
        if qual_atual not in qual_compat:
            self.qualidade_var.set(qual_compat[0] if qual_compat else "Melhor disponivel")

    def menu_contexto_url(self, event):
        """Menu de contexto para o campo URL."""
        menu = Menu(self.root, tearoff=0, bg=COR_FUNDO2, fg=COR_TEXTO,
                    activebackground=COR_SECUNDARIA, activeforeground="white")
        menu.add_command(label="Colar", command=lambda: self.entry_url.event_generate("<<Paste>>"))
        menu.add_command(label="Limpar", command=lambda: self.entry_url.delete(0, END))
        menu.post(event.x_root, event.y_root)

    def buscar_info_auto(self):
        """Tenta buscar informacoes automaticamente apos colar."""
        self.root.after(300, self.buscar_info)

    # ─── PESQUISA INTEGRADA ─────────────────────────────────────────────────

    def criar_pesquisa_youtube(self):
        """Constroi a pagina de pesquisa do YouTube com resultados inline."""
        # ─── Card de busca ────────────────────────────────────────────────
        card = Frame(self.pagina_pesquisa, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=X, padx=15, pady=(0, 10))
        self.aplicar_borda_card(card)

        conteudo = Frame(card, bg=COR_CARD)
        conteudo.pack(fill=X, padx=15, pady=10)

        # Linha 1: Rotulo + campo de busca
        linha_busca = Frame(conteudo, bg=COR_CARD)
        linha_busca.pack(fill=X)

        Label(linha_busca,
              text="Pesquisar no YouTube:",
              bg=COR_CARD,
              fg=COR_TEXTO,
              font=("Segoe UI", 9, "bold")).pack(side=LEFT, padx=(0, 8))

        self.entry_pesquisa = Entry(linha_busca,
                                     bg=COR_FUNDO2,
                                     fg=COR_TEXTO,
                                     insertbackground=COR_TEXTO,
                                     font=("Segoe UI", 10),
                                     relief="flat",
                                     bd=0,
                                     highlightthickness=1,
                                     highlightbackground=COR_CARD,
                                     highlightcolor=COR_PRIMARIA)
        self.entry_pesquisa.pack(side=LEFT, fill=X, expand=True, ipady=6, padx=(0, 6))
        self.entry_pesquisa.bind("<Return>", lambda e: self.pesquisar_youtube())

        self.btn_pesquisar = Button(linha_busca,
                                     text="Pesquisar",
                                     command=self.pesquisar_youtube,
                                     bg=COR_PRIMARIA,
                                     fg="white",
                                     font=("Segoe UI", 9, "bold"),
                                     relief="flat",
                                     bd=0,
                                     padx=12,
                                     pady=6,
                                     cursor="hand2",
                                     activebackground=COR_PRIMARIA2,
                                     activeforeground="white")
        self.btn_pesquisar.pack(side=LEFT)

        Label(conteudo,
              text="Digite o que deseja buscar. Ex: 'musica relaxante 2024' ou 'curso python'",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        # ─── Card de resultados (inline) ──────────────────────────────────
        card_res = Frame(self.pagina_pesquisa, bg=COR_CARD, relief="flat", bd=0)
        card_res.pack(fill=BOTH, expand=True, padx=15, pady=(0, 15))
        self.aplicar_borda_card(card_res)

        conteudo_res = Frame(card_res, bg=COR_CARD)
        conteudo_res.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.label_resultado_total = Label(conteudo_res,
                                           text="",
                                           bg=COR_CARD,
                                           fg=COR_TEXTO2,
                                           font=("Segoe UI", 9, "bold"))
        self.label_resultado_total.pack(anchor="w", pady=(0, 6))

        frame_lista = Frame(conteudo_res, bg=COR_FUNDO2, bd=0,
                            highlightthickness=1, highlightbackground=COR_CARD)
        frame_lista.pack(fill=BOTH, expand=True)

        self.canvas_resultados = Canvas(frame_lista, bg=COR_FUNDO2, highlightthickness=0)
        scroll = Scrollbar(frame_lista, orient=VERTICAL, command=self.canvas_resultados.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.canvas_resultados.pack(side=LEFT, fill=BOTH, expand=True)
        self.canvas_resultados.configure(yscrollcommand=scroll.set)

        self.frame_resultados = Frame(self.canvas_resultados, bg=COR_FUNDO2)
        self._resultados_window_id = self.canvas_resultados.create_window(
            (0, 0), window=self.frame_resultados, anchor="nw")

        def _config_scroll(event):
            self.canvas_resultados.configure(
                scrollregion=self.canvas_resultados.bbox("all"))
            self.canvas_resultados.itemconfig(
                self._resultados_window_id,
                width=self.canvas_resultados.winfo_width())

        self.frame_resultados.bind("<Configure>", _config_scroll)

    def pesquisar_youtube(self):
        """Executa pesquisa no YouTube via yt-dlp e mostra resultados."""
        query = self.entry_pesquisa.get().strip()
        if not query:
            messagebox.showinfo("Pesquisa vazia", "Digite algo para pesquisar no YouTube.")
            return

        self.btn_pesquisar.config(text="Buscando...", state="disabled", bg="#7f8c8d")
        self.adicionar_log(f"Pesquisando: {query[:60]}...", COR_SECUNDARIA)

        thread = threading.Thread(target=self._pesquisar_thread, args=(query,), daemon=True)
        thread.start()

    def _pesquisar_thread(self, query: str):
        """Thread para executar pesquisa sem travar a UI."""
        try:
            # yt-dlp ytsearchN:query --dump-json --flat-playlist --no-warnings
            cmd = localizar_ytdlp() + [
                "--dump-json",
                "--flat-playlist",
                "--no-warnings",
                "--default-search", "ytsearch",
                "--playlist-end", "15",
                query
            ]

            resultado = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            if resultado.returncode != 0:
                erro = resultado.stderr.strip()
                self.adicionar_log(f"Erro na pesquisa: {erro[:100]}", COR_ERRO)
                self.root.after(0, self._restaurar_botao_pesquisa)
                return

            linhas = resultado.stdout.strip().split("\n")
            if not linhas or not linhas[0]:
                self.adicionar_log("Nenhum resultado encontrado.", COR_AVISO)
                self.root.after(0, self._restaurar_botao_pesquisa)
                return

            resultados = []
            for linha in linhas:
                if linha.strip():
                    try:
                        info = json.loads(linha)
                        resultados.append(info)
                    except json.JSONDecodeError:
                        continue

            self.root.after(0, lambda: self._mostrar_resultados_pesquisa(resultados))

        except subprocess.TimeoutExpired:
            self.adicionar_log("Pesquisa excedeu o tempo limite.", COR_ERRO)
            self.root.after(0, self._restaurar_botao_pesquisa)
        except Exception as e:
            self.adicionar_log(f"Erro na pesquisa: {e}", COR_ERRO)
            self.root.after(0, self._restaurar_botao_pesquisa)

    def _restaurar_botao_pesquisa(self):
        """Restaura o botao de pesquisa ao estado normal."""
        self.btn_pesquisar.config(text="Pesquisar", state="normal",
                                  bg=COR_PRIMARIA, activebackground=COR_PRIMARIA2)

    def _mostrar_resultados_pesquisa(self, resultados: list):
        """Exibe os resultados da pesquisa na propria pagina (inline)."""
        self._restaurar_botao_pesquisa()

        if not resultados:
            messagebox.showinfo("Pesquisa", "Nenhum resultado encontrado.")
            return

        self.adicionar_log(f"Encontrados {len(resultados)} resultados.", COR_SUCESSO)

        # Garante que a pagina de pesquisa esteja visivel
        self.mostrar_pagina("pesquisar")

        # Limpa resultados anteriores
        for w in self.frame_resultados.winfo_children():
            w.destroy()

        self.label_resultado_total.config(
            text=f"{len(resultados)} videos encontrados")

        # Cria itens da lista
        for i, info in enumerate(resultados):
            self._criar_item_resultado(self.frame_resultados, info, i)

    def _criar_item_resultado(self, parent, info: dict, index: int):
        """Cria um item visual na lista de resultados."""
        item = Frame(parent, bg=COR_FUNDO2, relief="flat", bd=0,
                     highlightthickness=1, highlightbackground=COR_CARD)
        item.pack(fill=X, padx=5, pady=2)

        # Extrai informacoes
        titulo = info.get("title", "Sem titulo")
        url = info.get("url", info.get("webpage_url", ""))
        autor = info.get("uploader", info.get("channel", ""))
        duracao = info.get("duration", 0)
        views = info.get("view_count", 0)
        thumbnail = info.get("thumbnail", "")

        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"

        def _carregar_video(e=None):
            if url:
                self.entry_url.delete(0, END)
                self.entry_url.insert(0, url)
                self.mostrar_pagina("download")
                self.buscar_info()

        item.bind("<Button-1>", _carregar_video)
        item.config(cursor="hand2")

        # Numero + Titulo
        linha1 = Frame(item, bg=COR_FUNDO2)
        linha1.pack(fill=X, padx=8, pady=(4, 0))

        Label(linha1,
              text=f"{index + 1}.",
              bg=COR_FUNDO2,
              fg=COR_PRIMARIA,
              font=("Segoe UI", 10, "bold"),
              width=3).pack(side=LEFT, anchor="n")

        lbl_titulo = Label(linha1,
                           text=titulo[:70] + ("..." if len(titulo) > 70 else ""),
                           bg=COR_FUNDO2,
                           fg=COR_TEXTO,
                           font=("Segoe UI", 10, "bold"),
                           anchor="w",
                           cursor="hand2")
        lbl_titulo.pack(side=LEFT, fill=X, expand=True)
        lbl_titulo.bind("<Button-1>", _carregar_video)

        # Detalhes
        linha2 = Frame(item, bg=COR_FUNDO2)
        linha2.pack(fill=X, padx=8, pady=(0, 4))

        # Autor
        if autor:
            Label(linha2,
                  text=autor[:40],
                  bg=COR_FUNDO2,
                  fg=COR_SECUNDARIA,
                  font=("Segoe UI", 8)).pack(side=LEFT, padx=(0, 10))

        # Duracao
        if duracao:
            Label(linha2,
                  text=formatar_duracao(duracao),
                  bg=COR_FUNDO2,
                  fg=COR_TEXTO2,
                  font=("Segoe UI", 8)).pack(side=LEFT, padx=(0, 10))

        # Views (so mostra se tiver valor)
        if views and views > 0:
            Label(linha2,
                  text=f"{views:,} visualizacoes",
                  bg=COR_FUNDO2,
                  fg=COR_TEXTO2,
                  font=("Segoe UI", 8)).pack(side=LEFT, padx=(0, 10))

        # Separador
        Frame(item, bg=COR_CARD, height=1).pack(fill=X)

    # ─── FRAME INFORMACOES DO VIDEO ─────────────────────────────────────────

    def criar_frame_info(self):
        """Cria o frame com informacoes do video e thumbnail."""
        self.frame_info = Frame(self.pagina_download, bg=COR_FUNDO)
        self.frame_info.pack(fill=X, padx=15, pady=(0, 10))

        card = Frame(self.frame_info, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=X)
        self._card_info = card  # Salva para aplicar borda depois

        self.info_conteudo = Frame(card, bg=COR_CARD)
        self.info_conteudo.pack(fill=X, padx=15, pady=12)

        # ─── Layout horizontal: thumbnail (esquerda) + info (direita) ────
        self.info_layout = Frame(self.info_conteudo, bg=COR_CARD)
        self.info_layout.pack(fill=X)

        # ─── Lado esquerdo: Thumbnail ─────────────────────────────────────
        self.frame_thumbnail = Frame(self.info_layout, bg=COR_FUNDO2,
                                     width=320, height=180, relief="flat",
                                     highlightthickness=1,
                                     highlightbackground=COR_CARD)
        self.frame_thumbnail.pack(side=LEFT, padx=(0, 15))
        self.frame_thumbnail.pack_propagate(False)

        # Label para a imagem da thumbnail (inicialmente oculto)
        self.label_thumbnail = Label(
            self.frame_thumbnail,
            text="",
            bg=COR_FUNDO2,
            relief="flat"
        )

        # Placeholder da thumbnail (icone de video placeholder)
        self.label_placeholder_thumb = Label(
            self.frame_thumbnail,
            text="",
            bg=COR_FUNDO2
        )
        self.label_placeholder_thumb.pack(fill=BOTH, expand=True)

        # ─── Lado direito: Informações do video ───────────────────────────
        self.frame_info_texto = Frame(self.info_layout, bg=COR_CARD)
        self.frame_info_texto.pack(side=LEFT, fill=X, expand=True)

        # Placeholder para informacoes
        self.label_placeholder = Label(
            self.frame_info_texto,
            text="Cole uma URL do YouTube e clique em 'Buscar Informacoes'",
            bg=COR_CARD,
            fg=COR_TEXTO2,
            font=("Segoe UI", 11),
            pady=20
        )
        self.label_placeholder.pack()

        # Labels de informacao (inicialmente ocultos)
        self.info_widgets = {}
        self.criar_labels_info()

    def criar_labels_info(self):
        """Cria os labels para exibir informacoes do video (inicialmente ocultos)."""
        campos = [
            ("titulo", "Titulo:"),
            ("autor", "Autor:"),
            ("duracao", "Duracao:"),
            ("visualizacoes", "Visualizacoes:"),
            ("data", "Publicado em:"),
        ]

        self.info_frames = {}
        for chave, rotulo in campos:
            # Frame contenedor (mantido p/ pack/forget sem deixar espacos vazios)
            frame = Frame(self.frame_info_texto, bg=COR_CARD)
            self.info_frames[chave] = frame

            # Valor exibido
            label_valor = Label(frame,
                                text="",
                                bg=COR_CARD,
                                fg=COR_TEXTO,
                                font=("Segoe UI", 10),
                                anchor="w",
                                wraplength=500,
                                justify=LEFT)
            label_valor.pack(fill=X)

            self.info_widgets[chave] = label_valor

        # Tornar os widgets invisiveis inicialmente
        self.mostrar_ocultar_info(False)

    def mostrar_ocultar_info(self, mostrar: bool):
        """Mostra ou oculta os labels de informacao e thumbnail."""
        for chave, widget in self.info_widgets.items():
            frame = self.info_frames.get(chave)
            if mostrar:
                frame.pack(fill=X, pady=2)
                widget.pack(fill=X)
            else:
                widget.pack_forget()
                frame.pack_forget()

        if mostrar:
            self.label_placeholder.pack_forget()
            self.label_placeholder_thumb.pack_forget()
            self.label_thumbnail.pack(fill=BOTH, expand=True)
            # Ajusta altura do frame thumbnail
            self.frame_thumbnail.config(height=180)
        else:
            self.label_thumbnail.pack_forget()
            self.label_placeholder_thumb.pack(fill=BOTH, expand=True)
            self.label_placeholder.pack()

    def carregar_thumbnail(self, thumbnail_url: str):
        """Download e exibe a thumbnail do video em thread separada."""
        if not thumbnail_url:
            return

        self.thumbnail_url = thumbnail_url

        def _download():
            try:
                if not HAS_PIL:
                    if not self._aviso_pillow:
                        self._aviso_pillow = True
                        self.adicionar_log(
                            "Pillow nao instalado. Instale com: pip install pillow",
                            COR_AVISO
                        )
                    return

                response = urllib.request.urlopen(thumbnail_url, timeout=10)
                image_data = response.read()
                pil_image = Image.open(io.BytesIO(image_data))

                # Redimensiona mantendo proporcao (max 320x180)
                pil_image.thumbnail((320, 180), Image.LANCZOS)

                photo = ImageTk.PhotoImage(pil_image)
                self.thumbnail_img = photo  # Mantem referencia viva

                self.root.after(0, lambda: self.label_thumbnail.config(image=photo))

            except Exception:
                pass  # Falha silenciosa na thumbnail

        thread = threading.Thread(target=_download, daemon=True)
        thread.start()

    def remover_thumbnail(self):
        """Remove a thumbnail exibida."""
        self.thumbnail_img = None
        self.thumbnail_url = ""
        self.label_thumbnail.config(image="")

    def atualizar_info_video(self, info: dict):
        """Atualiza os labels e thumbnail com as informacoes do video."""
        if not info:
            return

        self.info_video = info

        # Carrega thumbnail do video
        thumb_url = info.get("thumbnail", "")
        self.carregar_thumbnail(thumb_url)

        if info.get("is_playlist"):
            titulo = info.get("playlist_title", "N/A")
            total = info.get("playlist_count", 0)
            self.info_widgets["titulo"].config(
                text=f"Titulo: {titulo}  ({'Playlist'})",
                fg=COR_AVISO
            )
            self.info_widgets["autor"].config(text=f"Total de videos: {total}")
            self.info_widgets["duracao"].config(text="")
            self.info_widgets["visualizacoes"].config(text="")
            self.info_widgets["data"].config(text="")
        else:
            duracao = formatar_duracao(info.get("duration", 0))
            views = f"{info.get('view_count', 0):,}"
            upload_date = info.get("upload_date", "")
            if upload_date and len(upload_date) == 8:
                upload_date = f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[:4]}"

            self.info_widgets["titulo"].config(
                text=f"Titulo: {info.get('title', 'N/A')}",
                fg=COR_TEXTO
            )
            self.info_widgets["autor"].config(text=f"Autor: {info.get('uploader', 'N/A')}")
            self.info_widgets["duracao"].config(text=f"Duracao: {duracao}")
            self.info_widgets["visualizacoes"].config(text=f"Visualizacoes: {views}")
            self.info_widgets["data"].config(text=f"Publicado em: {upload_date or 'N/A'}")

        self.mostrar_ocultar_info(True)

    # ─── FRAME OPCOES DE DOWNLOAD ───────────────────────────────────────────

    def criar_frame_opcoes(self):
        """Cria o frame com opcoes de formato, qualidade e diretorio."""
        frame = Frame(self.pagina_download, bg=COR_FUNDO)
        frame.pack(fill=X, padx=15, pady=(0, 10))

        card = Frame(frame, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=X)
        self._card_opcoes = card  # Salva para aplicar borda depois

        conteudo = Frame(card, bg=COR_CARD)
        conteudo.pack(fill=X, padx=15, pady=12)

        # ─── Titulo da secao ───────────────────────────────────────────────
        Label(conteudo,
              text="Opcoes de Download",
              bg=COR_CARD,
              fg=COR_TEXTO,
              font=("Segoe UI", 11, "bold")).pack(anchor="w")

        # ─── Linha 1: Formato ──────────────────────────────────────────────
        linha1 = Frame(conteudo, bg=COR_CARD)
        linha1.pack(fill=X, pady=(10, 5))

        Label(linha1,
              text="Formato:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              width=12,
              anchor="w").pack(side=LEFT)

        self.formato_var = StringVar(value="mp4")
        self._frame_formatos = linha1
        formatos = [("MP4 (Recomendado)", "mp4"),
                    ("MP3 (Audio apenas)", "mp3"),
                    ("WEBM", "webm"),
                    ("MKV", "mkv")]

        for texto, valor in formatos:
            rb = Radiobutton(linha1,
                             text=texto,
                             variable=self.formato_var,
                             value=valor,
                             bg=COR_CARD,
                             fg=COR_TEXTO,
                             selectcolor=COR_FUNDO2,
                             activebackground=COR_CARD,
                             activeforeground=COR_TEXTO,
                             font=("Segoe UI", 9),
                             cursor="hand2",
                             command=self.on_formato_change)
            rb.pack(side=LEFT, padx=(0, 15))

        # ─── Linha 2: Qualidade + Diretorio ────────────────────────────────
        linha2 = Frame(conteudo, bg=COR_CARD)
        linha2.pack(fill=X, pady=(5, 5))

        Label(linha2,
              text="Qualidade:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              width=12,
              anchor="w").pack(side=LEFT)

        self.qualidade_var = StringVar(value="best")
        self.combo_qualidade = ttk.Combobox(linha2,
                                            textvariable=self.qualidade_var,
                                            values=[
                                                "Melhor disponivel",
                                                "4K (2160p)",
                                                "2K (1440p)",
                                                "Full HD (1080p)",
                                                "HD (720p)",
                                                "SD (480p)",
                                                "SD (360p)"
                                            ],
                                            state="readonly",
                                            width=22,
                                            style="Custom.TCombobox")
        self.combo_qualidade.pack(side=LEFT, padx=(0, 20))

        # Mapeamento qualidade -> formato yt-dlp
        self.qualidade_map = {
            "Melhor disponivel": "best",
            "4K (2160p)": "2160p",
            "2K (1440p)": "1440p",
            "Full HD (1080p)": "1080p",
            "HD (720p)": "720p",
            "SD (480p)": "480p",
            "SD (360p)": "360p",
        }

        # ─── Diretorio ─────────────────────────────────────────────────────
        Label(linha2,
              text="Salvar em:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              anchor="w").pack(side=LEFT, padx=(0, 8))

        self.diretorio_var = StringVar(value=str(self.diretorio_saida))

        entry_dir = Entry(linha2,
                          textvariable=self.diretorio_var,
                          bg=COR_FUNDO2,
                          fg=COR_TEXTO,
                          insertbackground=COR_TEXTO,
                          font=("Segoe UI", 9),
                          relief="flat",
                          bd=0,
                          highlightthickness=1,
                          highlightbackground=COR_CARD)
        entry_dir.pack(side=LEFT, fill=X, expand=True, ipady=5, padx=(0, 5))

        btn_dir = Button(linha2,
                         text="...",
                         command=self.escolher_diretorio,
                         bg="#7f8c8d",
                         fg="white",
                         font=("Segoe UI", 9, "bold"),
                         relief="flat",
                         bd=0,
                         width=3,
                         pady=3,
                         cursor="hand2",
                         activebackground="#95a5a6",
                         activeforeground="white")
        btn_dir.pack(side=LEFT)

        # ─── Linha 3: Opcoes extras ────────────────────────────────────────
        linha3 = Frame(conteudo, bg=COR_CARD)
        linha3.pack(fill=X, pady=(5, 0))

        self.playlist_var = BooleanVar(value=False)
        self.check_playlist = Checkbutton(linha3,
                                          text="Esta URL e uma playlist",
                                          variable=self.playlist_var,
                                          bg=COR_CARD,
                                          fg=COR_TEXTO,
                                          selectcolor=COR_FUNDO2,
                                          activebackground=COR_CARD,
                                          activeforeground=COR_TEXTO,
                                          font=("Segoe UI", 9),
                                          cursor="hand2",
                                          command=self.on_playlist_change)
        self.check_playlist.pack(side=LEFT, padx=(12, 10))

        # Intervalo playlist (inicialmente desabilitado)
        Label(linha3,
              text="Intervalo:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 5))

        self.playlist_inicio_var = StringVar(value="")
        self.entry_playlist_inicio = Entry(linha3,
                                           textvariable=self.playlist_inicio_var,
                                           bg=COR_FUNDO2,
                                           fg=COR_TEXTO,
                                           insertbackground=COR_TEXTO,
                                           font=("Segoe UI", 9),
                                           relief="flat",
                                           bd=0,
                                           highlightthickness=1,
                                           highlightbackground=COR_CARD,
                                           width=5,
                                           state="disabled")
        self.entry_playlist_inicio.pack(side=LEFT, ipady=4, padx=(0, 3))

        Label(linha3,
              text="a",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 3))

        self.playlist_fim_var = StringVar(value="")
        self.entry_playlist_fim = Entry(linha3,
                                        textvariable=self.playlist_fim_var,
                                        bg=COR_FUNDO2,
                                        fg=COR_TEXTO,
                                        insertbackground=COR_TEXTO,
                                        font=("Segoe UI", 9),
                                        relief="flat",
                                        bd=0,
                                        highlightthickness=1,
                                        highlightbackground=COR_CARD,
                                        width=5,
                                        state="disabled")
        self.entry_playlist_fim.pack(side=LEFT, ipady=4)

        Label(linha3,
              text="(deixe em branco para todos)",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 8)).pack(side=LEFT, padx=(8, 0))

        # ─── Linha 4: Legendas ────────────────────────────────────────────────
        linha4 = Frame(conteudo, bg=COR_CARD)
        linha4.pack(fill=X, pady=(8, 0))

        # Separador visual
        Frame(conteudo, bg=COR_TEXTO2, height=1).pack(fill=X, pady=(8, 6))

        Label(linha4,
              text="Legendas:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              width=12,
              anchor="w").pack(side=LEFT)

        self.subs_var = BooleanVar(value=False)
        Checkbutton(linha4,
                    text="Baixar legendas (.srt)",
                    variable=self.subs_var,
                    bg=COR_CARD,
                    fg=COR_TEXTO,
                    selectcolor=COR_FUNDO2,
                    activebackground=COR_CARD,
                    activeforeground=COR_TEXTO,
                    font=("Segoe UI", 9),
                    cursor="hand2",
                    command=self.on_subtitle_change).pack(side=LEFT, padx=(0, 8))

        self.subs_auto_var = BooleanVar(value=False)
        self.check_sub_auto = Checkbutton(linha4,
                    text="Auto-geradas",
                    variable=self.subs_auto_var,
                    bg=COR_CARD,
                    fg=COR_TEXTO,
                    selectcolor=COR_FUNDO2,
                    activebackground=COR_CARD,
                    activeforeground=COR_TEXTO,
                    font=("Segoe UI", 9),
                    cursor="hand2",
                    state="disabled")
        self.check_sub_auto.pack(side=LEFT, padx=(0, 10))

        Label(linha4,
              text="Idioma:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 5))

        self.subs_idiomas = [
            ("Portugues (BR)", "pt"),
            ("English", "en"),
            ("Espanol", "es"),
            ("Francais", "fr"),
            ("Deutsch", "de"),
            ("Italiano", "it"),
            ("Portugues (PT)", "pt-PT"),
        ]

        self.subs_lang_var = StringVar(value="Portugues (BR)")
        self.combo_sub_idioma = ttk.Combobox(linha4,
                                              textvariable=self.subs_lang_var,
                                              values=[l[0] for l in self.subs_idiomas],
                                              state="disabled",
                                              width=16,
                                              style="Custom.TCombobox")
        self.combo_sub_idioma.pack(side=LEFT)

        # ─── Linha 5: Cookies ────────────────────────────────────────────────
        linha5 = Frame(conteudo, bg=COR_CARD)
        linha5.pack(fill=X, pady=(8, 0))

        # Separador visual
        Frame(conteudo, bg=COR_TEXTO2, height=1).pack(fill=X, pady=(8, 6))

        Label(linha5,
              text="Cookies:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              width=12,
              anchor="w").pack(side=LEFT)

        self.cookies_var = BooleanVar(value=False)
        Checkbutton(linha5,
                    text="Usar cookies do navegador",
                    variable=self.cookies_var,
                    bg=COR_CARD,
                    fg=COR_TEXTO,
                    selectcolor=COR_FUNDO2,
                    activebackground=COR_CARD,
                    activeforeground=COR_TEXTO,
                    font=("Segoe UI", 9),
                    cursor="hand2",
                    command=self.on_cookies_change).pack(side=LEFT, padx=(0, 8))

        Label(linha5,
              text="Navegador:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 5))

        self.cookies_nav_var = StringVar(value="chrome")
        self.combo_cookies = ttk.Combobox(linha5,
                                           textvariable=self.cookies_nav_var,
                                           values=NAVEGADORES_COOKIES,
                                           state="disabled",
                                           width=14,
                                           style="Custom.TCombobox")
        self.combo_cookies.pack(side=LEFT)

    def on_cookies_change(self):
        """Habilita/desabilita combo de navegador e salva config."""
        estado = "normal" if self.cookies_var.get() else "disabled"
        self.combo_cookies.config(state=estado)
        if not self._carregando_config:
            self.config.set_multiplas(
                cookies_habilitado=self.cookies_var.get(),
                cookies_navegador=self.cookies_nav_var.get(),
            )

    def on_formato_change(self):
        """Atualiza interface quando o formato muda e salva config."""
        is_mp3 = self.formato_var.get() == "mp3"
        self.combo_qualidade.config(state="readonly" if not is_mp3 else "disabled")
        if is_mp3:
            self.qualidade_var.set("Melhor disponivel")
        if not self._carregando_config:
            self.config.set("ultimo_formato", self.formato_var.get())

    def on_subtitle_change(self):
        """Atualiza interface quando opcao de legendas muda e salva config."""
        estado = "normal" if self.subs_var.get() else "disabled"
        self.combo_sub_idioma.config(state=estado)
        self.check_sub_auto.config(state=estado)
        if not self._carregando_config:
            self.config.set_multiplas(
                subs_habilitado=self.subs_var.get(),
                subs_auto=self.subs_auto_var.get(),
                subs_idioma=self.subs_lang_var.get(),
            )

    def on_playlist_change(self):
        """Atualiza campos de intervalo de playlist."""
        estado = "normal" if self.playlist_var.get() else "disabled"
        self.entry_playlist_inicio.config(state=estado)
        self.entry_playlist_fim.config(state=estado)

    def escolher_diretorio(self):
        """Abre dialogo para escolher diretorio de saida e salva config."""
        diretorio = filedialog.askdirectory(
            title="Escolher pasta de destino",
            initialdir=str(self.diretorio_saida)
        )
        if diretorio:
            self.diretorio_saida = Path(diretorio)
            self.diretorio_var.set(str(diretorio))
            self.config.set_diretorio(diretorio)

    # ─── FILA DE DOWNLOADS ────────────────────────────────────────────────

    def adicionar_fila(self):
        """Adiciona URL atual com as configuracoes atuais a fila de downloads."""
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("URL vazia", "Por favor, cole uma URL.")
            return

        if not url.startswith("http"):
            if re.match(r"^[\w-]{11}$", url):
                url = f"https://www.youtube.com/watch?v={url}"
            else:
                url = f"https://{url}"
            self.entry_url.delete(0, END)
            self.entry_url.insert(0, url)

        if not validar_url(url):
            messagebox.showwarning("URL invalida", "A URL informada nao parece ser suportada pelo yt-dlp.")
            return

        # Captura configuracoes atuais
        formato = self.formato_var.get()
        qual_label = self.qualidade_var.get()

        playlist_start = None
        playlist_end = None
        if self.playlist_var.get():
            inicio = self.playlist_inicio_var.get().strip()
            fim = self.playlist_fim_var.get().strip()
            playlist_start = int(inicio) if inicio.isdigit() else None
            playlist_end = int(fim) if fim.isdigit() else None

        subs_idioma = "pt"
        for nome, codigo in self.subs_idiomas:
            if nome == self.subs_lang_var.get():
                subs_idioma = codigo
                break

        item = QueueItem(
            url=url,
            formato=formato,
            qualidade=qual_label,
            diretorio=str(self.diretorio_saida),
            playlist=self.playlist_var.get(),
            playlist_start=playlist_start,
            playlist_end=playlist_end,
            subs=self.subs_var.get(),
            subs_auto=self.subs_auto_var.get(),
            subs_idioma=subs_idioma,
            cookies=self.cookies_nav_var.get() if self.cookies_var.get() else None,
        )

        self.fila_manager.add(item)
        self.adicionar_log(f"Adicionado a fila: {url[:50]}...", COR_SECUNDARIA)

        # Se nao estiver processando nada, pergunta se quer iniciar a fila
        if not self.fila_manager.is_processing and not self.download_em_andamento:
            if self.fila_manager.total_count() >= 1:
                self.iniciar_download()

    def abrir_fila(self):
        """Abre janela de gerenciamento da fila de downloads."""
        items = self.fila_manager.get_items()

        win = Toplevel(self.root)
        win.title("Fila de Downloads")
        win.configure(bg=COR_FUNDO)
        win.minsize(550, 350)
        win.geometry("600x450")
        win.transient(self.root)
        win.grab_set()

        # ─── Topo ──────────────────────────────────────────────────────────
        frame_top = Frame(win, bg=COR_FUNDO2)
        frame_top.pack(fill=X, padx=10, pady=10)

        Label(frame_top,
              text="Fila de Downloads",
              bg=COR_FUNDO2,
              fg=COR_TEXTO,
              font=("Segoe UI", 14, "bold")).pack(side=LEFT)

        self._fila_label_total = Label(
            frame_top,
            text=f"{len(items)} itens",
            bg=COR_FUNDO2,
            fg=COR_TEXTO2,
            font=("Segoe UI", 9)
        )
        self._fila_label_total.pack(side=LEFT, padx=(10, 0))

        # ─── Botoes de acao ───────────────────────────────────────────────
        frame_botoes = Frame(win, bg=COR_FUNDO)
        frame_botoes.pack(fill=X, padx=10, pady=(0, 10))

        def _processar_fila():
            if not self.fila_manager.is_processing and not self.download_em_andamento:
                self.iniciar_download()
                win.destroy()

        Button(frame_botoes,
               text="Processar Fila",
               command=_processar_fila,
               bg=COR_SUCESSO,
               fg="white",
               font=("Segoe UI", 9, "bold"),
               relief="flat",
               bd=0,
               padx=10,
               pady=6,
               cursor="hand2").pack(side=LEFT, padx=(0, 5))

        def _limpar_fila():
            if messagebox.askyesno("Limpar Fila", "Remover todos os itens pendentes?", parent=win):
                self.fila_manager.clear()
                win.destroy()
                self.adicionar_log("Fila limpa.", COR_AVISO)

        Button(frame_botoes,
               text="Limpar Pendentes",
               command=_limpar_fila,
               bg="#7f8c8d",
               fg="white",
               font=("Segoe UI", 9),
               relief="flat",
               bd=0,
               padx=10,
               pady=6,
               cursor="hand2").pack(side=LEFT, padx=(0, 5))

        # ─── Lista da fila ────────────────────────────────────────────────
        frame_lista = Frame(win, bg=COR_CARD, relief="flat", bd=0)
        frame_lista.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        canvas = Canvas(frame_lista, bg=COR_CARD, highlightthickness=0)
        scroll = Scrollbar(frame_lista, orient=VERTICAL, command=canvas.yview)
        scroll.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        canvas.configure(yscrollcommand=scroll.set)

        frame_itens = Frame(canvas, bg=COR_CARD)
        canvas.create_window((0, 0), window=frame_itens, anchor="nw", width=canvas.winfo_reqwidth)

        def _config_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(1, width=canvas.winfo_width())

        frame_itens.bind("<Configure>", _config_scroll)

        def _popular_fila():
            for w in frame_itens.winfo_children():
                w.destroy()

            itens = self.fila_manager.get_items()
            self._fila_label_total.config(text=f"{len(itens)} itens")

            if not itens:
                Label(frame_itens,
                      text="Fila vazia. Adicione URLs para download.",
                      bg=COR_CARD,
                      fg=COR_TEXTO2,
                      font=("Segoe UI", 11),
                      pady=30).pack()
                return

            for i, item in enumerate(itens):
                self._criar_item_fila(frame_itens, item, i, win, _popular_fila)

        _popular_fila()

    def _criar_item_fila(self, parent, item, index, win, refresh_cb):
        """Cria um item visual na lista da fila."""
        # Cor de fundo baseada no status
        if item.status == "downloading":
            bg = "#1a3a6a"
            fg_status = COR_AVISO
            status_text = "BAIXANDO..."
        elif item.status == "completed":
            bg = "#0a2a1a"
            fg_status = COR_SUCESSO
            status_text = "Concluido"
        elif item.status == "failed":
            bg = "#2a0a0a"
            fg_status = COR_ERRO
            status_text = "Falhou"
        elif item.status == "cancelled":
            bg = COR_FUNDO2
            fg_status = COR_TEXTO2
            status_text = "Cancelado"
        else:
            bg = COR_FUNDO2
            fg_status = COR_SECUNDARIA
            status_text = "Pendente"

        item_frame = Frame(parent, bg=bg, relief="flat", bd=0,
                           highlightthickness=1, highlightbackground=COR_CARD)
        item_frame.pack(fill=X, padx=5, pady=2)

        # Numero / Status
        linha1 = Frame(item_frame, bg=bg)
        linha1.pack(fill=X, padx=8, pady=(4, 0))

        Label(linha1,
              text=f"#{index + 1}",
              bg=bg,
              fg=COR_TEXTO2,
              font=("Segoe UI", 8, "bold")).pack(side=LEFT, padx=(0, 8))

        Label(linha1,
              text=status_text,
              bg=bg,
              fg=fg_status,
              font=("Segoe UI", 8, "bold")).pack(side=LEFT, padx=(0, 8))

        # ─── Botoes de acao ───────────────────────────────────────────────
        btn_frame = Frame(linha1, bg=bg)
        btn_frame.pack(side=RIGHT)

        if item.status == "pending":
            def _remover():
                if not self.fila_manager.remove(index):
                    messagebox.showwarning("Aviso", "Nao e possivel remover um item em andamento.", parent=win)
                refresh_cb()

            def _subir():
                self.fila_manager.move_up(index)
                refresh_cb()

            def _descer():
                self.fila_manager.move_down(index)
                refresh_cb()

            for texto, cmd in [("X", _remover), ("^", _subir), ("v", _descer)]:
                Button(btn_frame,
                       text=texto,
                       command=cmd,
                       bg=COR_CARD,
                       fg=COR_TEXTO,
                       font=("Segoe UI", 7, "bold"),
                       relief="flat",
                       bd=0,
                       width=2,
                       padx=2,
                       pady=1,
                       cursor="hand2").pack(side=LEFT, padx=1)
        elif item.status in ("failed", "cancelled"):
            def _re_tentar():
                if self.fila_manager.retry(index):
                    self.adicionar_log("Item marcado para re-tentar.", COR_SECUNDARIA)
                    # Se a fila estiver ociosa, inicia o processamento automaticamente
                    if not self.fila_manager.is_processing and not self.download_em_andamento:
                        self.root.after(100, self.iniciar_download)
                refresh_cb()

            Button(btn_frame,
                   text="↻ Re-tentar",
                   command=_re_tentar,
                   bg=COR_AVISO,
                   fg="white",
                   font=("Segoe UI", 7, "bold"),
                   relief="flat",
                   bd=0,
                   padx=6,
                   pady=1,
                   cursor="hand2").pack(side=LEFT, padx=1)

        # URL / info
        linha2 = Frame(item_frame, bg=bg)
        linha2.pack(fill=X, padx=8, pady=(0, 4))

        # Trunca URL para exibicao
        url_text = item.url[:65] + ("..." if len(item.url) > 65 else "")
        Label(linha2,
              text=url_text,
              bg=bg,
              fg=COR_TEXTO,
              font=("Segoe UI", 9),
              anchor="w").pack(side=LEFT, fill=X, expand=True)

        Label(linha2,
              text=f"{item.formato.upper()} | {item.qualidade}",
              bg=bg,
              fg=COR_TEXTO2,
              font=("Segoe UI", 8)).pack(side=RIGHT, padx=(5, 0))

    def _atualizar_indicador_fila(self):
        """Atualiza o indicador visual da fila na interface principal."""
        total = self.fila_manager.total_count()
        pendentes = self.fila_manager.get_pending_count()

        if total == 0:
            self.label_fila_count.config(text="")
        elif self.fila_manager.is_processing:
            concluidos = total - pendentes
            self.label_fila_count.config(
                text=f"[{concluidos}/{total}]",
                fg=COR_AVISO
            )
        else:
            self.label_fila_count.config(
                text=f"[{total}]",
                fg=COR_SECUNDARIA
            )

    # ═══════════════════════════════════════════════════════════════════════
    # DRAG & DROP (Windows nativo - OLE IDropTarget)
    # ═══════════════════════════════════════════════════════════════════════

    def _redraw_drop_border(self, event=None):
        """Redesenha a borda pontilhada no Canvas quando a janela redimensiona."""
        if not hasattr(self, '_drop_canvas') or not self._drop_canvas:
            return
        if not self._dashed_rect_id:
            return
        try:
            cw = self._drop_canvas.winfo_width()
            ch = self._drop_canvas.winfo_height()
            if cw > 4 and ch > 4:
                self._drop_canvas.delete(self._dashed_rect_id)
                self._dashed_rect_id = self._drop_canvas.create_rectangle(
                    2, 2, cw - 2, ch - 2,
                    outline=COR_SUCESSO,
                    dash=(4, 3),
                    width=2,
                    fill=""
                )
        except Exception:
            pass

    def _iniciar_drop_handler(self):
        """Inicializa o handler de drag & drop do Windows."""
        if not HAS_DROP_HANDLER:
            return
        if self.drop_handler:
            return

        try:
            hwnd = self.root.winfo_id()
            self.drop_handler = DropHandler(hwnd, self._on_drop_recebido)
            self.adicionar_log("Drag & drop ativado - arraste URLs diretamente para a janela", COR_SUCESSO)
            # Inicia o polling de status do drag
            self._poll_drag_status()
        except Exception as e:
            # Falha silenciosa
            self.drop_handler = None

    def _normalizar_url(self, url: str) -> str:
        """Normaliza uma URL: adiciona https:// se necessario, trata IDs curtos."""
        url = url.strip().strip('"').strip("'")
        if not url:
            return ""
        if not url.startswith("http"):
            if re.match(r"^[\w-]{11}$", url):
                url = f"https://www.youtube.com/watch?v={url}"
            elif url.startswith("www."):
                url = f"https://{url}"
            else:
                url = f"https://{url}"
        return url

    def _adicionar_multiplas_urls_fila(self, urls: list):
        """Adiciona multiplas URLs a fila de downloads com as configuracoes atuais."""
        if not urls:
            return

        # Captura configuracoes atuais (uma vez para todas as URLs)
        formato = self.formato_var.get()
        qual_label = self.qualidade_var.get()
        playlist_start = None
        playlist_end = None
        if self.playlist_var.get():
            inicio = self.playlist_inicio_var.get().strip()
            fim = self.playlist_fim_var.get().strip()
            playlist_start = int(inicio) if inicio.isdigit() else None
            playlist_end = int(fim) if fim.isdigit() else None

        subs_idioma = "pt"
        for nome, codigo in self.subs_idiomas:
            if nome == self.subs_lang_var.get():
                subs_idioma = codigo
                break

        adicionadas = 0
        ignoradas = 0

        for url_raw in urls:
            url = self._normalizar_url(url_raw)
            if not url:
                ignoradas += 1
                continue

            if not validar_url(url):
                ignoradas += 1
                continue

            item = QueueItem(
                url=url,
                formato=formato,
                qualidade=qual_label,
                diretorio=str(self.diretorio_saida),
                playlist=self.playlist_var.get(),
                playlist_start=playlist_start,
                playlist_end=playlist_end,
                subs=self.subs_var.get(),
                subs_auto=self.subs_auto_var.get(),
                subs_idioma=subs_idioma,
                cookies=self.cookies_nav_var.get() if self.cookies_var.get() else None,
            )

            self.fila_manager.add(item)
            adicionadas += 1

        # Log do resultado
        if adicionadas > 0:
            plural = "s" if adicionadas > 1 else ""
            self.adicionar_log(
                f"  ({adicionadas} URL{plural} adicionada{plural} a fila)",
                COR_SUCESSO
            )

        if ignoradas > 0:
            plural_i = "s" if ignoradas > 1 else ""
            self.adicionar_log(
                f"  ({ignoradas} URL{plural_i} ignorada{plural_i} - URL invalida{plural_i})",
                COR_AVISO
            )

        # Inicia processamento se nao estiver rodando
        if adicionadas > 0:
            if not self.fila_manager.is_processing and not self.download_em_andamento:
                if self.fila_manager.total_count() >= 1:
                    self.iniciar_download()

    def _on_drop_recebido(self, dados: str):
        """Callback chamado quando algo e soltado na janela.
        Suporta URLs unicas ou multiplas (separadas por quebra de linha ou ponto e virgula).
        """
        if not dados:
            return

        dados = dados.strip()
        if not dados:
            return

        # Divide o texto em URLs separadas por \n, \r\n, ;
        urls_raw = re.split(r"[\r\n]+|\s*;\s*", dados)
        urls_raw = [u.strip() for u in urls_raw if u.strip()]

        if not urls_raw:
            return

        if len(urls_raw) > 1:
            # Multiplos URLs: adiciona todos a fila de uma vez
            def _processar_multiplas():
                self.adicionar_log(
                    f"Recebidas {len(urls_raw)} URL{'' if len(urls_raw) == 1 else 's'} por drag & drop",
                    COR_SECUNDARIA
                )
                self._adicionar_multiplas_urls_fila(urls_raw)

            self.root.after(0, _processar_multiplas)
        else:
            # URL unica: insere no campo de URL (comportamento atual)
            dados_unica = urls_raw[0]
            parece_url = (
                dados_unica.startswith("http://") or
                dados_unica.startswith("https://") or
                dados_unica.startswith("www.") or
                re.match(r"^[\w-]{11}$", dados_unica)  # ID do YouTube
            )

            def _processar_unica():
                self.entry_url.focus_set()
                self.entry_url.delete(0, END)
                self.entry_url.insert(0, dados_unica)
                self._detectar_plataforma_auto()
                self.adicionar_log("URL recebida por drag & drop", COR_SECUNDARIA)
                if parece_url:
                    self.root.after(300, self.buscar_info)

            self.root.after(0, _processar_unica)

    def _desenhar_borda_pontilhada(self):
        """Desenha a borda pontilhada verde no Canvas do card URL."""
        if not hasattr(self, '_drop_canvas') or not self._drop_canvas:
            return
        try:
            self._drop_canvas.tk.call('raise', self._drop_canvas._w)  # Traz o canvas para frente
            cw = self._drop_canvas.winfo_width()
            ch = self._drop_canvas.winfo_height()
            if cw > 4 and ch > 4:
                # Remove retangulo anterior se existir
                if self._dashed_rect_id:
                    self._drop_canvas.delete(self._dashed_rect_id)
                self._dashed_rect_id = self._drop_canvas.create_rectangle(
                    2, 2, cw - 2, ch - 2,
                    outline=COR_SUCESSO,
                    dash=(5, 3),
                    width=2,
                    fill=""
                )
        except Exception:
            pass

    def _limpar_borda_pontilhada(self):
        """Remove a borda pontilhada do Canvas."""
        if not hasattr(self, '_drop_canvas') or not self._drop_canvas:
            return
        try:
            if self._dashed_rect_id:
                self._drop_canvas.delete(self._dashed_rect_id)
                self._dashed_rect_id = None
            self._drop_canvas.tk.call('lower', self._drop_canvas._w)  # Coloca o canvas atras do card
        except Exception:
            pass

    def _poll_drag_status(self):
        """Verifica periodicamente se um drag esta ativo e atualiza UI."""
        if not self.drop_handler:
            return

        try:
            if self.drop_handler.drag_ativo:
                # Destaca o campo URL durante o drag
                self.entry_url.config(
                    highlightbackground=COR_SUCESSO,
                    highlightcolor=COR_SUCESSO,
                    bg="#1a3a2a"
                )
                self.label_drop_zone.config(
                    text=" Solte aqui ",
                    fg=COR_SUCESSO,
                    bg="#0a2a1a"
                )
                # Borda pontilhada ao redor do card URL inteiro
                self._desenhar_borda_pontilhada()
                # Destaca o card wrapper
                if hasattr(self, '_drop_wrapper') and self._drop_wrapper:
                    self._drop_wrapper.config(
                        highlightthickness=2,
                        highlightbackground=COR_SUCESSO
                    )
            else:
                # Restaura estilo normal
                self.entry_url.config(
                    highlightbackground=COR_CARD,
                    highlightcolor=COR_SECUNDARIA,
                    bg=COR_FUNDO2
                )
                self.label_drop_zone.config(
                    text="",
                    fg=COR_TEXTO2,
                    bg=COR_CARD
                )
                # Remove borda pontilhada
                self._limpar_borda_pontilhada()
                # Restaura card wrapper
                if hasattr(self, '_drop_wrapper') and self._drop_wrapper:
                    self._drop_wrapper.config(
                        highlightthickness=0,
                        highlightbackground=COR_CARD
                    )
        except Exception:
            pass

        # Continua polling (5 vezes por segundo)
        self.root.after(200, self._poll_drag_status)

    def _notificar_windows(self, titulo: str, mensagem: str):
        """Mostra notificacao nativa do Windows (toast) via PowerShell.
        Funciona no Windows 10+ sem dependencias adicionais.
        Falha silenciosamente se o PowerShell nao estiver disponivel.
        """
        if sys.platform != "win32":
            return

        try:
            # Escapa aspas simples para PowerShell
            titulo_esc = titulo.replace("'", "''")
            msg_esc = mensagem.replace("'", "''")

            ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode('{titulo_esc}')) | Out-Null
$textNodes.Item(1).AppendChild($template.CreateTextNode('{msg_esc}')) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::New($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("YouTube Downloader").Show($toast)
'''

            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=10
            )
        except Exception:
            pass  # Falha silenciosa - notificacao nao e critica

    def _fila_concluida(self):
        """Chamado quando toda a fila termina."""
        self.adicionar_log("Fila de downloads concluida!", COR_SUCESSO)

        # Mostra notificacao nativa do Windows
        total = self.fila_manager.total_count()
        completos = sum(1 for i in self.fila_manager.get_items() if i.status == "completed")
        titulo = "YouTube Downloader"
        if total == 1:
            mensagem = "Download concluido com sucesso!"
        else:
            mensagem = f"Fila concluida! {completos} de {total} downloads finalizados."
        self._notificar_windows(titulo, mensagem)

    # ─── HISTORICO ─────────────────────────────────────────────────────────

    def abrir_historico(self):
        """Abre janela com historico de downloads."""
        history = self.config.get_history(100)

        win = Toplevel(self.root)
        win.title("Historico de Downloads")
        win.configure(bg=COR_FUNDO)
        win.minsize(680, 400)
        win.geometry("750x500")

        # Centraliza relativo a janela principal
        win.transient(self.root)
        win.grab_set()

        # ─── Frame de busca ───────────────────────────────────────────────
        frame_top = Frame(win, bg=COR_FUNDO2)
        frame_top.pack(fill=X, padx=10, pady=10)

        Label(frame_top,
              text="Historico de Downloads",
              bg=COR_FUNDO2,
              fg=COR_TEXTO,
              font=("Segoe UI", 14, "bold")).pack(side=LEFT, anchor="w")

        Label(frame_top,
              text=f"{len(history)} registros",
              bg=COR_FUNDO2,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(10, 0))

        # Botao limpar historico
        def _limpar_historico():
            if messagebox.askyesno("Limpar Historico",
                                    "Tem certeza que deseja limpar todo o historico?",
                                    parent=win):
                self.config.clear_history()
                win.destroy()
                self.adicionar_log("Historico limpo.", COR_AVISO)

        btn_limpar_hist = Button(frame_top,
                                  text="Limpar Historico",
                                  command=_limpar_historico,
                                  bg="#7f8c8d",
                                  fg="white",
                                  font=("Segoe UI", 8),
                                  relief="flat",
                                  bd=0,
                                  padx=8,
                                  pady=4,
                                  cursor="hand2")
        btn_limpar_hist.pack(side=RIGHT, padx=(5, 0))

        # ─── Frame de busca ───────────────────────────────────────────────
        frame_busca = Frame(win, bg=COR_FUNDO)
        frame_busca.pack(fill=X, padx=10, pady=(0, 10))

        Label(frame_busca,
              text="Buscar:",
              bg=COR_FUNDO,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 5))

        entry_busca = Entry(frame_busca,
                             bg=COR_FUNDO2,
                             fg=COR_TEXTO,
                             insertbackground=COR_TEXTO,
                             font=("Segoe UI", 10),
                             relief="flat",
                             bd=0,
                             highlightthickness=1,
                             highlightbackground=COR_CARD)
        entry_busca.pack(side=LEFT, fill=X, expand=True, ipady=5)

        # ─── Lista de historico ───────────────────────────────────────────
        frame_lista = Frame(win, bg=COR_CARD, relief="flat", bd=0)
        frame_lista.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        # Canvas + Scrollbar
        canvas = Canvas(frame_lista, bg=COR_CARD, highlightthickness=0)
        scroll = Scrollbar(frame_lista, orient=VERTICAL, command=canvas.yview)
        scroll.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        canvas.configure(yscrollcommand=scroll.set)

        # Frame interno para o conteudo
        frame_itens = Frame(canvas, bg=COR_CARD)
        canvas.create_window((0, 0), window=frame_itens, anchor="nw", width=canvas.winfo_reqwidth)

        def _configurar_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(1, width=canvas.winfo_width())

        frame_itens.bind("<Configure>", _configurar_scroll)

        def _popular_lista(filtro=""):
            # Limpa itens antigos
            for w in frame_itens.winfo_children():
                w.destroy()

            items = self.config.search_history(filtro) if filtro else history

            if not items:
                Label(frame_itens,
                      text=f"{'Nenhum download encontrado.' if filtro else 'Nenhum download no historico.'}",
                      bg=COR_CARD,
                      fg=COR_TEXTO2,
                      font=("Segoe UI", 11),
                      pady=30).pack()
                return

            for i, entry in enumerate(items):
                self._criar_item_historico(frame_itens, entry, i, filtro)

        def _buscar():
            _popular_lista(entry_busca.get().strip())

        entry_busca.bind("<KeyRelease>", lambda e: _buscar())

        # ─── Popula lista inicial ─────────────────────────────────────────
        _popular_lista()

    def _criar_item_historico(self, parent, entry, index, filtro=""):
        """Cria um item visual na lista de historico."""
        item = Frame(parent, bg=COR_FUNDO2, relief="flat", bd=0,
                     highlightthickness=1, highlightbackground=COR_CARD)
        item.pack(fill=X, padx=5, pady=2)

        # Bind de clique para carregar URL
        def _ao_clicar(e=None):
            url = entry.get("url", "")
            if url:
                self.entry_url.delete(0, END)
                self.entry_url.insert(0, url)
                self.buscar_info()
                parent.winfo_toplevel().destroy()

        item.bind("<Button-1>", _ao_clicar)

        # Info do item
        titulo = entry.get("titulo", "Desconhecido")
        info_text = f"{entry.get('formato', '')} | {entry.get('qualidade', '')}"
        data_text = entry.get("data", "")
        autor_text = entry.get("autor", "")

        # Linha 1: Titulo
        lbl_titulo = Label(item,
                           text=titulo[:60] + ("..." if len(titulo) > 60 else ""),
                           bg=COR_FUNDO2,
                           fg=COR_TEXTO,
                           font=("Segoe UI", 10, "bold"),
                           anchor="w",
                           cursor="hand2")
        lbl_titulo.pack(fill=X, padx=10, pady=(6, 0))
        lbl_titulo.bind("<Button-1>", _ao_clicar)

        # Linha 2: Info
        if autor_text or info_text:
            linha2 = Frame(item, bg=COR_FUNDO2)
            linha2.pack(fill=X, padx=10, pady=(2, 4))

            if autor_text:
                Label(linha2,
                      text=autor_text[:40],
                      bg=COR_FUNDO2,
                      fg=COR_SECUNDARIA,
                      font=("Segoe UI", 8),
                      anchor="w").pack(side=LEFT, padx=(0, 10))

            if info_text:
                Label(linha2,
                      text=info_text,
                      bg=COR_FUNDO2,
                      fg=COR_TEXTO2,
                      font=("Segoe UI", 8),
                      anchor="w").pack(side=LEFT, padx=(0, 10))

            if data_text:
                Label(linha2,
                      text=data_text,
                      bg=COR_FUNDO2,
                      fg=COR_TEXTO2,
                      font=("Segoe UI", 8),
                      anchor="e").pack(side=RIGHT)

        # Separador sutil
        Frame(item, bg=COR_CARD, height=1).pack(fill=X)

    # ─── FRAME DOWNLOAD ─────────────────────────────────────────────────────

    def criar_frame_download(self):
        """Cria o frame com botao de download e barra de progresso."""
        frame = Frame(self.pagina_download, bg=COR_FUNDO)
        frame.pack(fill=X, padx=15, pady=(0, 10))

        card = Frame(frame, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=X)
        self._card_download = card  # Salva para aplicar borda depois

        conteudo = Frame(card, bg=COR_CARD)
        conteudo.pack(fill=X, padx=15, pady=12)

        # ─── Barra de progresso ────────────────────────────────────────────
        self.progress_var = DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(conteudo,
                                            variable=self.progress_var,
                                            maximum=100,
                                            style="Custom.Horizontal.TProgressbar")
        self.progress_bar.pack(fill=X, pady=(0, 10))

        # Label de porcentagem
        self.label_progresso = Label(conteudo,
                                     text="0%",
                                     bg=COR_CARD,
                                     fg=COR_PROGRESSO,
                                     font=("Segoe UI", 12, "bold"))
        self.label_progresso.pack(anchor="center", pady=(0, 10))

        # ─── Botoes de acao ───────────────────────────────────────────────
        linha_botoes = Frame(conteudo, bg=COR_CARD)
        linha_botoes.pack(fill=X)

        self.btn_download = Button(linha_botoes,
                                   text="INICIAR DOWNLOAD",
                                   command=self.iniciar_download,
                                   bg=COR_PRIMARIA,
                                   fg="white",
                                   font=("Segoe UI", 13, "bold"),
                                   relief="flat",
                                   bd=0,
                                   padx=30,
                                   pady=12,
                                   cursor="hand2",
                                   activebackground=COR_PRIMARIA2,
                                   activeforeground="white")
        self.btn_download.pack(side=LEFT, expand=True, fill=X)

        self.btn_cancelar = Button(linha_botoes,
                                   text="Cancelar",
                                   command=self.cancelar_download,
                                   bg="#7f8c8d",
                                   fg="white",
                                   font=("Segoe UI", 10),
                                   relief="flat",
                                   bd=0,
                                   padx=15,
                                   pady=12,
                                   cursor="hand2",
                                   state="disabled",
                                   activebackground="#95a5a6",
                                   activeforeground="white")
        self.btn_cancelar.pack(side=RIGHT, padx=(10, 0))

        self.btn_abrir_pasta = Button(linha_botoes,
                                      text="Abrir Pasta",
                                      command=self.abrir_pasta,
                                      bg="#5d6d7e",
                                      fg="white",
                                      font=("Segoe UI", 10),
                                      relief="flat",
                                      bd=0,
                                      padx=15,
                                      pady=12,
                                      cursor="hand2",
                                      activebackground="#707b8c",
                                      activeforeground="white")
        self.btn_abrir_pasta.pack(side=RIGHT, padx=(10, 0))

    # ─── FRAME LOG ──────────────────────────────────────────────────────────

    def criar_frame_log(self):
        """Cria o frame com area de log."""
        self._log_tags_cache: set = set()  # Cache de tags configuradas

        frame = Frame(self.pagina_download, bg=COR_FUNDO)
        frame.pack(fill=BOTH, expand=True, padx=15, pady=(0, 15))

        card = Frame(frame, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=BOTH, expand=True)
        self._card_log = card  # Salva para aplicar borda depois

        conteudo = Frame(card, bg=COR_CARD)
        conteudo.pack(fill=BOTH, expand=True, padx=15, pady=10)

        # Label do log
        Label(conteudo,
              text="Status:",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9, "bold")).pack(anchor="w")

        # Area de texto do log
        frame_texto = Frame(conteudo, bg=COR_FUNDO2, bd=0, highlightthickness=1,
                           highlightbackground=COR_CARD)
        frame_texto.pack(fill=BOTH, expand=True, pady=(5, 0))

        self.text_log = Text(frame_texto,
                             bg=COR_FUNDO2,
                             fg=COR_TEXTO2,
                             insertbackground=COR_TEXTO,
                             font=("Consolas", 9),
                             relief="flat",
                             bd=0,
                             padx=10,
                             pady=8,
                             height=6,
                             wrap=WORD,
                             state="disabled")
        self.text_log.pack(side=LEFT, fill=BOTH, expand=True)

        # Scrollbar
        scroll_log = Scrollbar(frame_texto,
                               command=self.text_log.yview,
                               bg=COR_CARD,
                               troughcolor=COR_FUNDO2)
        scroll_log.pack(side=RIGHT, fill=Y)
        self.text_log.config(yscrollcommand=scroll_log.set)

    # ─── PAGINA SOBRE ───────────────────────────────────────────────────────

    def criar_pagina_sobre(self):
        """Constroi a pagina 'Sobre' com informacoes do app."""
        # ─── Card: sobre o app ────────────────────────────────────────────
        card = Frame(self.pagina_sobre, bg=COR_CARD, relief="flat", bd=0)
        card.pack(fill=X, padx=15, pady=(0, 10))
        self.aplicar_borda_card(card)

        conteudo = Frame(card, bg=COR_CARD)
        conteudo.pack(fill=X, padx=15, pady=12)

        Label(conteudo,
              text="Sobre o YouTube Downloader",
              bg=COR_CARD,
              fg=COR_TEXTO,
              font=("Segoe UI", 13, "bold")).pack(anchor="w")

        Label(conteudo,
              text=f"Versao {APP_VERSION} - Baixe videos e audios do YouTube e de dezenas de outras plataformas, gratuitamente.",
              bg=COR_CARD,
              fg=COR_TEXTO2,
              font=("Segoe UI", 9),
              wraplength=650,
              justify=LEFT).pack(anchor="w", pady=(6, 0))

        # ─── Card: status do ambiente ─────────────────────────────────────
        card2 = Frame(self.pagina_sobre, bg=COR_CARD, relief="flat", bd=0)
        card2.pack(fill=X, padx=15, pady=(0, 10))
        self.aplicar_borda_card(card2)

        conteudo2 = Frame(card2, bg=COR_CARD)
        conteudo2.pack(fill=X, padx=15, pady=12)

        Label(conteudo2,
              text="Status do ambiente",
              bg=COR_CARD,
              fg=COR_TEXTO,
              font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        self._status_sobre_labels = {}
        status_itens = [
            ("yt-dlp", "ytdlp"),
            ("ffmpeg", "ffmpeg"),
            ("Pillow (thumbnails)", "pillow"),
            ("Drag & drop (Windows)", "drop"),
        ]
        for nome, chave in status_itens:
            linha = Frame(conteudo2, bg=COR_CARD)
            linha.pack(fill=X, pady=2)
            Label(linha,
                  text=nome,
                  bg=COR_CARD,
                  fg=COR_TEXTO2,
                  font=("Segoe UI", 9),
                  width=24,
                  anchor="w").pack(side=LEFT)
            lbl = Label(linha,
                        text="...",
                        bg=COR_CARD,
                        fg=COR_TEXTO2,
                        font=("Segoe UI", 9, "bold"))
            lbl.pack(side=LEFT)
            self._status_sobre_labels[chave] = lbl

        # ─── Card: atalhos de teclado ─────────────────────────────────────
        card3 = Frame(self.pagina_sobre, bg=COR_CARD, relief="flat", bd=0)
        card3.pack(fill=X, padx=15, pady=(0, 10))
        self.aplicar_borda_card(card3)

        conteudo3 = Frame(card3, bg=COR_CARD)
        conteudo3.pack(fill=X, padx=15, pady=12)

        Label(conteudo3,
              text="Atalhos de teclado",
              bg=COR_CARD,
              fg=COR_TEXTO,
              font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        atalhos = [
            ("Ctrl + D", "Voltar para a pagina Download"),
            ("Ctrl + F", "Ir para a pesquisa do YouTube"),
            ("Ctrl + Enter", "Iniciar download"),
            ("Ctrl + L", "Limpar tudo"),
            ("Enter (no campo URL)", "Buscar informacoes"),
            ("Clique direito (campo URL)", "Colar / Limpar"),
        ]
        for tecla, desc in atalhos:
            linha = Frame(conteudo3, bg=COR_CARD)
            linha.pack(fill=X, pady=2)
            Label(linha,
                  text=tecla,
                  bg=COR_CARD,
                  fg=COR_SECUNDARIA,
                  font=("Segoe UI", 9, "bold"),
                  width=18,
                  anchor="w").pack(side=LEFT)
            Label(linha,
                  text=desc,
                  bg=COR_CARD,
                  fg=COR_TEXTO2,
                  font=("Segoe UI", 9),
                  anchor="w").pack(side=LEFT)

        # ─── Botoes de acao ───────────────────────────────────────────────
        frame_botoes = Frame(self.pagina_sobre, bg=COR_FUNDO)
        frame_botoes.pack(fill=X, padx=15)

        Button(frame_botoes,
               text="Verificar Atualizacao",
               command=self.verificar_atualizacao_app,
               bg=COR_SECUNDARIA,
               fg="white",
               font=("Segoe UI", 9, "bold"),
               relief="flat",
               bd=0,
               padx=12,
               pady=8,
               cursor="hand2",
               activebackground="#2980b9",
               activeforeground="white").pack(side=LEFT, padx=(0, 6))

        Button(frame_botoes,
               text="Atualizar yt-dlp",
               command=self.atualizar_ytdlp,
               bg="#8e44ad",
               fg="white",
               font=("Segoe UI", 9),
               relief="flat",
               bd=0,
               padx=12,
               pady=8,
               cursor="hand2",
               activebackground="#9b59b6",
               activeforeground="white").pack(side=LEFT, padx=(0, 6))

        Button(frame_botoes,
               text="Abrir pasta de downloads",
               command=self.abrir_pasta,
               bg="#5d6d7e",
               fg="white",
               font=("Segoe UI", 9),
               relief="flat",
               bd=0,
               padx=12,
               pady=8,
               cursor="hand2",
               activebackground="#707b8c",
               activeforeground="white").pack(side=LEFT)

    def _atualizar_status_sobre(self):
        """Atualiza os indicadores de ambiente da pagina Sobre (lazy)."""
        valores = {
            "ytdlp": verificar_ytdlp(),
            "ffmpeg": verificar_ffmpeg(),
            "pillow": HAS_PIL,
            "drop": HAS_DROP_HANDLER,
        }
        for chave, ok in valores.items():
            lbl = self._status_sobre_labels.get(chave)
            if lbl:
                lbl.config(
                    text="OK" if ok else "Faltando",
                    fg=COR_SUCESSO if ok else COR_ERRO,
                )

    # =========================================================================
    # LOGICA PRINCIPAL
    # =========================================================================

    def aplicar_config_salva(self):
        """Aplica as configuracoes salvas aos widgets da interface."""
        # Formato salvo
        fmt = self.config.get("ultimo_formato", "mp4")
        if fmt in ("mp4", "mp3", "webm", "mkv"):
            self.formato_var.set(fmt)

        # Qualidade salva
        qual = self.config.get("ultima_qualidade", "Melhor disponivel")
        qual_values = self.combo_qualidade["values"]
        if qual in qual_values:
            self.qualidade_var.set(qual)

        # Diretorio salvo
        self.diretorio_var.set(str(self.diretorio_saida))

        # Legendas salvas
        self.subs_var.set(self.config.get("subs_habilitado", False))
        self.subs_auto_var.set(self.config.get("subs_auto", False))
        lang = self.config.get("subs_idioma", "Portugues (BR)")
        lang_values = [l[0] for l in self.subs_idiomas]
        if lang in lang_values:
            self.subs_lang_var.set(lang)

        # Cookies salvos
        self.cookies_var.set(self.config.get("cookies_habilitado", False))
        nav = self.config.get("cookies_navegador", "chrome")
        if nav in NAVEGADORES_COOKIES:
            self.cookies_nav_var.set(nav)
        self.on_cookies_change()

        # Atualiza estados dos widgets dependentes
        self.on_formato_change()
        self.on_subtitle_change()

        # Log de carregamento
        total = self.config.history_count()
        if total > 0:
            self._config_log_historico(total)

    def _config_log_historico(self, total: int):
        """Log do carregamento do historico (chamado apos UI pronta)."""
        self.adicionar_log(f"Configuracoes carregadas. {total} downloads no historico.", COR_TEXTO2)

    def _ao_fechar(self):
        """Salva configuracoes e fecha a janela."""
        # Remove o drop handler (Windows)
        try:
            if self.drop_handler:
                self.drop_handler.destroy()
                self.drop_handler = None
        except Exception:
            pass

        # Salva geometria da janela
        try:
            geo = self.root.geometry()
            match = re.match(r"(\d+)x(\d+)", geo)
            if match:
                self.config.set_multiplas(
                    janela_largura=int(match.group(1)),
                    janela_altura=int(match.group(2)),
                )
        except Exception:
            pass
        self.root.destroy()

    def verificar_ambiente(self):
        """Verifica se as dependencias estao instaladas."""
        erros = []

        if not verificar_ytdlp():
            erros.append("yt-dlp nao encontrado! Instale com: pip install yt-dlp")
        if not verificar_ffmpeg():
            erros.append("ffmpeg nao encontrado!")

        if erros:
            msg = "Atencao: " + ", ".join(erros)
            self.adicionar_log(msg, COR_AVISO)
            messagebox.showwarning("Dependencias", msg)
        else:
            self.adicionar_log("Ambiente OK! yt-dlp e ffmpeg encontrados.", COR_SUCESSO)
            self.adicionar_log("Cole uma URL e clique em 'Buscar Informacoes'.", COR_TEXTO2)

    def buscar_info(self):
        """Busca informacoes do video em thread separada."""
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("URL vazia", "Por favor, cole uma URL.")
            return

        if not url.startswith("http"):
            if re.match(r"^[\w-]{11}$", url):
                url = f"https://www.youtube.com/watch?v={url}"
            else:
                url = f"https://{url}"
            self.entry_url.delete(0, END)
            self.entry_url.insert(0, url)

        if not validar_url(url):
            messagebox.showwarning("URL invalida",
                                   "A URL informada nao parece ser suportada pelo yt-dlp.")
            return

        # Detecta plataforma e loga
        plat = detectar_plataforma(url)
        if plat:
            self.adicionar_log(f"Buscando informacoes ({plat['nome']})...", COR_SECUNDARIA)
        else:
            self.adicionar_log("Buscando informacoes...", COR_SECUNDARIA)
        self.info_video = None

        thread = threading.Thread(target=self._buscar_info_thread, args=(url,), daemon=True)
        thread.start()

    def _buscar_info_thread(self, url: str):
        """Thread para buscar informacoes sem travar a UI."""
        try:
            cmd = localizar_ytdlp() + [
                "--dump-json",
                "--no-warnings",
                "--flat-playlist",
                url
            ]
            resultado = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            if resultado.returncode != 0:
                erro = resultado.stderr.strip()
                self.adicionar_log(f"Erro ao buscar informacoes: {erro}", COR_ERRO)
                return

            linhas = resultado.stdout.strip().split("\n")
            if not linhas or not linhas[0]:
                self.adicionar_log("Nenhum dado encontrado.", COR_ERRO)
                return

            info = json.loads(linhas[0])

            if info.get("playlist_count", 0) > 1:
                info["is_playlist"] = True

            self.root.after(0, lambda: self.atualizar_info_video(info))
            self.root.after(0, lambda: self.adicionar_log(
                "Informacoes obtidas com sucesso!", COR_SUCESSO))

        except subprocess.TimeoutExpired:
            self.adicionar_log("Tempo limite excedido.", COR_ERRO)
        except json.JSONDecodeError:
            self.adicionar_log("Erro ao processar dados do YouTube.", COR_ERRO)
        except Exception as e:
            self.adicionar_log(f"Erro: {e}", COR_ERRO)

    def abrir_pasta(self):
        """Abre a pasta de destino no explorador de arquivos."""
        pasta = Path(self.diretorio_var.get()) if self.diretorio_var.get() else self.diretorio_saida
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(pasta))
            else:
                subprocess.Popen(["xdg-open", str(pasta)])
            self.adicionar_log(f"Abrindo pasta: {pasta}", COR_SECUNDARIA)
        except Exception as e:
            self.adicionar_log(f"Erro ao abrir pasta: {e}", COR_ERRO)

    def atualizar_ytdlp(self):
        """Atualiza o yt-dlp para a versao mais recente (em thread)."""
        if self._atualizando_ytdlp:
            return
        self._atualizando_ytdlp = True
        self.adicionar_log("Atualizando yt-dlp... (pode levar alguns segundos)", COR_SECUNDARIA)

        def _run():
            ok, msg = atualizar_ytdlp()
            self.root.after(0, lambda: self._fim_atualizacao(ok, msg))

        threading.Thread(target=_run, daemon=True).start()

    def _fim_atualizacao(self, ok: bool, msg: str):
        """Finaliza a atualizacao do yt-dlp."""
        self._atualizando_ytdlp = False
        self.adicionar_log(msg, COR_SUCESSO if ok else COR_ERRO)
        if ok:
            messagebox.showinfo("Atualizar yt-dlp", msg)
        else:
            messagebox.showwarning("Atualizar yt-dlp", msg)
        # Mantem o status da pagina Sobre atualizado apos a atualizacao
        if hasattr(self, "_status_sobre_labels"):
            self._atualizar_status_sobre()

    def limpar_tudo(self):
        """Limpa URL, informacoes, thumbnail, pesquisa e log."""
        self.entry_url.delete(0, END)
        self.info_video = None
        self.remover_thumbnail()
        self.mostrar_ocultar_info(False)
        self.progress_var.set(0)
        self.label_progresso.config(text="0%")
        # Limpa estado da pesquisa (se ja criada)
        if hasattr(self, "entry_pesquisa"):
            self.entry_pesquisa.delete(0, END)
        if hasattr(self, "frame_resultados"):
            for w in self.frame_resultados.winfo_children():
                w.destroy()
        if hasattr(self, "label_resultado_total"):
            self.label_resultado_total.config(text="")
        self.text_log.config(state="normal")
        self.text_log.delete(1.0, END)
        self.text_log.config(state="disabled")

    # ─── DOWNLOAD ───────────────────────────────────────────────────────────

    def iniciar_download(self):
        """Inicia download: direto se fila vazia, ou processa a fila."""
        if self.download_em_andamento:
            return

        # Se tem itens na fila, processa a fila
        if self.fila_manager.total_count() > 0 and not self.fila_manager.is_processing:
            self._processar_proximo_fila()
            return

        # Download direto (sem fila)
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("URL vazia", "Por favor, cole uma URL do YouTube.")
            return

        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
            self.entry_url.delete(0, END)
            self.entry_url.insert(0, url)

        if not validar_url(url):
            messagebox.showwarning("URL invalida",
                                   "A URL informada nao parece ser suportada pelo yt-dlp.")
            return

        # Configura parametros
        formato = self.formato_var.get()
        qual_label = self.qualidade_var.get()
        qualidade = self.qualidade_map.get(qual_label, "best")
        diretorio = Path(self.diretorio_var.get())

        playlist_start = None
        playlist_end = None
        is_playlist = self.playlist_var.get()
        if is_playlist:
            inicio = self.playlist_inicio_var.get().strip()
            fim = self.playlist_fim_var.get().strip()
            playlist_start = int(inicio) if inicio.isdigit() else None
            playlist_end = int(fim) if fim.isdigit() else None

        # Atualiza UI
        self._iniciar_estado_download()

        self.adicionar_log(f"Iniciando download...", COR_SECUNDARIA)
        self.adicionar_log(f"  Formato: {formato.upper()}", COR_TEXTO2)
        self.adicionar_log(f"  Qualidade: {qual_label}", COR_TEXTO2)
        self.adicionar_log(f"  Destino: {diretorio}", COR_TEXTO2)

        # Log de legendas
        if self.subs_var.get():
            lang_name = self.subs_lang_var.get()
            auto_txt = " + auto" if self.subs_auto_var.get() else ""
            self.adicionar_log(f"  Legendas: {lang_name}{auto_txt}", COR_TEXTO2)

        # Thread de download
        cookies = self.cookies_nav_var.get() if self.cookies_var.get() else None
        thread = threading.Thread(
            target=self._download_thread,
            args=(url, formato, qualidade, diretorio,
                  playlist_start, playlist_end,
                  self.subs_var.get(), self.subs_lang_var.get(), self.subs_auto_var.get(),
                  cookies),
            daemon=True
        )
        thread.start()

    def _processar_proximo_fila(self):
        """Pega o proximo item da fila e inicia o download."""
        if self.download_em_andamento:
            return
        item = self.fila_manager.get_next()
        if not item:
            return

        url = item.url
        formato = item.formato
        qual_label = item.qualidade
        qualidade = self.qualidade_map.get(qual_label, "best")
        diretorio = Path(item.diretorio)
        playlist_start = item.playlist_start
        playlist_end = item.playlist_end

        # Atualiza a UI
        self._iniciar_estado_download()

        total = self.fila_manager.total_count()
        concluidos = sum(1 for i in self.fila_manager.get_items() if i.status in ("completed", "failed", "cancelled"))

        self.adicionar_log(f"[{concluidos + 1}/{total}] Baixando da fila...", COR_SECUNDARIA)
        self.adicionar_log(f"  URL: {url[:60]}...", COR_TEXTO2)
        self.adicionar_log(f"  Formato: {formato.upper()}", COR_TEXTO2)
        self.adicionar_log(f"  Qualidade: {qual_label}", COR_TEXTO2)
        self.adicionar_log(f"  Destino: {diretorio}", COR_TEXTO2)

        if item.subs:
            self.adicionar_log(f"  Legendas: {item.subs_idioma}", COR_TEXTO2)

        # Thread de download
        thread = threading.Thread(
            target=self._download_thread,
            args=(url, formato, qualidade, diretorio,
                  playlist_start, playlist_end,
                  item.subs, item.subs_idioma, item.subs_auto, item.cookies),
            daemon=True
        )
        thread.start()

    def _iniciar_estado_download(self):
        """Prepara a UI para o estado de download."""
        self.download_em_andamento = True
        texto_btn = "BAIXANDO..."
        if self.fila_manager.is_processing:
            total = self.fila_manager.total_count()
            pendentes = self.fila_manager.get_pending_count()
            completo = total - pendentes + 1
            texto_btn = f"FILA {completo}/{total}"
        self.btn_download.config(text=texto_btn, state="disabled", bg="#7f8c8d")
        self.btn_cancelar.config(state="normal")
        self.progress_var.set(0)
        self.label_progresso.config(text="Preparando...", fg=COR_AVISO)

    def _download_thread(self, url, formato, qualidade, diretorio,
                         playlist_start, playlist_end,
                         subs_ativado=False, subs_idioma="pt", subs_auto=False,
                         navegador_cookies=None):
        """Thread que executa o download (usa o motor compartilhado)."""
        try:
            diretorio.mkdir(parents=True, exist_ok=True)

            cmd = montar_comando_download(
                url, formato, qualidade, diretorio,
                playlist_start=playlist_start,
                playlist_end=playlist_end,
                subs=subs_ativado,
                subs_auto=subs_auto,
                subs_idioma=subs_idioma,
                navegador_cookies=navegador_cookies,
            )

            # Executa o download
            self.processando = True
            cancelado = False
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

            ultimo_pct = -1.0
            for linha in processo.stdout:
                if not self.processando:
                    cancelado = True
                    processo.terminate()
                    break

                linha = linha.strip()
                if not linha:
                    continue

                if linha.startswith("[youtube]") or linha.startswith("[info]") or linha.startswith("[debug]"):
                    continue

                if "[download]" in linha and "%" in linha:
                    match = re.search(r"(\d+\.?\d*)%", linha)
                    if match:
                        pct = float(match.group(1))
                        velocidade = ""
                        eta = ""
                        m_vel = re.search(r"at\s+([\d.]+\s*\w+/s)", linha)
                        if m_vel:
                            velocidade = m_vel.group(1)
                        m_eta = re.search(r"ETA\s+(\d{1,2}:\d{2})", linha)
                        if m_eta:
                            eta = m_eta.group(1)
                        # Throttling: so atualiza a UI quando o percentual mudar
                        # de forma significativa (evita travar com milhares de updates)
                        if pct - ultimo_pct >= 0.5 or pct >= 100:
                            ultimo_pct = pct
                            self.root.after(0, lambda v=pct, vd=velocidade, et=eta: self.atualizar_progresso(v, vd, et))
                elif "has already been downloaded" in linha.lower():
                    self.adicionar_log("Arquivo ja existe. Pulando...", COR_AVISO)
                elif "[download]" in linha and "100%" in linha:
                    self.root.after(0, lambda: self.atualizar_progresso(100))

            processo.wait()

            if cancelado:
                self.root.after(0, self._download_cancelado)
            elif processo.returncode == 0:
                self.root.after(0, self.download_concluido)
            else:
                self.root.after(0, self._download_falhou)

        except Exception as e:
            self.adicionar_log(f"Erro: {e}", COR_ERRO)
            self.root.after(0, self._download_falhou)
        finally:
            self.processando = False
            self.root.after(0, self.finalizar_download)

    def atualizar_progresso(self, valor: float, velocidade: str = "", eta: str = ""):
        """Atualiza a barra de progresso (com velocidade e ETA quando disponiveis)."""
        self.progress_var.set(valor)
        texto = f"{valor:.0f}%"
        if velocidade:
            texto += f"  |  {velocidade}"
        if eta:
            texto += f"  |  ETA {eta}"
        self.label_progresso.config(text=texto, fg=COR_PROGRESSO)

    def download_concluido(self):
        """Chamado quando o download e concluido. Salva no historico."""
        self.adicionar_log("Download concluido com sucesso!", COR_SUCESSO)
        self.progress_var.set(100)
        self.label_progresso.config(text="100%", fg=COR_SUCESSO)

        # Obtem informacoes para o historico (da UI ou do item da fila)
        current_item = self.fila_manager.get_current()

        if self.info_video:
            info = self.info_video
            entry = {
                "url": self.entry_url.get().strip(),
                "titulo": info.get("title", info.get("playlist_title", "Desconhecido")),
                "autor": info.get("uploader", ""),
                "formato": self.formato_var.get().upper(),
                "qualidade": self.qualidade_var.get(),
                "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "caminho": str(self.diretorio_saida),
                "duracao": formatar_duracao(info.get("duration", 0)),
                "thumbnail": info.get("thumbnail", ""),
            }
            self.config.add_history(entry)
            self.adicionar_log("Salvo no historico.", COR_TEXTO2)
        elif current_item:
            # Modo fila: salva com info minima (sem dados do video)
            entry = {
                "url": current_item.url,
                "titulo": current_item.url[:50],
                "autor": "",
                "formato": current_item.formato.upper(),
                "qualidade": current_item.qualidade,
                "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "caminho": current_item.diretorio,
                "duracao": "",
                "thumbnail": "",
            }
            self.config.add_history(entry)

        # Marca item atual da fila como completo (se houver)
        if current_item:
            self.fila_manager.mark_completed(current_item, True)
            current_item.titulo = self.info_video.get("title", "") if self.info_video else ""

    def finalizar_download(self):
        """Finaliza o estado de download. Se houver fila, processa proximo."""
        self.download_em_andamento = False

        # Verifica se tem mais itens na fila para processar
        if self.fila_manager.get_pending_count() > 0:
            self.btn_download.config(text="FILA...", state="disabled", bg="#7f8c8d")
            self.btn_cancelar.config(state="disabled")
            self.progress_var.set(0)
            self.label_progresso.config(text="Proximo...", fg=COR_AVISO)
            self.root.after(500, self._processar_proximo_fila)
        else:
            self.btn_download.config(text="INICIAR DOWNLOAD",
                                     state="normal",
                                     bg=COR_PRIMARIA,
                                     activebackground=COR_PRIMARIA2)
            self.btn_cancelar.config(state="disabled")

        self.root.after(0, self.verificar_fila_log)

    def _download_cancelado(self):
        """Marca o item atual da fila como cancelado."""
        current = self.fila_manager.get_current()
        if current:
            self.fila_manager.mark_completed(current, False)
            current.status = "cancelled"
            self.fila_manager._notify_status()
        self.progress_var.set(0)
        self.label_progresso.config(text="Cancelado", fg=COR_AVISO)

    def _download_falhou(self):
        """Marca o item atual da fila como falho e informa o usuario."""
        current = self.fila_manager.get_current()
        if current:
            self.fila_manager.mark_completed(current, False)
        self.progress_var.set(0)
        self.label_progresso.config(text="Falhou", fg=COR_ERRO)

    def cancelar_download(self):
        """Cancela o download em andamento."""
        if self.download_em_andamento:
            self.processando = False
            self.adicionar_log("Cancelando download...", COR_AVISO)
            self.btn_cancelar.config(state="disabled")

    # ─── LOG ─────────────────────────────────────────────────────────────────

    def adicionar_log(self, mensagem: str, cor: str = COR_TEXTO2):
        """Adiciona mensagem ao log (thread-safe)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.fila_log.put((timestamp, mensagem, cor))

    def verificar_fila_log(self):
        """Verifica se ha mensagens na fila de log e exibe."""
        try:
            while True:
                timestamp, mensagem, cor = self.fila_log.get_nowait()
                self._inserir_log(timestamp, mensagem, cor)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.verificar_fila_log)

    def _inserir_log(self, timestamp: str, mensagem: str, cor: str):
        """Insere uma linha no log com a cor especificada."""
        self.text_log.config(state="normal")
        self.text_log.insert(END, f"[{timestamp}] ", "timestamp")

        # Tag fixa por cor para evitar acúmulo de milhares de tags
        tag_msg = f"msg_{cor.replace('#', '')}"
        if tag_msg not in self._log_tags_cache:
            self._log_tags_cache.add(tag_msg)
            self.text_log.tag_config(tag_msg, foreground=cor)

        self.text_log.tag_config("timestamp", foreground=COR_TEXTO2)
        self.text_log.insert(END, f"{mensagem}\n", tag_msg)
        self.text_log.see(END)
        self.text_log.config(state="disabled")

    # ─── UTILITARIOS ─────────────────────────────────────────────────────────

    @staticmethod
    def aplicar_borda_card(widget):
        """Aplica borda sutil em um card."""
        widget.config(highlightthickness=1, highlightbackground="#1a3a6a")

    def aplicar_bordas_cards(self):
        """Aplica borda em todos os cards apos criacao."""
        for attr in ["_card_info", "_card_opcoes", "_card_download", "_card_log"]:
            card = getattr(self, attr, None)
            if card:
                self.aplicar_borda_card(card)

    # =========================================================================
    # SISTEMA DE ATUALIZACOES DO APP
    # =========================================================================

    def verificar_atualizacao_app(self):
        """Verifica se ha nova versao do app no servidor (em thread)."""
        update_url = self.config.get_update_url()
        if not update_url or update_url.startswith("https://SEU-SERVIDOR"):
            return  # Servidor ainda nao configurado
        self.adicionar_log("Verificando atualizacoes...", COR_TEXTO2)
        threading.Thread(
            target=self._thread_verificar_atualizacao,
            args=(update_url,),
            daemon=True,
        ).start()

    def _thread_verificar_atualizacao(self, update_url: str):
        """Thread de verificacao de atualizacao (nao bloqueia a UI)."""
        try:
            info = verificar_atualizacao(update_url, APP_VERSION, plataforma_atual())
            if info:
                self.root.after(0, self._mostrar_dialogo_atualizacao, info)
            else:
                self.adicionar_log(
                    "Voce esta usando a versao mais recente.", COR_SUCESSO
                )
        except Exception as e:
            self.adicionar_log(f"Falha ao verificar atualizacoes: {e}", COR_AVISO)

    def _mostrar_dialogo_atualizacao(self, info: AtualizacaoInfo):
        """Mostra a janela de nova versao disponivel."""
        if not info or not info.platform or not info.platform.url:
            return

        # Se o usuario ja ignorou esta versao, nao mostra de novo
        if self.config.get("update_ignorada") == info.version:
            return

        # Evita multiplos dialogos de atualizacao abertos ao mesmo tempo
        if getattr(self, "_dialogo_atualizacao_aberto", False):
            return
        self._dialogo_atualizacao_aberto = True

        win = Toplevel(self.root)
        win.title("Atualizacao disponivel")
        win.configure(bg=COR_FUNDO)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        # Fechar pelo "X" tambem libera o guard anti-duplicidade
        win.protocol("WM_DELETE_WINDOW", lambda: self._fechar_dialogo_atualizacao(win))

        # ─── Cabecalho ────────────────────────────────────────────────────
        cab = Frame(win, bg=COR_FUNDO2)
        cab.pack(fill=X)
        Frame(cab, bg=COR_SUCESSO, height=4).pack(fill=X, side=BOTTOM)
        Label(cab,
              text="Nova versao disponivel!",
              bg=COR_FUNDO2,
              fg=COR_SUCESSO,
              font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=10)

        corpo = Frame(win, bg=COR_FUNDO)
        corpo.pack(fill=BOTH, expand=True, padx=16, pady=10)

        Label(corpo,
              text=f"Versao atual: {APP_VERSION}   →   Nova versao: {info.version}",
              bg=COR_FUNDO,
              fg=COR_TEXTO,
              font=("Segoe UI", 11, "bold")).pack(anchor="w")

        if info.published_at:
            Label(corpo,
                  text=f"Publicada em: {info.published_at[:10]}",
                  bg=COR_FUNDO,
                  fg=COR_TEXTO2,
                  font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        # Notas da versao
        frame_notas = Frame(corpo, bg=COR_CARD, relief="flat", bd=0)
        frame_notas.pack(fill=X, pady=(10, 4))
        self.aplicar_borda_card(frame_notas)

        text_notas = Text(frame_notas,
                          bg=COR_FUNDO2,
                          fg=COR_TEXTO,
                          font=("Segoe UI", 9),
                          wrap=WORD,
                          height=7,
                          relief="flat",
                          bd=0,
                          padx=8,
                          pady=8)
        scroll = Scrollbar(frame_notas, command=text_notas.yview)
        text_notas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=RIGHT, fill=Y)
        text_notas.pack(side=LEFT, fill=BOTH, expand=True)
        text_notas.insert(END, info.notes or "Sem notas para esta versao.")
        text_notas.config(state="disabled")

        # Progresso (oculto ate baixar)
        frame_prog = Frame(corpo, bg=COR_FUNDO)
        label_prog = Label(frame_prog,
                           text="",
                           bg=COR_FUNDO,
                           fg=COR_TEXTO2,
                           font=("Segoe UI", 9))
        label_prog.pack(anchor="w", pady=(4, 2))
        barra = ttk.Progressbar(frame_prog, mode="determinate",
                                style="Custom.Horizontal.TProgressbar")
        barra.pack(fill=X)

        # Botoes
        frame_botoes = Frame(win, bg=COR_FUNDO)
        frame_botoes.pack(fill=X, padx=16, pady=(0, 12))

        def _baixar():
            self._baixar_atualizacao(
                info, win, frame_prog, label_prog, barra, frame_botoes
            )

        Button(frame_botoes,
               text="Baixar e instalar",
               command=_baixar,
               bg=COR_SUCESSO,
               fg="white",
               font=("Segoe UI", 10, "bold"),
               relief="flat",
               bd=0,
               padx=12,
               pady=8,
               cursor="hand2",
               activebackground="#27ae60",
               activeforeground="white").pack(side=LEFT, padx=(0, 6))

        Button(frame_botoes,
               text="Pagina da versao",
               command=lambda: self._abrir_pagina_release(info),
               bg=COR_SECUNDARIA,
               fg="white",
               font=("Segoe UI", 9),
               relief="flat",
               bd=0,
               padx=10,
               pady=8,
               cursor="hand2",
               activebackground="#2980b9",
               activeforeground="white").pack(side=LEFT, padx=(0, 6))

        Button(frame_botoes,
               text="Ignorar esta versao",
               command=lambda: self._ignorar_atualizacao(info.version, win),
               bg=COR_FUNDO2,
               fg=COR_TEXTO2,
               font=("Segoe UI", 9),
               relief="flat",
               bd=0,
               padx=10,
               pady=8,
               cursor="hand2",
               activebackground=COR_CARD,
               activeforeground=COR_TEXTO).pack(side=LEFT, padx=(0, 6))

        Button(frame_botoes,
               text="Depois",
               command=lambda: self._fechar_dialogo_atualizacao(win),
               bg=COR_FUNDO2,
               fg=COR_TEXTO2,
               font=("Segoe UI", 9),
               relief="flat",
               bd=0,
               padx=10,
               pady=8,
               cursor="hand2",
               activebackground=COR_CARD,
               activeforeground=COR_TEXTO).pack(side=LEFT)

        # Centraliza sobre a janela principal
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_reqheight()) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _baixar_atualizacao(self, info, win, frame_prog, label_prog, barra, frame_botoes):
        """Baixa o instalador em thread com barra de progresso."""
        for w in frame_botoes.winfo_children():
            w.config(state="disabled")
        frame_prog.pack(fill=X, pady=(8, 4))
        label_prog.config(text="Iniciando download...")

        destino = caminho_instalador_temp(info.version)

        def _reporthook(count, block_size, total_size):
            if total_size > 0:
                pct = min(100, int(count * block_size * 100 / total_size))
                self.root.after(0, lambda: barra.config(value=pct))
                self.root.after(0, lambda: label_prog.config(
                    text=f"Baixando... {pct}%"))

        def _thread():
            try:
                baixar_instalador(info.platform.url, destino, reporthook=_reporthook)
                if info.platform.sha256 and not verificar_sha256(destino, info.platform.sha256):
                    raise RuntimeError(
                        "Verificacao SHA-256 falhou. Arquivo corrompido?"
                    )
                self.root.after(0, self._instalador_baixado, info, win, destino)
            except Exception as e:
                self.root.after(0, self._erro_download_atualizacao, win, str(e))

        threading.Thread(target=_thread, daemon=True).start()

    def _fechar_dialogo_atualizacao(self, win):
        """Fecha o dialogo de atualizacao e libera o guard."""
        self._dialogo_atualizacao_aberto = False
        try:
            win.destroy()
        except Exception:
            pass

    def _instalador_baixado(self, info, win, destino):
        """Instalador baixado e verificado: pergunta se quer executar."""
        self._fechar_dialogo_atualizacao(win)
        self.adicionar_log(f"Instalador da versao {info.version} baixado.", COR_SUCESSO)
        if messagebox.askyesno(
                "Atualizacao",
                f"Nova versao {info.version} baixada.\n\n"
                "O instalador sera executado agora. Feche o app se necessario.\n"
                "Deseja continuar?"):
            if executar_instalador(destino):
                self.adicionar_log(
                    "Instalador executado. A atualizacao iniciara.", COR_AVISO
                )
            else:
                messagebox.showerror(
                    "Atualizacao",
                    f"Nao foi possivel executar o instalador.\n{destino}",
                )

    def _erro_download_atualizacao(self, win, erro):
        """Exibe erro de download da atualizacao."""
        messagebox.showerror(
            "Atualizacao", f"Falha ao baixar a atualizacao:\n{erro}", parent=win
        )
        self._fechar_dialogo_atualizacao(win)

    def _abrir_pagina_release(self, info):
        """Abre a pagina da release (ou do arquivo) no navegador."""
        import webbrowser
        url = info.release_page or (info.platform.url if info.platform else "")
        if url:
            webbrowser.open(url)

    def _ignorar_atualizacao(self, versao, win):
        """Salva a versao ignorada para nao avisar de novo."""
        self.config.set("update_ignorada", versao)
        win.destroy()
        self.adicionar_log(f"Versao {versao} ignorada.", COR_TEXTO2)


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

def main():
    """Funcao principal."""
    try:
        # Verifica se tkinter esta disponivel
        root = Tk()
        app = YouTubeDownloaderGUI(root)
        root.mainloop()
    except ImportError:
        print("Erro: tkinter nao encontrado!")
        print("No Windows geralmente ja vem instalado com Python.")
        print("Caso contrario, instale com: pip install tk")
        sys.exit(1)
    except Exception as e:
        import traceback
        msg = f"Erro ao iniciar interface grafica: {e}\n\n" + traceback.format_exc()
        # Em executavel windowed nao ha console: grava o erro em arquivo para diagnostico
        try:
            with open("erro_inicio.txt", "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        if sys.stdout is not None:
            print(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
