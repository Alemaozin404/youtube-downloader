#!/usr/bin/env python3
"""
Modelos Pydantic do servidor de atualizacoes.
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class ArquivoPlataforma(BaseModel):
    """Informacoes de um binario/instalador para uma plataforma."""

    url: str = ""
    sha256: str = ""
    size: int = 0
    filename: str = ""
    signature: str = ""  # Assinatura Ed25519 (base64) do digest sha256


class RegistroRelease(BaseModel):
    """Payload de registro de uma release (endpoint administrativo)."""

    version: str
    min_required_version: str = "1.0"
    published_at: str = ""
    notes: str = ""
    release_page: str = ""
    mandatory: bool = False
    platforms: Dict[str, ArquivoPlataforma] = Field(default_factory=dict)


class CheckAtualizacao(BaseModel):
    """Resposta do endpoint /api/update/check."""

    update_available: bool
    app: str
    current_version: str
    latest_version: Optional[str] = None
    mandatory: bool = False
    min_required_version: Optional[str] = None
    published_at: Optional[str] = None
    notes: Optional[str] = None
    release_page: Optional[str] = None
    platform: Optional[ArquivoPlataforma] = None
