#!/usr/bin/env python3
"""
Testes da logica pura do pipeline release.py
(validacao de versao, deteccao do ISCC, parse do git remote, sha256, nome do instalador).
Nao executa build nem faz requisicoes de rede.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import release  # noqa: E402
from release import (  # noqa: E402
    encontrar_iscc,
    localizar_instalador,
    repo_do_git,
    sha256_arquivo,
    validar_versao,
)


class TestValidarVersao(unittest.TestCase):
    def test_versoes_validas(self):
        for v in ["1.0", "1.1", "1.2.3", "1.2.3-beta", "2.10.0-rc1"]:
            self.assertTrue(validar_versao(v), f"{v} deveria ser valida")

    def test_versoes_invalidas(self):
        for v in ["", "v1.0", "1", "abc", "1.2.3.4", "1.2.x", "1..2"]:
            self.assertFalse(validar_versao(v), f"{v} nao deveria ser valida")


class TestLocalizarInstalador(unittest.TestCase):
    def test_nome_do_instalador(self):
        p = localizar_instalador("1.1.0")
        self.assertEqual(p.name, "YouTube-Downloader-Setup-1.1.0.exe")
        self.assertEqual(p.parent.name, "installer")


class TestEncontrarIscc(unittest.TestCase):
    def test_env_iscc(self):
        """Se ISCC estiver no ambiente, deve retornar esse caminho se existir."""
        old = os.environ.get("ISCC")
        os.environ["ISCC"] = "/caminho/inexistente/ISCC.exe"
        try:
            # Caminho inexistente: nao deve retornar o env
            self.assertNotEqual(encontrar_iscc(), "/caminho/inexistente/ISCC.exe")
        finally:
            if old is None:
                os.environ.pop("ISCC", None)
            else:
                os.environ["ISCC"] = old

    def test_retorna_none_sem_iscc(self):
        """Sem ISCC no ambiente nem nos caminhos padrao, retorna None."""
        old = os.environ.get("ISCC")
        os.environ.pop("ISCC", None)
        try:
            # Em maquinas sem Inno Setup, pode retornar None
            # (no Windows com Inno Setup instalado, retorna o caminho)
            resultado = encontrar_iscc()
            self.assertIsNone(resultado) if resultado is None else self.assertTrue(
                resultado.lower().endswith("iscc.exe")
            )
        finally:
            if old is not None:
                os.environ["ISCC"] = old


class TestRepoDoGit(unittest.TestCase):
    def test_repo_sem_git(self):
        """Se nao houver git remote origin, retorna string vazia."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            self.assertEqual(repo_do_git(), "")
        finally:
            os.chdir(old_cwd)


class TestSha256(unittest.TestCase):
    def test_sha256_arquivo(self):
        import hashlib

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"dados de teste do release")
            caminho = f.name
        try:
            esperado = hashlib.sha256(b"dados de teste do release").hexdigest()
            self.assertEqual(sha256_arquivo(caminho), esperado)
        finally:
            os.unlink(caminho)


if __name__ == "__main__":
    unittest.main()
