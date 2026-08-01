"""Testes unitarios para o modulo downloader.py (motor compartilhado)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import downloader

QUALIDADES = ["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]


# ─── formatar_duracao ────────────────────────────────────────────────────────


class TestFormatarDuracao(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(downloader.formatar_duracao(0), "0min 00s")

    def test_menos_de_um_minuto(self):
        self.assertEqual(downloader.formatar_duracao(59), "0min 59s")

    def test_um_minuto(self):
        self.assertEqual(downloader.formatar_duracao(60), "1min 00s")

    def test_uma_hora(self):
        self.assertEqual(downloader.formatar_duracao(3600), "1h 00min 00s")

    def test_hora_minuto_segundo(self):
        self.assertEqual(downloader.formatar_duracao(3661), "1h 01min 01s")

    def test_duas_horas(self):
        self.assertEqual(downloader.formatar_duracao(7200), "2h 00min 00s")

    def test_quase_uma_hora(self):
        self.assertEqual(downloader.formatar_duracao(3599), "59min 59s")

    def test_float_e_arredondado(self):
        self.assertEqual(downloader.formatar_duracao(90.5), "1min 30s")


# ─── _mapa_qualidade ─────────────────────────────────────────────────────────


class TestMapaQualidade(unittest.TestCase):
    def test_todas_qualidades_presentes(self):
        for formato in ("mp4", "webm", "mkv"):
            chaves = set(downloader._mapa_qualidade(formato).keys())
            self.assertEqual(chaves, set(QUALIDADES), f"formato={formato}")

    def test_mp4_best(self):
        valor = downloader._mapa_qualidade("mp4")["best"]
        self.assertIn("bestvideo[ext=mp4]+bestaudio[ext=m4a]", valor)

    def test_webm_best(self):
        valor = downloader._mapa_qualidade("webm")["best"]
        self.assertIn("bestvideo[ext=webm]+bestaudio[ext=webm]", valor)

    def test_mkv_best(self):
        self.assertEqual(downloader._mapa_qualidade("mkv")["best"],
                         "bestvideo+bestaudio/best")

    def test_filtro_de_altura(self):
        valor = downloader._mapa_qualidade("mp4")["1080p"]
        self.assertIn("height<=1080", valor)

    def test_formato_desconhecido_usa_padrao_mkv(self):
        self.assertEqual(downloader._mapa_qualidade("avi"),
                         downloader._mapa_qualidade("mkv"))


# ─── montar_comando_download ─────────────────────────────────────────────────


class TestMontarComandoDownload(unittest.TestCase):
    def setUp(self):
        # Garante determinismo: fixa a invocacao do yt-dlp independente do PATH
        patcher = mock.patch("downloader.localizar_ytdlp", return_value=["yt-dlp"])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_base(self):
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "mp4")
        self.assertEqual(cmd[0], "yt-dlp")
        for flag in ("--no-warnings", "--progress", "--no-playlist", "-o"):
            self.assertIn(flag, cmd)
        idx = cmd.index("-o")
        self.assertTrue(cmd[idx + 1].endswith("%(title)s.%(ext)s"))
        padrao = Path.home() / "Downloads" / "YouTube Downloads"
        self.assertTrue(cmd[idx + 1].startswith(str(padrao)))

    def test_diretorio_personalizado(self):
        diretorio = Path("C:/Meus Downloads")
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", diretorio=diretorio)
        idx = cmd.index("-o")
        # Prefixo derivado do Path (portavel em Windows/Linux)
        self.assertTrue(cmd[idx + 1].startswith(str(diretorio)))

    def test_mp3(self):
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "mp3")
        for flag in ("-x", "--audio-format", "mp3", "--audio-quality", "0",
                     "--embed-thumbnail", "--add-metadata"):
            self.assertIn(flag, cmd)
        # Audio nao usa -f
        self.assertNotIn("-f", cmd)

    def test_mp4_inclui_formato_e_merge(self):
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "mp4")
        idx = cmd.index("-f")
        self.assertEqual(cmd[idx + 1],
                         downloader._mapa_qualidade("mp4")["best"])
        self.assertEqual(cmd[cmd.index("--merge-output-format") + 1], "mp4")

    def test_qualidade_personalizada(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", qualidade="1080p")
        idx = cmd.index("-f")
        self.assertIn("height<=1080", cmd[idx + 1])

    def test_qualidade_invalida_cai_no_best(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", qualidade="ultra-4k-absurdo")
        idx = cmd.index("-f")
        self.assertEqual(cmd[idx + 1], downloader._mapa_qualidade("mp4")["best"])

    def test_webm_merge(self):
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "webm")
        self.assertEqual(cmd[cmd.index("--merge-output-format") + 1], "webm")

    def test_mkv_merge(self):
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "mkv")
        self.assertEqual(cmd[cmd.index("--merge-output-format") + 1], "mkv")

    def test_playlist_intervalo(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", playlist_start=2, playlist_end=5)
        self.assertNotIn("--no-playlist", cmd)
        self.assertEqual(cmd[cmd.index("--playlist-start") + 1], "2")
        self.assertEqual(cmd[cmd.index("--playlist-end") + 1], "5")

    def test_playlist_apenas_inicio(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", playlist_start=3)
        self.assertNotIn("--no-playlist", cmd)
        self.assertIn("--playlist-start", cmd)
        self.assertNotIn("--playlist-end", cmd)

    def test_legendas(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", subs=True, subs_idioma="pt")
        for flag in ("--write-subs", "--sub-langs", "pt", "--sub-format", "srt",
                     "--convert-subs", "srt"):
            self.assertIn(flag, cmd)
        self.assertNotIn("--write-auto-subs", cmd)

    def test_legendas_auto(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", subs=True, subs_auto=True)
        self.assertIn("--write-auto-subs", cmd)

    def test_cookies(self):
        cmd = downloader.montar_comando_download(
            "https://youtu.be/abc", "mp4", navegador_cookies="chrome")
        self.assertEqual(cmd[cmd.index("--cookies-from-browser") + 1], "chrome")

    def test_sem_cookies_quando_none(self):
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "mp4")
        self.assertNotIn("--cookies-from-browser", cmd)

    def test_formato_nao_suportado_sem_f_ou_merge(self):
        # Container desconhecido cai no caminho padrao (sem -f nem merge)
        cmd = downloader.montar_comando_download("https://youtu.be/abc", "avi")
        self.assertNotIn("-f", cmd)
        self.assertNotIn("--merge-output-format", cmd)


# ─── localizar_ytdlp / verificacoes de ambiente ──────────────────────────────


class TestLocalizarYtdlp(unittest.TestCase):
    def test_prioriza_executavel_no_path(self):
        with mock.patch("downloader.shutil.which", return_value="C:/yt-dlp.exe"):
            self.assertEqual(downloader.localizar_ytdlp(), ["yt-dlp"])

    def test_fallback_para_modulo_python(self):
        with mock.patch("downloader.shutil.which", return_value=None), \
             mock.patch.dict(sys.modules, {"yt_dlp": object()}), \
             mock.patch("sys.executable", "C:/Python39/python.exe"):
            self.assertEqual(downloader.localizar_ytdlp(),
                             ["C:/Python39/python.exe", "-m", "yt_dlp"])

    def test_retorna_vazio_quando_ausente(self):
        with mock.patch("downloader.shutil.which", return_value=None), \
             mock.patch.dict(sys.modules, {"yt_dlp": None}):
            self.assertEqual(downloader.localizar_ytdlp(), [])

    def test_verificar_ytdlp_true(self):
        with mock.patch("downloader.localizar_ytdlp", return_value=["yt-dlp"]):
            self.assertTrue(downloader.verificar_ytdlp())

    def test_verificar_ytdlp_false(self):
        with mock.patch("downloader.localizar_ytdlp", return_value=[]):
            self.assertFalse(downloader.verificar_ytdlp())

    def test_verificar_ffmpeg_true(self):
        with mock.patch("downloader.shutil.which", return_value="C:/ffmpeg.exe"):
            self.assertTrue(downloader.verificar_ffmpeg())

    def test_verificar_ffmpeg_false(self):
        with mock.patch("downloader.shutil.which", return_value=None):
            self.assertFalse(downloader.verificar_ffmpeg())


# ─── obter_info_video ────────────────────────────────────────────────────────


def _run_fake(returncode=0, stdout="", stderr=""):
    return mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestObterInfoVideo(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("downloader.localizar_ytdlp", return_value=["yt-dlp"])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sucesso(self):
        info = {"id": "abc", "title": "Video", "playlist_count": 1}
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(stdout=json.dumps(info))):
            resultado = downloader.obter_info_video("https://youtu.be/abc")
        self.assertEqual(resultado["title"], "Video")
        self.assertNotIn("is_playlist", resultado)

    def test_detecta_playlist(self):
        info = {"id": "abc", "title": "Playlist", "playlist_count": 5}
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(stdout=json.dumps(info))):
            resultado = downloader.obter_info_video("https://youtu.be/abc")
        self.assertTrue(resultado["is_playlist"])

    def test_erro_retornado_pelo_ytdlp(self):
        erros = []
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(returncode=1, stderr="boom")):
            resultado = downloader.obter_info_video(
                "https://youtu.be/abc", on_error=erros.append)
        self.assertIsNone(resultado)
        self.assertEqual(erros, ["boom"])

    def test_erro_sem_stderr(self):
        erros = []
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(returncode=2, stderr="")):
            downloader.obter_info_video("https://youtu.be/abc", on_error=erros.append)
        self.assertEqual(erros, ["Erro ao obter informacoes."])

    def test_saida_vazia(self):
        erros = []
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(stdout="")):
            downloader.obter_info_video("https://youtu.be/abc", on_error=erros.append)
        self.assertEqual(erros, ["Nenhum dado encontrado."])

    def test_json_invalido(self):
        erros = []
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(stdout="isso nao e json")):
            downloader.obter_info_video("https://youtu.be/abc", on_error=erros.append)
        self.assertEqual(erros, ["Erro ao processar resposta do yt-dlp."])

    def test_timeout(self):
        erros = []
        with mock.patch("downloader.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(["yt-dlp"], 30)):
            downloader.obter_info_video("https://youtu.be/abc", on_error=erros.append)
        self.assertEqual(erros, ["Tempo limite excedido ao obter informacoes."])

    def test_excecao_generica(self):
        erros = []
        with mock.patch("downloader.subprocess.run",
                        side_effect=OSError("sem rede")):
            downloader.obter_info_video("https://youtu.be/abc", on_error=erros.append)
        self.assertEqual(erros, ["sem rede"])


# ─── atualizar_ytdlp ─────────────────────────────────────────────────────────


class TestAtualizarYtdlp(unittest.TestCase):
    def test_pip_sucesso(self):
        with mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(returncode=0)):
            ok, msg = downloader.atualizar_ytdlp()
        self.assertTrue(ok)
        self.assertIn("sucesso", msg)

    def test_fallback_atualizacao_interna(self):
        # pip falha, depois 'yt-dlp -U' funciona
        with mock.patch("downloader.localizar_ytdlp", return_value=["yt-dlp"]), \
             mock.patch("downloader.subprocess.run", side_effect=[
                 _run_fake(returncode=1, stderr="pip erro"),
                 _run_fake(returncode=0),
             ]):
            ok, msg = downloader.atualizar_ytdlp()
        self.assertTrue(ok)

    def test_ambos_falham(self):
        with mock.patch("downloader.localizar_ytdlp", return_value=["yt-dlp"]), \
             mock.patch("downloader.subprocess.run", side_effect=[
                 _run_fake(returncode=1, stderr="pip erro"),
                 _run_fake(returncode=1, stderr="update erro"),
             ]):
            ok, msg = downloader.atualizar_ytdlp()
        self.assertFalse(ok)
        self.assertIn("update erro", msg)
        self.assertIn("pip erro", msg)

    def test_ytdlp_nao_encontrado(self):
        with mock.patch("downloader.localizar_ytdlp", return_value=[]), \
             mock.patch("downloader.subprocess.run",
                        return_value=_run_fake(returncode=1, stderr="pip erro")):
            ok, msg = downloader.atualizar_ytdlp()
        self.assertFalse(ok)
        self.assertIn("yt-dlp nao encontrado", msg)

    def test_pip_levanta_excecao_mas_interno_funciona(self):
        with mock.patch("downloader.localizar_ytdlp", return_value=["yt-dlp"]), \
             mock.patch("downloader.subprocess.run", side_effect=[
                 OSError("sem permissao"),
                 _run_fake(returncode=0),
             ]):
            ok, _ = downloader.atualizar_ytdlp()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
