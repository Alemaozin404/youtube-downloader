#!/usr/bin/env python3
"""
Download Queue Manager
Gerenciamento de fila de downloads com multiplos itens.
"""

import threading
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime


# ─── Status possiveis para itens da fila ─────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_DOWNLOADING = "downloading"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


class QueueItem:
    """Representa um item na fila de download."""

    def __init__(self, url: str, formato: str = "mp4", qualidade: str = "Melhor disponivel",
                 diretorio: str = "", playlist: bool = False,
                 playlist_start: Optional[int] = None, playlist_end: Optional[int] = None,
                 subs: bool = False, subs_auto: bool = False, subs_idioma: str = "pt",
                 cookies: Optional[str] = None):
        self.url = url
        self.formato = formato
        self.qualidade = qualidade
        self.diretorio = diretorio
        self.playlist = playlist
        self.playlist_start = playlist_start
        self.playlist_end = playlist_end
        self.subs = subs
        self.subs_auto = subs_auto
        self.subs_idioma = subs_idioma
        self.cookies = cookies
        self.status: str = STATUS_PENDING
        self.titulo: str = ""
        self.erro: str = ""
        self.data_adicao: str = datetime.now().strftime("%H:%M:%S")
        self.data_conclusao: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario (para exibicao na UI)."""
        return {
            "url": self.url,
            "formato": self.formato.upper(),
            "qualidade": self.qualidade,
            "titulo": self.titulo or self.url[:50],
            "status": self.status,
            "data": self.data_adicao,
        }


class DownloadQueueManager:
    """Gerenciador de fila de downloads com processamento sequencial."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: List[QueueItem] = []
        self._current_index: int = -1
        self._processing: bool = False
        self._on_item_complete: Optional[Callable] = None
        self._on_queue_complete: Optional[Callable] = None
        self._on_status_change: Optional[Callable] = None

    # ─── Callbacks ─────────────────────────────────────────────────────────

    def set_on_item_complete(self, callback: Callable[[QueueItem, bool], None]):
        """Callback chamado quando um item termina (item, sucesso)."""
        self._on_item_complete = callback

    def set_on_queue_complete(self, callback: Callable[[], None]):
        """Callback chamado quando toda a fila termina."""
        self._on_queue_complete = callback

    def set_on_status_change(self, callback: Callable[[], None]):
        """Callback chamado quando o status da fila muda."""
        self._on_status_change = callback

    # ─── Gerenciamento da fila ─────────────────────────────────────────────

    def add(self, item: QueueItem) -> int:
        """Adiciona item a fila. Retorna o indice."""
        with self._lock:
            self._items.append(item)
            idx = len(self._items) - 1
        self._notify_status()
        return idx

    def remove(self, index: int) -> bool:
        """Remove item da fila pelo indice."""
        ok = False
        with self._lock:
            if 0 <= index < len(self._items):
                item = self._items[index]
                if item.status == STATUS_DOWNLOADING:
                    return False  # Nao pode remover enquanto baixa
                del self._items[index]
                # Ajusta current_index se necessario
                if index <= self._current_index:
                    self._current_index -= 1
                ok = True
        if ok:
            self._notify_status()
        return ok

    def move_up(self, index: int) -> bool:
        """Move item para cima na fila."""
        with self._lock:
            if 0 < index < len(self._items) and index != self._current_index + 1:
                self._items[index], self._items[index - 1] = self._items[index - 1], self._items[index]
                if index == self._current_index:
                    self._current_index -= 1
                elif index - 1 == self._current_index:
                    self._current_index += 1
            else:
                return False
        self._notify_status()
        return True

    def move_down(self, index: int) -> bool:
        """Move item para baixo na fila."""
        with self._lock:
            if 0 <= index < len(self._items) - 1 and index != self._current_index:
                self._items[index], self._items[index + 1] = self._items[index + 1], self._items[index]
                if index == self._current_index:
                    self._current_index += 1
                elif index + 1 == self._current_index:
                    self._current_index -= 1
            else:
                return False
        self._notify_status()
        return True

    def retry(self, index: int) -> bool:
        """Marca item falho/cancelado como pendente novamente (re-tentar)."""
        ok = False
        with self._lock:
            if 0 <= index < len(self._items):
                item = self._items[index]
                if item.status in (STATUS_FAILED, STATUS_CANCELLED):
                    item.status = STATUS_PENDING
                    item.erro = ""
                    item.data_conclusao = ""
                    ok = True
        if ok:
            self._notify_status()
        return ok

    def clear(self):
        """Remove todos os itens pendentes (exceto o que esta baixando)."""
        with self._lock:
            self._items = [item for item in self._items if item.status == STATUS_DOWNLOADING]
            self._current_index = 0 if self._items else -1
        self._notify_status()

    def clear_all(self):
        """Remove TODOS os itens, incluindo o atual."""
        with self._lock:
            self._items = []
            self._current_index = -1
        self._notify_status()

    def get_items(self) -> List[QueueItem]:
        """Retorna copia dos itens."""
        with self._lock:
            return list(self._items)

    def get_pending_count(self) -> int:
        """Retorna quantos itens ainda faltam (incluindo o atual)."""
        with self._lock:
            return len([i for i in self._items if i.status in (STATUS_PENDING, STATUS_DOWNLOADING)])

    def total_count(self) -> int:
        """Retorna total de itens na fila."""
        with self._lock:
            return len(self._items)

    # ─── Processamento ─────────────────────────────────────────────────────

    def get_next(self) -> Optional[QueueItem]:
        """Retorna o proximo item pendente e marca como downloading."""
        with self._lock:
            for i, item in enumerate(self._items):
                if item.status == STATUS_PENDING:
                    item.status = STATUS_DOWNLOADING
                    self._current_index = i
                    self._processing = True
                    return item
            return None

    def get_current(self) -> Optional[QueueItem]:
        """Retorna o item sendo baixado atualmente."""
        with self._lock:
            if 0 <= self._current_index < len(self._items):
                item = self._items[self._current_index]
                if item.status == STATUS_DOWNLOADING:
                    return item
            return None

    def mark_completed(self, item: QueueItem, sucesso: bool = True):
        """Marca item como concluido/falhou e notifica."""
        with self._lock:
            item.status = STATUS_COMPLETED if sucesso else STATUS_FAILED
            item.data_conclusao = datetime.now().strftime("%H:%M:%S")

        # Notifica callback de item completo
        if self._on_item_complete:
            self._on_item_complete(item, sucesso)

        # Verifica se acabou a fila
        remaining = self.get_pending_count()
        if remaining == 0:
            self._processing = False
            self._current_index = -1
            if self._on_queue_complete:
                self._on_queue_complete()

        self._notify_status()

    @property
    def is_processing(self) -> bool:
        """Retorna se a fila esta processando."""
        return self._processing

    @property
    def progress_text(self) -> str:
        """Texto de progresso: '3/10' ou 'Fila vazia'."""
        with self._lock:
            total = len(self._items)
            if total == 0:
                return ""
            completed = len([i for i in self._items if i.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED)])
            return f"{completed + 1}/{total}" if self._processing else f"{completed}/{total}"

    def _notify_status(self):
        """Notifica mudanca de status."""
        if self._on_status_change:
            self._on_status_change()
