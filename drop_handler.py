"""
drop_handler.py - Suporte a arrastar e soltar (drag & drop) de URLs/texto
de outras janelas (navegadores, editores, etc.) no Windows.

Implementa a interface COM IDropTarget via ctypes.
Nao requer dependencias externas (funciona com Python puro no Windows).
"""

import sys
import ctypes
import ctypes.wintypes
import os
import re
import threading
from typing import Optional, Callable

# ─── So funciona no Windows ──────────────────────────────────────────────────
if sys.platform != "win32":
    raise ImportError("DropHandler is only supported on Windows")

# ─── Carrega DLLs do Windows ─────────────────────────────────────────────────
ole32 = ctypes.windll.ole32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

# ─── COM API ─────────────────────────────────────────────────────────────────
OleInitialize = ole32.OleInitialize
OleInitialize.restype = ctypes.c_long
OleInitialize.argtypes = [ctypes.c_void_p]

OleUninitialize = ole32.OleUninitialize
OleUninitialize.restype = None
OleUninitialize.argtypes = []

RegisterDragDrop = ole32.RegisterDragDrop
RegisterDragDrop.restype = ctypes.c_long
RegisterDragDrop.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

RevokeDragDrop = ole32.RevokeDragDrop
RevokeDragDrop.restype = ctypes.c_long
RevokeDragDrop.argtypes = [ctypes.c_void_p]

CoTaskMemFree = ole32.CoTaskMemFree
CoTaskMemFree.restype = None
CoTaskMemFree.argtypes = [ctypes.c_void_p]

GlobalLock = kernel32.GlobalLock
GlobalLock.restype = ctypes.c_void_p
GlobalLock.argtypes = [ctypes.c_void_p]

GlobalUnlock = kernel32.GlobalUnlock
GlobalUnlock.restype = ctypes.c_long
GlobalUnlock.argtypes = [ctypes.c_void_p]

GlobalFree = kernel32.GlobalFree
GlobalFree.restype = ctypes.c_void_p
GlobalFree.argtypes = [ctypes.c_void_p]

# Shell32 - DragQueryFile
DragQueryFileW = shell32.DragQueryFileW
DragQueryFileW.restype = ctypes.c_uint
DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]

DragFinish = shell32.DragFinish
DragFinish.restype = None
DragFinish.argtypes = [ctypes.c_void_p]

# Shell32 - SHGetFileInfoW for .url files
# We'll just read .url files directly

# ─── Constantes ──────────────────────────────────────────────────────────────
S_OK = 0
S_FALSE = 1
E_NOINTERFACE = 0x80004002
E_FAIL = 0x80004005
DV_E_FORMATETC = 0x80040064
E_UNEXPECTED = 0x8000FFFF

CF_TEXT = 1
CF_UNICODETEXT = 13
CF_HDROP = 15

DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1

MK_LBUTTON = 1
MK_RBUTTON = 2
MK_SHIFT = 4
MK_CONTROL = 8

DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1
DROPEFFECT_MOVE = 2
DROPEFFECT_LINK = 4

GMEM_FIXED = 0
GMEM_MOVEABLE = 2
GMEM_ZEROINIT = 0x40


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRUTURAS COM
# ═══════════════════════════════════════════════════════════════════════════════

class POINTL(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class FORMATETC(ctypes.Structure):
    _fields_ = [
        ("cfFormat", ctypes.c_ushort),
        ("ptd", ctypes.c_void_p),
        ("dwAspect", ctypes.c_ulong),
        ("lindex", ctypes.c_int),
        ("tymed", ctypes.c_ulong),
    ]


class STGMEDIUM(ctypes.Structure):
    _fields_ = [
        ("tymed", ctypes.c_ulong),
        ("hGlobal", ctypes.c_void_p),
        ("pUnkForRelease", ctypes.c_void_p),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# VTABLES COM
# ═══════════════════════════════════════════════════════════════════════════════

class IDataObjectVtbl(ctypes.Structure):
    """Vtable para IDataObject (IUnknown + 7 metodos)."""
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p),
        ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.c_void_p),
        ("GetData", ctypes.c_void_p),
        ("GetDataHere", ctypes.c_void_p),
        ("QueryGetData", ctypes.c_void_p),
        ("GetCanonicalFormatEtc", ctypes.c_void_p),
        ("SetData", ctypes.c_void_p),
        ("EnumFormatEtc", ctypes.c_void_p),
        ("DAdvise", ctypes.c_void_p),
        ("DUnadvise", ctypes.c_void_p),
        ("EnumDAdvise", ctypes.c_void_p),
    ]


