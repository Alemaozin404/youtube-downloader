#!/usr/bin/env python3
"""
Testes da resolucao da URL do servidor de atualizacoes (config_manager.py).

A URL e resolvida nesta ordem:
  1. Variavel de ambiente UPDATE_URL
  2. config.json -> chave update_url (se nao for placeholder)
  3. Padrao updater.UPDATE_URL
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import config_manager
from config_manager import ConfigManager


class TestGetUpdateUrl(unittest.TestCase):
    """Testes da resolucao da URL sem tocar no config real do usuario."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="cfg_test_"))
        self.patch_dir = mock.patch.object(config_manager, "CONFIG_DIR", self.tmpdir)
        self.patch_file = mock.patch.object(config_manager, "CONFIG_FILE",
                                            self.tmpdir / "config.json")
        self.patch_dir.start()
        self.patch_file.start()
        self.addCleanup(self.patch_dir.stop)
        self.addCleanup(self.patch_file.stop)
        self.old_env = os.environ.get("UPDATE_URL")

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("UPDATE_URL", None)
        else:
            os.environ["UPDATE_URL"] = self.old_env
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_env_var_tem_prioridade(self):
        os.environ["UPDATE_URL"] = "https://env.onrender.com"
        cfg = ConfigManager()
        cfg.config["update_url"] = "https://config.onrender.com"
        self.assertEqual(cfg.get_update_url(), "https://env.onrender.com")

    def test_config_json_usado_sem_env(self):
        os.environ.pop("UPDATE_URL", None)
        cfg = ConfigManager()
        cfg.config["update_url"] = "https://config.onrender.com"
        self.assertEqual(cfg.get_update_url(), "https://config.onrender.com")

    def test_placeholder_cai_no_padrao(self):
        os.environ.pop("UPDATE_URL", None)
        cfg = ConfigManager()
        cfg.config["update_url"] = "https://SEU-SERVIDOR.onrender.com"
        import updater
        self.assertEqual(cfg.get_update_url(), updater.UPDATE_URL)

    def test_sem_config_usa_padrao(self):
        os.environ.pop("UPDATE_URL", None)
        cfg = ConfigManager()
        cfg.config.pop("update_url", None)
        import updater
        self.assertEqual(cfg.get_update_url(), updater.UPDATE_URL)


if __name__ == "__main__":
    unittest.main()
