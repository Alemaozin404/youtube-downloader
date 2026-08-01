#!/usr/bin/env python3
"""
Testes unitarios do modulo updater.py (sistema de atualizacao).
Usa apenas unittest e urllib, sem dependencias externas.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import updater  # noqa: E402
from updater import (  # noqa: E402
    APP_VERSION,
    AtualizacaoInfo,
    baixar_instalador,
    calcular_sha256,
    caminho_instalador_temp,
    comparar_versoes,
    executar_instalador,
    verificar_atualizacao,
    verificar_sha256,
)


class TestCompararVersoes(unittest.TestCase):
    """Testes de comparacao de versoes."""

    def test_igualdade(self):
        self.assertEqual(comparar_versoes("1.0", "1.0"), 0)
        self.assertEqual(comparar_versoes("1.2.3", "1.2.3"), 0)

    def test_maior(self):
        self.assertEqual(comparar_versoes("1.1", "1.0"), 1)
        self.assertEqual(comparar_versoes("1.10", "1.9"), 1)
        self.assertEqual(comparar_versoes("2.0", "1.9.9"), 1)
        self.assertEqual(comparar_versoes("1.0.1", "1.0.0"), 1)

    def test_menor(self):
        self.assertEqual(comparar_versoes("1.0", "1.1"), -1)
        self.assertEqual(comparar_versoes("0.9", "1.0"), -1)

    def test_versoes_desiguais_no_comprimento(self):
        self.assertEqual(comparar_versoes("1.0", "1.0.0"), 0)
        self.assertEqual(comparar_versoes("1.2", "1.2.1"), -1)

    def test_sufixos(self):
        # Pre-release (sufixo) conta como menor que a versao final
        self.assertEqual(comparar_versoes("1.0-beta", "1.0"), -1)
        self.assertEqual(comparar_versoes("1.0", "1.0-beta"), 1)


class TestVerificarAtualizacao(unittest.TestCase):
    """Testes da consulta ao servidor."""

    def _mock_urlopen(self, payload):
        class FakeResp:
            def __init__(self, data):
                self._data = data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(self._data).encode("utf-8")

        return mock.patch(
            "urllib.request.urlopen", return_value=FakeResp(payload)
        )

    def test_sem_atualizacao(self):
        payload = {
            "update_available": False,
            "app": "YouTube Downloader",
            "current_version": "1.0",
            "latest_version": "1.0",
        }
        with self._mock_urlopen(payload):
            info = verificar_atualizacao("https://exemplo.com", "1.0")
        self.assertIsNone(info)

    def test_com_atualizacao(self):
        payload = {
            "update_available": True,
            "app": "YouTube Downloader",
            "current_version": "1.0",
            "latest_version": "1.1",
            "min_required_version": "1.0",
            "published_at": "2026-08-01T00:00:00",
            "notes": "Correcoes de bugs",
            "release_page": "https://github.com/user/repo/releases/v1.1",
            "platform": {
                "url": "https://exemplo.com/Setup-1.1.exe",
                "sha256": "abc123",
                "size": 12345,
                "filename": "Setup-1.1.exe",
            },
        }
        with self._mock_urlopen(payload):
            info = verificar_atualizacao("https://exemplo.com", "1.0", "windows")
        self.assertIsInstance(info, AtualizacaoInfo)
        self.assertEqual(info.version, "1.1")
        self.assertEqual(info.notes, "Correcoes de bugs")
        self.assertEqual(info.platform.url, "https://exemplo.com/Setup-1.1.exe")
        self.assertEqual(info.platform.sha256, "abc123")
        self.assertEqual(info.release_page, "https://github.com/user/repo/releases/v1.1")

    def test_url_build(self):
        """Verifica que a URL consultada contem versao e plataforma."""
        payload = {"update_available": False, "app": "X", "current_version": "1.0"}
        with self._mock_urlopen(payload) as m:
            verificar_atualizacao("https://exemplo.com/base/", "1.2", "windows")
        req = m.call_args[0][0]
        url = req.full_url if hasattr(req, "full_url") else str(req)
        self.assertIn("/api/update/check", url)
        self.assertIn("current_version=1.2", url)
        self.assertIn("platform=windows", url)


class TestSha256(unittest.TestCase):
    """Testes de verificacao de integridade."""

    def test_calcular_e_verificar(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            f.write(b"conteudo de teste")
            caminho = f.name
        try:
            esperado = hashlib.sha256(b"conteudo de teste").hexdigest()
            self.assertEqual(calcular_sha256(caminho), esperado)
            self.assertTrue(verificar_sha256(caminho, esperado))
            self.assertFalse(verificar_sha256(caminho, "0000"))
            # Sem hash esperado, considera ok
            self.assertTrue(verificar_sha256(caminho, ""))
        finally:
            os.unlink(caminho)

    def test_caminho_temp(self):
        p = caminho_instalador_temp("1.1")
        self.assertIn("YouTube-Downloader-Setup-1.1.exe", p)
        Path(p).parent.mkdir(parents=True, exist_ok=True)


class TestBaixarInstalador(unittest.TestCase):
    """Testes de download com urlopen mockado."""

    def test_download(self):
        destino = Path(tempfile.gettempdir()) / "updater_teste_destino.txt"
        destino.unlink(missing_ok=True)

        class FakeResp:
            headers = {"Content-Length": "5"}

            def __init__(self):
                self._chamadas = 0

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, n=-1):
                self._chamadas += 1
                return b"dados" if self._chamadas == 1 else b""

        try:
            with mock.patch("urllib.request.urlopen", return_value=FakeResp()) as m:
                ret = baixar_instalador("https://exemplo.com/setup.exe", str(destino))
            self.assertEqual(ret, str(destino))
            self.assertTrue(destino.exists())
            self.assertEqual(destino.read_text(encoding="utf-8"), "dados")
            req = m.call_args[0][0]
            self.assertIsInstance(req, urllib.request.Request)
        finally:
            destino.unlink(missing_ok=True)

    def test_download_timeout_passthrough(self):
        """O timeout deve ser repassado ao urlopen (nao mais ignorado)."""
        destino = Path(tempfile.gettempdir()) / "updater_teste_timeout.txt"
        destino.unlink(missing_ok=True)

        class FakeResp:
            headers = {"Content-Length": "0"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, n=-1):
                return b""

        try:
            with mock.patch("urllib.request.urlopen", return_value=FakeResp()) as m:
                baixar_instalador("https://exemplo.com/setup.exe", str(destino), timeout=42)
            self.assertEqual(m.call_args[1]["timeout"], 42)
        finally:
            destino.unlink(missing_ok=True)


class TestExecutarInstalador(unittest.TestCase):
    """Testes de execucao do instalador."""

    def test_arquivo_inexistente(self):
        self.assertFalse(executar_instalador("/caminho/inexistente/arquivo.exe"))


if __name__ == "__main__":
    unittest.main()