class IDropTargetVtbl(ctypes.Structure):
    """Vtable para IDropTarget (IUnknown + DragEnter/DragOver/DragLeave/Drop)."""
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p),
        ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.c_void_p),
        ("DragEnter", ctypes.c_void_p),
        ("DragOver", ctypes.c_void_p),
        ("DragLeave", ctypes.c_void_p),
        ("Drop", ctypes.c_void_p),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# NOSSO OBJETO COM (IDropTarget)
# ═══════════════════════════════════════════════════════════════════════════════

class DropTargetObj(ctypes.Structure):
    """
    Estrutura que representa nosso objeto COM IDropTarget.
    Primeiro campo = ponteiro pra vtable (padrao COM).
    Campos adicionais = dados do Python.
    """
    _fields_ = [
        ("lpVtbl", ctypes.POINTER(IDropTargetVtbl)),
        ("refCount", ctypes.c_ulong),
        ("hwnd", ctypes.c_void_p),
        ("callback_ref", ctypes.py_object),   # Mantem referencia Python viva
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# TIPOS DE FUNCAO PARA CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

# IUnknown
QI_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_long,           # HRESULT
    ctypes.c_void_p,         # this
    ctypes.c_void_p,         # riid (REFIID)
    ctypes.c_void_p,         # ppvObject (void**)
)
ADDREF_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_ulong,          # ULONG
    ctypes.c_void_p,         # this
)

# IDropTarget
DRAGENTER_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_long,           # HRESULT
    ctypes.c_void_p,         # this
    ctypes.c_void_p,         # pDataObj (IDataObject*)
    ctypes.c_ulong,          # grfKeyState
    ctypes.POINTER(POINTL),  # pt
    ctypes.POINTER(ctypes.c_ulong),  # pdwEffect
)
DRAGOVER_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_long,           # HRESULT
    ctypes.c_void_p,         # this
    ctypes.c_ulong,          # grfKeyState
    ctypes.POINTER(POINTL),  # pt
    ctypes.POINTER(ctypes.c_ulong),  # pdwEffect
)
DRAGLEAVE_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_long,           # HRESULT
    ctypes.c_void_p,         # this
)
DROP_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_long,           # HRESULT
    ctypes.c_void_p,         # this
    ctypes.c_void_p,         # pDataObj (IDataObject*)
    ctypes.c_ulong,          # grfKeyState
    ctypes.POINTER(POINTL),  # pt
    ctypes.POINTER(ctypes.c_ulong),  # pdwEffect
)

# IDataObject::GetData
GETDATA_FUNC = ctypes.WINFUNCTYPE(
    ctypes.c_long,           # HRESULT
    ctypes.c_void_p,         # this
    ctypes.POINTER(FORMATETC),  # pFormatetc
    ctypes.POINTER(STGMEDIUM),  # pMedium
)


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS ESTATICOS (COM chama estas funcoes C)
# ═══════════════════════════════════════════════════════════════════════════════

