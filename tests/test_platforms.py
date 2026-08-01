"""Testes unitarios para o modulo platforms.py (deteccao de plataformas)."""

import unittest

import platforms
from platforms import (
    PLATFORMS,
    cor_plataforma,
    detectar_plataforma,
    formatos_para_plataforma,
    get_platform_ids,
    get_platform_names,
    nome_plataforma,
    qualidades_para_plataforma,
    validar_url,
    validar_url_youtube,
)

# Novas plataformas adicionadas (id -> URLs de exemplo)
NOVAS_PLATAFORMAS = {
    "soundcloud": [
        "https://soundcloud.com/artista/faixa-legal",
        "https://on.soundcloud.com/abc123",
    ],
    "pinterest": [
        "https://pinterest.com/pin/123456789/",
        "https://br.pinterest.com/pin/987654321/",
        "https://pin.it/abc123",
    ],
    "bilibili": [
        "https://www.bilibili.com/video/BV1GJ411x7h7",
        "https://b23.tv/abc123",
    ],
    "bandcamp": [
        "https://artista.bandcamp.com/track/faixa",
        "https://bandcamp.com/album/algum-album",
    ],
    "vk": [
        "https://vk.com/video-123456_7890",
        "https://vkvideo.ru/video_abc",
    ],
    "rumble": [
        "https://rumble.com/vabc123",
        "https://rumble.com/vabc123-parte-2",
    ],
    "mixcloud": [
        "https://mixcloud.com/dj/set-legal",
    ],
    "niconico": [
        "https://www.nicovideo.jp/watch/sm1234567",
        "https://www.nicovideo.jp/watch/nm1234567",
    ],
    "ted": [
        "https://ted.com/talks/pessoa_titulo",
        "https://www.ted.com/talks/alguma_palestra",
    ],
    "streamable": [
        "https://streamable.com/abc123",
    ],
    "kick": [
        "https://kick.com/video/abc123",
    ],
    "archiveorg": [
        "https://archive.org/details/algum-video-1",
        "https://archive.org/details/filme.classico.1990",
    ],
    "tumblr": [
        "https://meu.tumblr.com/post/123456789",
        "https://tumblr.com/usuario/987654321",
    ],
    "okru": [
        "https://ok.ru/video/123456789",
    ],
    "peertube": [
        "https://peertube.tv/w/abc123",
        "https://peertube.fr/w/xyz789",
    ],
}

# Plataformas pre-existentes (regressao)
PLATAFORMAS_EXISTENTES = {
    "youtube": [
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/playlist?list=PLabc123",
        "dQw4w9WgXcQ",
    ],
    "twitter": [
        "https://twitter.com/user/status/123456789",
        "https://x.com/user/status/123456789",
    ],
    "tiktok": [
        "https://tiktok.com/@user/video/123456789",
        "https://vm.tiktok.com/abc123",
    ],
    "instagram": [
        "https://instagram.com/p/ABC123/",
        "https://instagram.com/reel/ABC123/",
    ],
    "facebook": [
        "https://facebook.com/watch/?v=123456789",
        "https://fb.watch/abc123",
    ],
    "twitch": [
        "https://twitch.tv/streamer",
        "https://twitch.tv/streamer/videos/12345",
    ],
    "vimeo": [
        "https://vimeo.com/123456789",
    ],
    "dailymotion": [
        "https://dailymotion.com/video/abc123",
    ],
    "reddit": [
        "https://reddit.com/r/videos/comments/abc123/",
    ],
    "linkedin": [
        "https://linkedin.com/posts/user-123456789",
    ],
}


class TestDetectarPlataforma(unittest.TestCase):
    def test_plataformas_novas(self):
        for plat_id, urls in NOVAS_PLATAFORMAS.items():
            for url in urls:
                with self.subTest(url=url):
                    plat = detectar_plataforma(url)
                    self.assertIsNotNone(plat, f"URL nao detectada: {url}")
                    self.assertEqual(plat["id"], plat_id, f"URL: {url}")

    def test_plataformas_existentes(self):
        for plat_id, urls in PLATAFORMAS_EXISTENTES.items():
            for url in urls:
                with self.subTest(url=url):
                    plat = detectar_plataforma(url)
                    self.assertIsNotNone(plat, f"URL nao detectada: {url}")
                    self.assertEqual(plat["id"], plat_id, f"URL: {url}")

    def test_deteccao_case_insensitive(self):
        self.assertEqual(
            detectar_plataforma("HTTPS://SOUNDCLOUD.COM/USER/TRACK")["id"],
            "soundcloud")
        self.assertEqual(
            detectar_plataforma("https://RUMBLE.COM/VABC")["id"],
            "rumble")

    def test_url_vazia_retorna_none(self):
        self.assertIsNone(detectar_plataforma(""))
        self.assertIsNone(detectar_plataforma("   "))

    def test_url_generica_retorna_outro(self):
        plat = detectar_plataforma("https://exemplo.com/video")
        self.assertIsNotNone(plat)
        self.assertEqual(plat["id"], "outro")

    def test_texto_sem_url_retorna_none(self):
        self.assertIsNone(detectar_plataforma("isto nao e uma url"))


