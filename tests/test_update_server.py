#!/usr/bin/env python3
"""
Testes do servidor de atualizacoes (server/).

- Testes de logica (ReleaseManager, comparacao) rodam sem dependencias extras,
  exigindo apenas pydantic (instalado junto com fastapi).
- Testes de API (endpoints HTTP) exigem fastapi + httpx (TestClient).
  Se nao estiverem disponiveis, os testes de API sao pulados automaticamente.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from server.release_manager import ReleaseManager, comparar_versoes as comparar_srv
    HAS_SERVER_CORE = True
except Exception:
    HAS_SERVER_CORE = False

try:
    from fastapi.testclient import TestClient
    from server.app import app
    HAS_TESTCLIENT = True
except Exception:
    HAS_TESTCLIENT = False


def _payload_versao(versao="1.1.0"):
    return {
        "version": versao,
        "min_required_version": "1.0",
        "published_at": "2026-08-01T00:00:00",
        "notes": "Notas de teste",
        "release_page": "https://github.com/user/repo/releases/v" + versao,
        "mandatory": False,
        "platforms": {
            "windows": {
                "url": "https://github.com/user/repo/releases/download/v"
                + versao
                + "/YouTube-Downloader-Setup-"
                + versao
                + ".exe",
                "sha256": "abc123",
                "size": 12345,
                "filename": "Setup-" + versao + ".exe",
            }
        },
    }


def _manager_tmp():
    """Cria um ReleaseManager isolado em pasta temporaria."""
    tmpdir = Path(tempfile.mkdtemp(prefix="updatesrv_"))
    return ReleaseManager(tmpdir / "releases.json"), tmpdir


# ─── Logica do servidor (sem httpx) ─────────────────────────────────────────

@unittest.skipUnless(HAS_SERVER_CORE, "pydantic/fastapi nao instalados (dependencias do servidor)")
class TestCompararVersoesServidor(unittest.TestCase):
    """Testes do comparador de versoes do servidor."""

    def test_comparacoes(self):
        self.assertEqual(comparar_srv("1.0", "1.0"), 0)
        self.assertEqual(comparar_srv("1.0", "1.0.0"), 0)
        self.assertEqual(comparar_srv("1.2.0", "1.1.9"), 1)
        self.assertEqual(comparar_srv("1.1", "1.2"), -1)
        self.assertEqual(comparar_srv("2.0", "1.9.9"), 1)
        self.assertEqual(comparar_srv("1.0-beta", "1.0"), -1)


@unittest.skipUnless(HAS_SERVER_CORE, "pydantic/fastapi nao instalados (dependencias do servidor)")
class TestReleaseManager(unittest.TestCase):
    """Testes do gerenciador de releases (sem HTTP)."""

    def setUp(self):
        self.manager, self.tmpdir = _manager_tmp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_registrar_e_mais_recente(self):
        self.manager.registrar(_payload_versao("1.0.0"))
        self.manager.registrar(_payload_versao("1.1.0"))
        self.manager.registrar(_payload_versao("1.0.5"))
        self.assertEqual(self.manager.mais_recente()["version"], "1.1.0")
        versoes = [r["version"] for r in self.manager.listar()]
        self.assertEqual(versoes, ["1.1.0", "1.0.5", "1.0.0"])

    def test_substituir_mesma_versao(self):
        self.manager.registrar(_payload_versao("1.1.0"))
        p = _payload_versao("1.1.0")
        p["notes"] = "Atualizado"
        self.manager.registrar(p)
        self.assertEqual(self.manager.listar().__len__(), 1)
        self.assertEqual(self.manager.mais_recente()["notes"], "Atualizado")

    def test_persistencia(self):
        arquivo = self.tmpdir / "releases.json"
        self.manager.registrar(_payload_versao("1.0.0"))
        # Nova instancia le o mesmo arquivo
        outro = ReleaseManager(arquivo)
        self.assertEqual(outro.mais_recente()["version"], "1.0.0")

    def test_remover(self):
        self.manager.registrar(_payload_versao("1.0.0"))
        self.assertTrue(self.manager.remover("1.0.0"))
        self.assertFalse(self.manager.remover("1.0.0"))
        self.assertIsNone(self.manager.mais_recente())


# ─── API do servidor (exige httpx/TestClient) ───────────────────────────────

@unittest.skipUnless(HAS_TESTCLIENT, "fastapi/httpx nao instalados (dependencias do servidor)")
class TestServidorAtualizacoes(unittest.TestCase):
    """Testes dos endpoints HTTP do servidor."""

    @classmethod
    def setUpClass(cls):
        cls.old_env = os.environ.get("RELEASES_FILE")
        cls.old_token = os.environ.get("ADMIN_TOKEN")
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="updatesrv_"))
        os.environ["RELEASES_FILE"] = str(cls.tmpdir / "releases.json")
        os.environ["ADMIN_TOKEN"] = "token-teste"
        import server.app as server_app
        server_app.manager = ReleaseManager(cls.tmpdir / "releases.json")
        cls.client = TestClient(server_app.app)

    @classmethod
    def tearDownClass(cls):
        if cls.old_env is None:
            os.environ.pop("RELEASES_FILE", None)
        else:
            os.environ["RELEASES_FILE"] = cls.old_env
        if cls.old_token is None:
            os.environ.pop("ADMIN_TOKEN", None)
        else:
            os.environ["ADMIN_TOKEN"] = cls.old_token
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        import server.app as server_app
        arquivo = self.tmpdir / "releases.json"
        if arquivo.exists():
            arquivo.unlink()
        server_app.manager = ReleaseManager(arquivo)

    # ─── Endpoints publicos ────────────────────────────────────────────────

    def test_raiz_sem_releases(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")
        self.assertIsNone(r.json()["latest_version"])

    def test_latest_404_sem_releases(self):
        self.assertEqual(self.client.get("/api/latest").status_code, 404)

    def test_check_sem_releases(self):
        r = self.client.get("/api/update/check", params={"current_version": "1.0"})
        self.assertFalse(r.json()["update_available"])

    # ─── Endpoints admin ───────────────────────────────────────────────────

    def test_registrar_requer_token(self):
        r = self.client.post("/api/releases", json=_payload_versao())
        self.assertEqual(r.status_code, 401)

    def test_registrar_com_token(self):
        r = self.client.post(
            "/api/releases",
            json=_payload_versao(),
            headers={"Authorization": "Bearer token-teste"},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["version"], "1.1.0")
        self.assertEqual(r.json()["total"], 1)

    def test_registrar_sem_token_env(self):
        old = os.environ.get("ADMIN_TOKEN")
        os.environ.pop("ADMIN_TOKEN", None)
        try:
            r = self.client.post("/api/releases", json=_payload_versao())
            self.assertEqual(r.status_code, 503)
        finally:
            if old:
                os.environ["ADMIN_TOKEN"] = old

    # ─── Fluxo completo ────────────────────────────────────────────────────

    def test_fluxo_completo(self):
        self.client.post(
            "/api/releases",
            json=_payload_versao("1.2.0"),
            headers={"Authorization": "Bearer token-teste"},
        )

        # App desatualizado -> atualizacao disponivel
        r = self.client.get(
            "/api/update/check",
            params={"current_version": "1.0", "platform": "windows"},
        )
        dados = r.json()
        self.assertTrue(dados["update_available"])
        self.assertEqual(dados["latest_version"], "1.2.0")
        self.assertEqual(dados["platform"]["filename"], "Setup-1.2.0.exe")

        # App atualizado -> sem atualizacao
        r = self.client.get(
            "/api/update/check",
            params={"current_version": "1.2.0", "platform": "windows"},
        )
        self.assertFalse(r.json()["update_available"])

        # App mais novo que a release -> sem atualizacao
        r = self.client.get(
            "/api/update/check",
            params={"current_version": "2.0", "platform": "windows"},
        )
        self.assertFalse(r.json()["update_available"])

        # Plataforma sem binario -> update disponivel mas sem platform
        r = self.client.get(
            "/api/update/check",
            params={"current_version": "1.0", "platform": "linux"},
        )
        self.assertTrue(r.json()["update_available"])
        self.assertIsNone(r.json()["platform"])


if __name__ == "__main__":
    unittest.main()