def _query_interface(this_ptr, riid, ppvObject):
    """IUnknown::QueryInterface - retorna IDropTarget se pedido."""
    obj = ctypes.cast(this_ptr, ctypes.POINTER(DropTargetObj))
    # Extrai o IID de IDropTarget (00000122-0000-0000-C000-000000000046)
    # Simplesmente aceitamos IUnknown, IDropTarget, ou NULL
    try:
        iid_bytes = (ctypes.c_byte * 16).from_address(riid)
        # IID_IDropTarget: 00000122-0000-0000-C000-000000000046
        is_drop_target = (
            iid_bytes[0] == 0x22 and iid_bytes[1] == 0x01 and
            iid_bytes[2] == 0x00 and iid_bytes[3] == 0x00 and
            iid_bytes[4] == 0x00 and iid_bytes[5] == 0x00 and
            iid_bytes[6] == 0x00 and iid_bytes[7] == 0x00 and
            iid_bytes[8] == 0xC0 and iid_bytes[9] == 0x00 and
            iid_bytes[10] == 0x00 and iid_bytes[11] == 0x00 and
            iid_bytes[12] == 0x00 and iid_bytes[13] == 0x00 and
            iid_bytes[14] == 0x00 and iid_bytes[15] == 0x46
        )
        is_iunknown = all(b == 0 for b in iid_bytes[1:]) and iid_bytes[0] == 0
        
        if is_drop_target or is_iunknown:
            obj.contents.refCount += 1
            ctypes.memmove(ppvObject, ctypes.byref(this_ptr), ctypes.sizeof(ctypes.c_void_p))
            return S_OK
    except Exception:
        pass
    
    ctypes.memmove(ppvObject, ctypes.byref(ctypes.c_void_p(0)), ctypes.sizeof(ctypes.c_void_p))
    return E_NOINTERFACE


def _add_ref(this_ptr):
    """IUnknown::AddRef."""
    obj = ctypes.cast(this_ptr, ctypes.POINTER(DropTargetObj))
    obj.contents.refCount += 1
    return obj.contents.refCount


def _release(this_ptr):
    """IUnknown::Release."""
    obj = ctypes.cast(this_ptr, ctypes.POINTER(DropTargetObj))
    obj.contents.refCount -= 1
    return obj.contents.refCount


def _drag_enter(this_ptr, pDataObj, grfKeyState, pt, pdwEffect):
    """IDropTarget::DragEnter - aceita o drag se tiver texto."""
    try:
        obj = ctypes.cast(this_ptr, ctypes.POINTER(DropTargetObj))
        handler = obj.contents.callback_ref
        if handler:
            handler._on_drag_enter()
    except Exception:
        pass
    # Aceita copy/move/link effects
    ctypes.memmove(pdwEffect, ctypes.byref(ctypes.c_ulong(DROPEFFECT_COPY)), ctypes.sizeof(ctypes.c_ulong))
    return S_OK


def _drag_over(this_ptr, grfKeyState, pt, pdwEffect):
    """IDropTarget::DragOver."""
    try:
        ctypes.memmove(pdwEffect, ctypes.byref(ctypes.c_ulong(DROPEFFECT_COPY)), ctypes.sizeof(ctypes.c_ulong))
    except Exception:
        pass
    return S_OK


def _drag_leave(this_ptr):
    """IDropTarget::DragLeave."""
    try:
        obj = ctypes.cast(this_ptr, ctypes.POINTER(DropTargetObj))
        handler = obj.contents.callback_ref
        if handler:
            handler._on_drag_leave()
    except Exception:
        pass
    return S_OK


def _drop(this_ptr, pDataObj, grfKeyState, pt, pdwEffect):
    """IDropTarget::Drop - extrai o texto/URL do IDataObject."""
    try:
        obj = ctypes.cast(this_ptr, ctypes.POINTER(DropTargetObj))
        handler = obj.contents.callback_ref
        if not handler:
            return E_UNEXPECTED

        dados = _extrair_dados(pDataObj)
        if dados:
            handler._on_drop(dados)
    except Exception:
        pass
    return S_OK


