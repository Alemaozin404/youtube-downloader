#!/usr/bin/env python3
"""
Gerenciador de releases do servidor de atualizacoes.

Armazena as versoes publicadas em um arquivo JSON (server/releases.json).
Como a Render (plano free) tem disco efemero, o recomendado e que os
binarios (.exe) fiquem no GitHub Releases e aqui apenas o manifest JSON.
"""

import json
import re
from functools import cmp_to_key
from pathlib import Path
from typing import Dict, List, Optional

DATA_FILE = Path(__file__).parent / "releases.json"

# Regex simples de versao: 1.2.3, 1.2, 1.2.3-beta1 etc.
_VERSAO_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-.]?([a-zA-Z0-9]+))?")


def comparar_versoes(a: str, b: str) -> int:
    """Compara duas strings de versao. Retorna -1, 0 ou 1.

    Ex.: comparar_versoes("1.2.0", "1.1.9") -> 1
    """
    pa = _VERSAO_RE.match(a or "0")
    pb = _VERSAO_RE.match(b or "0")
    va = [int(g or 0) for g in pa.groups()[:3]]
    vb = [int(g or 0) for g in pb.groups()[:3]]
    for x, y in zip(va, vb):
        if x != y:
            return 1 if x > y else -1
    # Pre-release: versao com sufixo conta como menor
    sa = pa.group(4) or ""
    sb = pb.group(4) or ""
    if bool(sa) != bool(sb):
        return -1 if sa else 1
    if sa != sb:
        return 1 if sa > sb else -1
    return 0


class ReleaseManager:
    """Carrega e salva o manifest de releases em JSON."""

    def __init__(self, data_file: Path = DATA_FILE):
        self.data_file = Path(data_file)
        self.releases: List[dict] = []
        self._carregar()

    def _carregar(self):
        self.releases = []
        if self.data_file.exists():
            try:
                dados = json.loads(self.data_file.read_text(encoding="utf-8"))
                self.releases = dados.get("releases", [])
            except (json.JSONDecodeError, OSError):
                self.releases = []
        self._ordenar()

    def _salvar(self):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        dados = {"app": "YouTube Downloader", "releases": self.releases}
        self.data_file.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ─── Consultas ──────────────────────────────────────────────────────────

    def listar(self) -> List[dict]:
        return list(self.releases)

    def obter(self, versao: str) -> Optional[dict]:
        for r in self.releases:
            if r.get("version") == versao:
                return r
        return None

    def mais_recente(self) -> Optional[dict]:
        if not self.releases:
            return None
        return self.releases[0]

    # ─── Escrita ────────────────────────────────────────────────────────────

    def registrar(self, release: Dict) -> dict:
        """Registra ou substitui uma release (dict). Retorna o dict salvo."""
        versao = release.get("version")
        self.releases = [r for r in self.releases if r.get("version") != versao]
        self.releases.append(release)
        self._ordenar()
        self._salvar()
        return release

    def _ordenar(self):
        """Ordena as releases da mais recente para a mais antiga."""
        self.releases.sort(
            key=cmp_to_key(lambda a, b: comparar_versoes(a.get("version", "0"), b.get("version", "0"))),
            reverse=True,
        )

    def remover(self, versao: str) -> bool:
        antes = len(self.releases)
        self.releases = [r for r in self.releases if r.get("version") != versao]
        if len(self.releases) != antes:
            self._salvar()
            return True
        return False
