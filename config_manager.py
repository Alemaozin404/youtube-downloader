#!/usr/bin/env python3
"""
Config Manager
Gerenciamento de configuracoes persistentes e historico de downloads.
Salva em: ~/.youtube-downloader/config.json
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict, List


# ─── Caminho dos arquivos de config ─────────────────────────────────────────
CONFIG_DIR = Path.home() / ".youtube-downloader"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ─── Valores padrao ─────────────────────────────────────────────────────────
DEFAULT_CONFIG: Dict[str, Any] = {
    "versao": "1.1.0",
    # ─── Sistema de atualizacoes ────────────────────────────────────
    "update_url": "https://SEU-SERVIDOR.onrender.com",
    "update_check_auto": True,          # Verifica atualizacao ao iniciar
    "update_ignorada": "",             # Versao ignorada pelo usuario
    "diretorio_saida": str(Path.home() / "Downloads" / "YouTube Downloads"),
    "ultimo_formato": "mp4",
    "ultima_qualidade": "Melhor disponivel",
    "tema": "escuro",
    "janela_largura": 850,
    "janela_altura": 700,
    "janela_maximizada": False,
    "subs_habilitado": False,
    "subs_auto": False,
    "subs_idioma": "Portugues (BR)",
    "playlist_habilitado": False,
    "cookies_habilitado": False,
    "cookies_navegador": "chrome",
}

MAX_HISTORY = 100  # Maximo de entradas no historico


# =============================================================================
# GERENCIADOR DE CONFIGURACAO
# =============================================================================

class ConfigManager:
    """Gerencia config.json e historico de downloads."""

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self._carregar()

    # ─── Carregar / Salvar ──────────────────────────────────────────────────

    def _carregar(self):
        """Carrega config do disco ou cria com valores padrao."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                self.config = dados.get("config", {})
                self.history = dados.get("history", [])
                # Garante que chaves padrao existam
                for chave, valor in DEFAULT_CONFIG.items():
                    self.config.setdefault(chave, valor)
            except (json.JSONDecodeError, KeyError):
                self._resetar()
        else:
            self._resetar()

        self._migrar_history()

    def _resetar(self):
        """Reseta para configuracao padrao."""
        self.config = dict(DEFAULT_CONFIG)
        self.history = []
        self._salvar()

    def _salvar(self):
        """Salva config e historico no disco."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        dados = {
            "config": self.config,
            "history": self.history,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)

    def _migrar_history(self):
        """Garante que entradas antigas do historico tenham todos os campos."""
        campos_obrigatorios = [
            "url", "titulo", "autor", "formato", "qualidade",
            "data", "caminho", "duracao", "thumbnail"
        ]
        migrados = []
        for entry in self.history:
            for campo in campos_obrigatorios:
                entry.setdefault(campo, "")
            migrados.append(entry)
        self.history = migrados

    # ─── Acessar config ─────────────────────────────────────────────────────

    def get(self, chave: str, padrao: Any = None) -> Any:
        """Retorna valor da config ou padrao."""
        return self.config.get(chave, padrao)

    def set(self, chave: str, valor: Any):
        """Define valor da config e salva."""
        self.config[chave] = valor
        self._salvar()

    def set_multiplas(self, **kwargs):
        """Define varios valores de config de uma vez e salva."""
        for chave, valor in kwargs.items():
            self.config[chave] = valor
        self._salvar()

    def get_diretorio(self) -> Path:
        """Retorna o diretorio de saida como Path."""
        return Path(self.config.get("diretorio_saida", DEFAULT_CONFIG["diretorio_saida"]))

    def set_diretorio(self, path: Path):
        """Define diretorio de saida e salva."""
        path.mkdir(parents=True, exist_ok=True)
        self.set("diretorio_saida", str(path))

    # ─── Historico ──────────────────────────────────────────────────────────

    def add_history(self, entry: Dict[str, Any]):
        """Adiciona entrada ao historico."""
        # Garante campos obrigatorios
        entry.setdefault("url", "")
        entry.setdefault("titulo", "Desconhecido")
        entry.setdefault("autor", "")
        entry.setdefault("formato", "mp4")
        entry.setdefault("qualidade", "")
        entry.setdefault("data", datetime.now().strftime("%d/%m/%Y %H:%M"))
        entry.setdefault("caminho", "")
        entry.setdefault("duracao", "")
        entry.setdefault("thumbnail", "")

        # Insere no inicio
        self.history.insert(0, entry)

        # Limita tamanho
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[:MAX_HISTORY]

        self._salvar()

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historico recente."""
        return self.history[:limit]

    def search_history(self, query: str) -> list[dict[str, Any]]:
        """Busca no historico por titulo ou URL."""
        query = query.lower().strip()
        if not query:
            return self.get_history()
        return [
            entry for entry in self.history
            if query in entry.get("titulo", "").lower()
            or query in entry.get("url", "").lower()
            or query in entry.get("autor", "").lower()
        ]

    def clear_history(self):
        """Limpa todo o historico."""
        self.history = []
        self._salvar()

    def remove_history(self, index: int):
        """Remove entrada do historico pelo indice."""
        if 0 <= index < len(self.history):
            del self.history[index]
            self._salvar()

    def history_count(self) -> int:
        """Retorna quantidade de entradas no historico."""
        return len(self.history)

    # ─── Utilitarios ────────────────────────────────────────────────────────

    def get_diretorio_config(self) -> Path:
        """Retorna o diretorio onde a config esta salva."""
        return CONFIG_DIR

    def exportar_history(self, caminho: Path) -> bool:
        """Exporta historico para um arquivo JSON."""
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def importar_history(self, caminho: Path) -> bool:
        """Importa historico de um arquivo JSON."""
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            if isinstance(dados, list):
                self.history = dados[:MAX_HISTORY]
                self._salvar()
                return True
            return False
        except Exception:
            return False

    @property
    def versao(self) -> str:
        return self.config.get("versao", DEFAULT_CONFIG["versao"])

    def get_update_url(self) -> str:
        """Retorna a URL do servidor de atualizacoes configurada.

        Precedencia:
          1. Variavel de ambiente UPDATE_URL (lida ao vivo, a cada chamada)
          2. config.json -> chave update_url (se nao for placeholder)
          3. Padrao updater.UPDATE_URL (lido no import; util para build/empacotamento)

        Placeholders antigos (https://SEU-SERVIDOR...) salvos no config.json
        sao tratados como nao configurados e caem no padrao atual.
        """
        env_url = os.environ.get("UPDATE_URL", "").strip()
        if env_url:
            return env_url
        from updater import UPDATE_URL as UPDATE_URL_PADRAO  # sem env, sem circular (updater so usa stdlib)
        url = str(self.config.get("update_url", "")).strip()
        if not url or url.startswith("https://SEU-SERVIDOR"):
            return UPDATE_URL_PADRAO  # sem config ou placeholder antigo
        return url


# =============================================================================
# Singleton global
# =============================================================================
_config_manager_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Retorna a instancia unica do ConfigManager."""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance


# =============================================================================
# Teste rapido
# =============================================================================
if __name__ == "__main__":
    cfg = get_config()
    print(f"Config versao: {cfg.versao}")
    print(f"Diretorio: {cfg.get_diretorio()}")
    print(f"Formato: {cfg.get('ultimo_formato')}")
    print(f"Historico: {cfg.history_count()} entradas")

    # Teste: adiciona historico
    cfg.add_history({
        "url": "https://youtube.com/watch?v=test",
        "titulo": "Video de teste",
        "autor": "Autor Teste",
        "formato": "mp4",
        "qualidade": "1080p",
        "caminho": "C:/Downloads/test.mp4",
    })
    print(f"Historico apos adicionar: {cfg.history_count()} entradas")
    print(f"Primeira entrada: {cfg.get_history(1)[0]['titulo']}")

    # Limpa o teste
    cfg.clear_history()
    print(f"Historico apos limpar: {cfg.history_count()} entradas")