def _extrair_dados(pDataObj):
    """Tenta extrair texto e arquivos do IDataObject."""
    if not pDataObj:
        return None

    resultados = {
        "text": None,
        "files": [],
    }

    # Tenta CF_UNICODETEXT (URLs do navegador, texto)
    texto = _extrair_cf_unicode(pDataObj)
    if texto:
        resultados["text"] = texto

    # Tenta CF_HDROP (arquivos)
    arquivos = _extrair_cf_hdrop(pDataObj)
    if arquivos:
        resultados["files"] = arquivos

    # Se tem texto, retorna so ele (prioridade maior)
    if resultados["text"]:
        return resultados["text"]

    # Se tem arquivos, tenta extrair URL de arquivos .url
    if resultados["files"]:
        for arquivo in resultados["files"]:
            url = _ler_url_de_arquivo(arquivo)
            if url:
                return url
        return "\n".join(resultados["files"])

    return None


def _extrair_cf_unicode(pDataObj):
    """Extrai texto CF_UNICODETEXT do IDataObject."""
    try:
        fmt = FORMATETC()
        fmt.cfFormat = CF_UNICODETEXT
        fmt.ptd = None
        fmt.dwAspect = DVASPECT_CONTENT
        fmt.lindex = -1
        fmt.tymed = TYMED_HGLOBAL

        med = STGMEDIUM()
        med.tymed = 0
        med.hGlobal = None
        med.pUnkForRelease = None

        vtbl = ctypes.cast(pDataObj, ctypes.POINTER(ctypes.POINTER(IDataObjectVtbl)))
        if not vtbl or not vtbl.contents:
            return None

        get_data = GETDATA_FUNC(vtbl.contents[0].GetData)
        hr = get_data(pDataObj, ctypes.byref(fmt), ctypes.byref(med))

        if hr == S_OK and med.hGlobal:
            ptr = GlobalLock(med.hGlobal)
            if ptr:
                try:
                    # Unicode (wchar_t)
                    texto = ctypes.wstring_at(ptr)
                    if texto:
                        return texto
                finally:
                    GlobalUnlock(med.hGlobal)

            # Libera o STGMEDIUM
            _release_stgmedium(med)

        # Tenta CF_TEXT (ANSI) se Unicode falhou
        if hr != S_OK:
            fmt.cfFormat = CF_TEXT
            hr = get_data(pDataObj, ctypes.byref(fmt), ctypes.byref(med))
            if hr == S_OK and med.hGlobal:
                ptr = GlobalLock(med.hGlobal)
                if ptr:
                    try:
                        texto = ctypes.c_char_p(ptr).value
                        if texto:
                            return texto.decode("utf-8", errors="replace")
                    finally:
                        GlobalUnlock(med.hGlobal)
                _release_stgmedium(med)
    except Exception:
        pass
    return None


def _extrair_cf_hdrop(pDataObj):
    """Extrai lista de arquivos CF_HDROP do IDataObject."""
    try:
        fmt = FORMATETC()
        fmt.cfFormat = CF_HDROP
        fmt.ptd = None
        fmt.dwAspect = DVASPECT_CONTENT
        fmt.lindex = -1
        fmt.tymed = TYMED_HGLOBAL

        med = STGMEDIUM()
        med.tymed = 0
        med.hGlobal = None
        med.pUnkForRelease = None

        vtbl = ctypes.cast(pDataObj, ctypes.POINTER(ctypes.POINTER(IDataObjectVtbl)))
        if not vtbl or not vtbl.contents:
            return None

        get_data = GETDATA_FUNC(vtbl.contents[0].GetData)
        hr = get_data(pDataObj, ctypes.byref(fmt), ctypes.byref(med))

        if hr == S_OK and med.hGlobal:
            try:
                drop_handle = med.hGlobal
                num_arquivos = DragQueryFileW(drop_handle, 0xFFFFFFFF, None, 0)
                arquivos = []
                for i in range(num_arquivos):
                    # Primeiro descobre o tamanho
                    tamanho = DragQueryFileW(drop_handle, i, None, 0)
                    if tamanho > 0:
                        buf = ctypes.create_unicode_buffer(tamanho + 1)
                        DragQueryFileW(drop_handle, i, buf, tamanho + 1)
                        arquivos.append(buf.value)
                return arquivos
            finally:
                DragFinish(drop_handle)
    except Exception:
        pass
    return None