class TestValidarUrl(unittest.TestCase):
    def test_url_valida(self):
        self.assertTrue(validar_url("https://soundcloud.com/user/track"))
        self.assertTrue(validar_url("https://bilibili.com/video/BV1GJ411x7h7"))
        self.assertTrue(validar_url("https://exemplo.com/video"))  # generica

    def test_id_youtube_curto(self):
        self.assertTrue(validar_url("dQw4w9WgXcQ"))

    def test_url_invalida(self):
        self.assertFalse(validar_url(""))
        self.assertFalse(validar_url("nao e uma url"))

    def test_validar_url_youtube_alias(self):
        self.assertTrue(validar_url_youtube("https://youtube.com/watch?v=abc"))
        self.assertFalse(validar_url_youtube("texto invalido"))


class TestHelpers(unittest.TestCase):
    def test_get_platform_ids_inclui_novas(self):
        ids = get_platform_ids()
        for plat_id in NOVAS_PLATAFORMAS:
            self.assertIn(plat_id, ids)
        self.assertNotIn("outro", ids)

    def test_get_platform_names(self):
        nomes = get_platform_names()
        self.assertIn("SoundCloud", nomes)
        self.assertIn("Bilibili", nomes)
        self.assertIn("TED Talks", nomes)

    def test_formatos_para_plataforma(self):
        self.assertEqual(formatos_para_plataforma("soundcloud"), ["mp3", "mp4"])
        self.assertEqual(formatos_para_plataforma("streamable"), ["mp4"])
        # Plataforma desconhecida usa padrao
        self.assertEqual(formatos_para_plataforma("nao-existe"),
                         ["mp4", "mp3", "webm", "mkv"])

    def test_qualidades_para_plataforma(self):
        self.assertEqual(qualidades_para_plataforma("bilibili"),
                         ["best", "1080p", "720p", "480p", "360p"])
        self.assertEqual(qualidades_para_plataforma("soundcloud"), ["best"])
        self.assertEqual(qualidades_para_plataforma("nao-existe"), ["best"])

    def test_nome_plataforma(self):
        self.assertEqual(nome_plataforma("pinterest"), "Pinterest")
        self.assertEqual(nome_plataforma("archiveorg"), "Archive.org")
        self.assertEqual(nome_plataforma("nao-existe"), "Desconhecida")

    def test_cor_plataforma(self):
        self.assertEqual(cor_plataforma("soundcloud"), "#FF5500")
        self.assertEqual(cor_plataforma("bilibili"), "#00A1D6")
        self.assertEqual(cor_plataforma("nao-existe"), "#7f8c8d")


class TestIntegridadeDados(unittest.TestCase):
    """Garante que a tabela PLATFORMS esta bem formada."""

    CHAVES_OBRIGATORIAS = {
        "id", "nome", "cor", "icone", "padroes_url",
        "formatos_padrao", "qualidades", "tem_legendas", "tem_playlists",
    }

    def test_ids_unicos(self):
        ids = [p["id"] for p in PLATFORMS]
        self.assertEqual(len(ids), len(set(ids)), "IDs duplicados na tabela")

    def test_todas_entradas_completas(self):
        for p in PLATFORMS:
            with self.subTest(id=p.get("id")):
                self.assertTrue(self.CHAVES_OBRIGATORIAS.issubset(p.keys()))

    def test_padroes_url_sao_regex_validas(self):
        import re
        for p in PLATFORMS:
            for padrao in p["padroes_url"]:
                with self.subTest(id=p["id"], padrao=padrao):
                    re.compile(padrao)  # deve compilar sem erro

    def test_outro_e_o_ultimo_e_sem_padroes(self):
        self.assertEqual(PLATFORMS[-1]["id"], "outro")
        self.assertEqual(PLATFORMS[-1]["padroes_url"], [])

    def test_formatos_validos(self):
        validos = {"mp4", "mp3", "webm", "mkv"}
        for p in PLATFORMS:
            with self.subTest(id=p["id"]):
                self.assertTrue(validos.issuperset(p["formatos_padrao"]))

    def test_qualidades_validas(self):
        validas = {"best", "2160p", "1440p", "1080p", "720p", "480p", "360p"}
        for p in PLATFORMS:
            with self.subTest(id=p["id"]):
                self.assertTrue(validas.issuperset(p["qualidades"]))
                self.assertIn("best", p["qualidades"])


if __name__ == "__main__":
    unittest.main()
