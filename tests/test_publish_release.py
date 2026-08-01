#!/usr/bin/env python3
"""
Testes da persistencia local do manifest (publish_release.py).

Apos publicar, o publish_release.py grava a release em server/releases.json
no repositorio local. No plano free da Render o disco e efemero, entao esse
arquivo commitado e a fonte duravel do manifest (a Render redeploya sozinha
no push e restaura o arquivo).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from publish_release import atualizar_manifest_local, commit_push_manifest
    HAS_PUBLISH = True
except Exception:
    HAS_PUBLISH = False


def _payload(versao="1.1.0"):
    return {
        "version": versao,
        "min_required_version": "1.0",
        "published_at": "2026-08-01T00:00:00",
        "notes": "Notas de teste",
        "release_page": "",
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


@unittest.skipUnless(HAS_PUBLISH, "publish_release.py nao importavel")
class TestManifestLocal(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="pubrel_"))
        self.manifest = self.tmpdir / "releases.json"
        # Manifest inicial vazio (mesmo formato do server/releases.json)
        self.manifest.write_text(
            json.dumps({"app": "YouTube Downloader", "releases": []}),
            encoding="utf-8",
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_grava_release_no_manifest(self):
        ok = atualizar_manifest_local(_payload("1.1.0"), self.manifest)
        self.assertTrue(ok)
        dados = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(len(dados["releases"]), 1)
        self.assertEqual(dados["releases"][0]["version"], "1.1.0")

    def test_ordena_por_versao(self):
        atualizar_manifest_local(_payload("1.0.0"), self.manifest)
        atualizar_manifest_local(_payload("1.1.0"), self.manifest)
        atualizar_manifest_local(_payload("1.0.5"), self.manifest)
        dados = json.loads(self.manifest.read_text(encoding="utf-8"))
        versoes = [r["version"] for r in dados["releases"]]
        self.assertEqual(versoes, ["1.1.0", "1.0.5", "1.0.0"])

    def test_substitui_mesma_versao(self):
        atualizar_manifest_local(_payload("1.1.0"), self.manifest)
        p = _payload("1.1.0")
        p["notes"] = "Atualizado"
        atualizar_manifest_local(p, self.manifest)
        dados = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(len(dados["releases"]), 1)
        self.assertEqual(dados["releases"][0]["notes"], "Atualizado")

    def test_commit_sem_git_retorna_false(self):
        """Sem repositorio git, commit_push_manifest deve retornar False sem erro."""
        with mock.patch("subprocess.run",
                        side_effect=FileNotFoundError("git nao instalado")):
            self.assertFalse(commit_push_manifest("1.1.0", self.manifest))

    def test_commit_com_push_falho_retorna_false(self):
        """Commit ok mas push falha: retorna False e instrui apenas o push."""
        import subprocess as sp

        def _fake_run(cmd, **kwargs):
            if cmd[:2] == ["git", "push"]:
                raise sp.CalledProcessError(1, cmd)
            if cmd[:2] == ["git", "diff"]:
                return mock.Mock(returncode=1)  # ha mudancas staged
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=_fake_run):
            self.assertFalse(commit_push_manifest("1.1.0", self.manifest))

    def test_commit_nada_a_commitar_retorna_true(self):
        """Sem mudancas staged (republish identico): sucesso sem commit/push."""
        def _fake_run(cmd, **kwargs):
            if cmd[:2] == ["git", "diff"]:
                return mock.Mock(returncode=0)  # nada staged
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=_fake_run) as m:
            self.assertTrue(commit_push_manifest("1.1.0", self.manifest))
        # Nao deve chamar commit nem push
        chamadas = [c.args[0] for c in m.call_args_list if c.args]
        self.assertFalse(any(c[:2] == ["git", "commit"] for c in chamadas))
        self.assertFalse(any(c[:2] == ["git", "push"] for c in chamadas))


if __name__ == "__main__":
    unittest.main()