def _release_stgmedium(med):
    """Libera um STGMEDIUM usando ReleaseStgMedium."""
    try:
        RSM = ole32.ReleaseStgMedium
        RSM.restype = None
        RSM.argtypes = [ctypes.POINTER(STGMEDIUM)]
        RSM(ctypes.byref(med))
    except Exception:
        pass


def _ler_url_de_arquivo(caminho):
    """Tenta extrair URL de um arquivo .url."""
    if not caminho or not caminho.lower().endswith(".url"):
        return None
    try:
        with open(caminho, "r", encoding="utf-8", errors="replace") as f:
            for linha in f:
                linha = linha.strip()
                if linha.upper().startswith("URL="):
                    return linha[4:].strip()
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class DropHandler:
    """
    Gerenciador de drag-and-drop via IDropTarget do Windows.
    
    Uso:
        handler = DropHandler(hwnd, on_drop_callback)
        # hwnd = identificador da janela (tk_root.winfo_id())
        # on_drop_callback(data_received) - recebe string com texto/URL
        
        handler.destroy()  # Para limpar
    """

    def __init__(self, hwnd: int, on_drop: Callable[[str], None]):
        """
        Inicializa o handler de drag-and-drop.
        
        Args:
            hwnd: HWND da janela (use root.winfo_id())
            on_drop: Callable que recebe a string soltada (URL ou texto)
        """
        self.hwnd = ctypes.c_void_p(hwnd)
        self.on_drop = on_drop
        self._obj_ptr = None
        self._ativo = False
        self._drag_ativo = False

        self._inicializar()

    def _inicializar(self):
        """Inicializa COM e registra o drop target."""
        try:
            # Inicializa COM
            hr = OleInitialize(None)
            if hr not in (S_OK, S_FALSE):
                return  # COM ja inicializado ou falhou

            # Cria nosso objeto COM IDropTarget
            obj = DropTargetObj()
            obj.refCount = 1
            obj.callback_ref = self

            # Cria a vtable
            vtbl = IDropTargetVtbl()
            vtbl.QueryInterface = QI_FUNC(_query_interface)
            vtbl.AddRef = ADDREF_FUNC(_add_ref)
            vtbl.Release = ADDREF_FUNC(_release)
            vtbl.DragEnter = DRAGENTER_FUNC(_drag_enter)
            vtbl.DragOver = DRAGOVER_FUNC(_drag_over)
            vtbl.DragLeave = DRAGLEAVE_FUNC(_drag_leave)
            vtbl.Drop = DROP_FUNC(_drop)

            # Aloca e copia vtable (precisa ser memoria viva)
            vtbl_ptr = ctypes.pointer(vtbl)
            obj.lpVtbl = vtbl_ptr

            # Aloca o objeto em memoria (como COM object)
            self._obj_ptr = ctypes.pointer(obj)

            # Registra como drop target
            hr = RegisterDragDrop(self.hwnd, self._obj_ptr)
            if hr == S_OK:
                self._ativo = True
        except Exception:
            self._ativo = False

    def destroy(self):
        """Remove o drop target e finaliza COM."""
        try:
            if self._ativo:
                RevokeDragDrop(self.hwnd)
                self._ativo = False
        except Exception:
            pass
        try:
            OleUninitialize()
        except Exception:
            pass

    @property
    def drag_ativo(self) -> bool:
        """Retorna True se um drag esta em andamento sobre a janela."""
        return self._drag_ativo

    def _on_drag_enter(self):
        """Chamado quando um drag entra na janela."""
        self._drag_ativo = True

    def _on_drag_leave(self):
        """Chamado quando um drag sai da janela."""
        self._drag_ativo = False

    def _on_drop(self, dados: str):
        """Chamado quando algo e soltado na janela."""
        self._drag_ativo = False
        if dados and self.on_drop:
            # Limpa e normaliza
            dados = dados.strip().strip('"').strip("'")
            if dados:
                self.on_drop(dados)

    def __del__(self):
        """Limpeza na destruicao."""
        try:
            self.destroy()
        except Exception:
            pass
