#!/usr/bin/env python3
"""
Platform Definitions
Define as plataformas suportadas e seus padroes de URL.
O yt-dlp ja suporta todas essas plataformas internamente.
"""

import re
from typing import Optional, Dict, List, Tuple


# ─── Definicao de cada plataforma ───────────────────────────────────────────

Platform = Dict[str, any]

PLATFORMS: List[Platform] = [
    {
        "id": "youtube",
        "nome": "YouTube",
        "cor": "#FF0000",
        "icone": "YT",
        "padroes_url": [
            r"youtube\.com/watch\?v=[\w-]+",
            r"youtu\.be/[\w-]+",
            r"youtube\.com/playlist\?list=[\w-]+",
            r"youtube\.com/shorts/[\w-]+",
            r"youtube\.com/watch\?.*v=[\w-]+",
            r"youtube\.com/embed/[\w-]+",
            r"^[\w-]{11}$",  # Apenas o ID do video
        ],
        "formatos_padrao": ["mp4", "mp3", "webm", "mkv"],
        "qualidades": ["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"],
        "tem_legendas": True,
        "tem_playlists": True,
    },
    {
        "id": "twitter",
        "nome": "Twitter / X",
        "cor": "#1DA1F2",
        "icone": "TW",
        "padroes_url": [
            r"(?:twitter|x)\.com/[\w_]+/status/[\d]+",
            r"t\.co/[\w\d]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "tiktok",
        "nome": "TikTok",
        "cor": "#000000",
        "icone": "TK",
        "padroes_url": [
            r"tiktok\.com/@[\w.-]+/video/[\d]+",
            r"tiktok\.com/@[\w.-]+",
            r"vm\.tiktok\.com/[\w]+",
            r"m\.tiktok\.com/v/[\d]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "instagram",
        "nome": "Instagram",
        "cor": "#E4405F",
        "icone": "IG",
        "padroes_url": [
            r"instagram\.com/p/[\w-]+",
            r"instagram\.com/reel/[\w-]+",
            r"instagram\.com/tv/[\w-]+",
            r"instagram\.com/stories/[\w.-]+/[\d]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "facebook",
        "nome": "Facebook",
        "cor": "#1877F2",
        "icone": "FB",
        "padroes_url": [
            r"facebook\.com/[\w.-]+/videos/[\d]+",
            r"facebook\.com/watch/?\?v=[\d]+",
            r"fb\.watch/[\w\d]+",
            r"facebook\.com/reel/[\d]+",
            r"fb\.com/[\w.-]+/videos/[\d]+",
        ],
        "formatos_padrao": ["mp4"],
        "qualidades": ["best", "720p", "480p", "360p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "twitch",
        "nome": "Twitch",
        "cor": "#9146FF",
        "icone": "TW",
        "padroes_url": [
            r"twitch\.tv/[\w_]+(?:/videos/[\d]+|/clips/[\w]+)?",
            r"clips\.twitch\.tv/[\w]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best", "1080p", "720p", "480p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "vimeo",
        "nome": "Vimeo",
        "cor": "#1AB7EA",
        "icone": "VM",
        "padroes_url": [
            r"vimeo\.com/[\d]+",
            r"vimeo\.com/[\w]+/[\d]+",
            r"player\.vimeo\.com/video/[\d]+",
        ],
        "formatos_padrao": ["mp4", "webm"],
        "qualidades": ["best", "1080p", "720p", "480p"],
        "tem_legendas": True,
        "tem_playlists": False,
    },
    {
        "id": "dailymotion",
        "nome": "Dailymotion",
        "cor": "#0066DC",
        "icone": "DM",
        "padroes_url": [
            r"dailymotion\.com/video/[\w]+",
            r"dailymotion\.com/[\w]+/video/[\w]+",
            r"dai\.ly/[\w]+",
        ],
        "formatos_padrao": ["mp4", "mp3", "webm"],
        "qualidades": ["best", "1080p", "720p", "480p", "360p"],
        "tem_legendas": True,
        "tem_playlists": False,
    },
    {
        "id": "reddit",
        "nome": "Reddit",
        "cor": "#FF4500",
        "icone": "RD",
        "padroes_url": [
            r"reddit\.com/r/[\w-]+/comments/[\w-]+",
            r"reddit\.com/[\w-]+/s/[\w]+",
            r"redd\.it/[\w]+",
        ],
        "formatos_padrao": ["mp4"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "linkedin",
        "nome": "LinkedIn",
        "cor": "#0A66C2",
        "icone": "LI",
        "padroes_url": [
            r"linkedin\.com/posts/[\w-]+-[\d]+",
            r"linkedin\.com/feed/update/urn:li:[\w]+:[\d]+",
        ],
        "formatos_padrao": ["mp4"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "soundcloud",
        "nome": "SoundCloud",
        "cor": "#FF5500",
        "icone": "SC",
        "padroes_url": [
            r"soundcloud\.com/[\w-]+/[\w-]+",
            r"on\.soundcloud\.com/[\w]+",
        ],
        "formatos_padrao": ["mp3", "mp4"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": True,
    },
    {
        "id": "pinterest",
        "nome": "Pinterest",
        "cor": "#E60023",
        "icone": "PI",
        "padroes_url": [
            r"pinterest\.[a-z.]+/pin/[\d]+",
            r"pin\.it/[\w]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "bilibili",
        "nome": "Bilibili",
        "cor": "#00A1D6",
        "icone": "BI",
        "padroes_url": [
            r"bilibili\.com/video/BV[\w]+",
            r"b23\.tv/[\w]+",
        ],
        "formatos_padrao": ["mp4", "mp3", "webm"],
        "qualidades": ["best", "1080p", "720p", "480p", "360p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "bandcamp",
        "nome": "Bandcamp",
        "cor": "#1DA0C3",
        "icone": "BC",
        "padroes_url": [
            # O grupo do subdominio e opcional: cobre bandcamp.com e usuario.bandcamp.com
            r"(?:[\w-]+\.)?bandcamp\.com/(?:track|album)/[\w-]+",
        ],
        "formatos_padrao": ["mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "vk",
        "nome": "VK",
        "cor": "#0077FF",
        "icone": "VK",
        "padroes_url": [
            r"vk\.com/video-?[\d_]+",
            r"vk\.com/clip[\d_-]+",
            r"vkvideo\.ru/[\w-]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best", "1080p", "720p", "480p", "360p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "rumble",
        "nome": "Rumble",
        "cor": "#85C742",
        "icone": "RU",
        "padroes_url": [
            r"rumble\.com/v[\w-]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best", "1080p", "720p", "480p", "360p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "mixcloud",
        "nome": "Mixcloud",
        "cor": "#52AAD8",
        "icone": "MX",
        "padroes_url": [
            r"mixcloud\.com/[\w-]+/[\w-]+",
        ],
        "formatos_padrao": ["mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "niconico",
        "nome": "Niconico",
        "cor": "#F27289",
        "icone": "NN",
        "padroes_url": [
            r"nicovideo\.jp/watch/(?:sm|nm|so)[\d]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best", "1080p", "720p", "480p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "ted",
        "nome": "TED Talks",
        "cor": "#E62B1E",
        "icone": "TD",
        "padroes_url": [
            r"ted\.com/talks/[\w-]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best", "1080p", "720p"],
        "tem_legendas": True,
        "tem_playlists": False,
    },
    {
        "id": "streamable",
        "nome": "Streamable",
        "cor": "#111111",
        "icone": "ST",
        "padroes_url": [
            r"streamable\.com/[\w]+",
        ],
        "formatos_padrao": ["mp4"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "kick",
        "nome": "Kick",
        "cor": "#53FC18",
        "icone": "KC",
        "padroes_url": [
            r"kick\.com/video/[\w]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "archiveorg",
        "nome": "Archive.org",
        "cor": "#000000",
        "icone": "AR",
        "padroes_url": [
            r"archive\.org/details/[\w.-]+",
        ],
        "formatos_padrao": ["mp4", "mp3", "webm"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "tumblr",
        "nome": "Tumblr",
        "cor": "#36465D",
        "icone": "TB",
        "padroes_url": [
            r"[\w-]+\.tumblr\.com/post/[\d]+",
            r"tumblr\.com/[\w-]+/[\d]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "okru",
        "nome": "OK.ru",
        "cor": "#ED812B",
        "icone": "OK",
        "padroes_url": [
            r"ok\.ru/video/[\d]+",
        ],
        "formatos_padrao": ["mp4", "mp3"],
        "qualidades": ["best", "720p", "480p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "peertube",
        "nome": "PeerTube",
        "cor": "#F1680D",
        "icone": "PT",
        "padroes_url": [
            # Nota: so detecta instancias com 'peertube' no dominio (ex.: peertube.tv).
            # Outras instancias federadas caem no generico 'outro' (ainda funcionam).
            r"peertube\.[\w.]+/w/[\w]+",
        ],
        "formatos_padrao": ["mp4", "webm", "mp3"],
        "qualidades": ["best", "1080p", "720p", "480p"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
    {
        "id": "outro",
        "nome": "Generico (yt-dlp)",
        "cor": "#7f8c8d",
        "icone": "??",
        "padroes_url": [],
        "formatos_padrao": ["mp4", "mp3", "webm", "mkv"],
        "qualidades": ["best"],
        "tem_legendas": False,
        "tem_playlists": False,
    },
]

# Indice por ID
PLATFORMS_BY_ID: Dict[str, Platform] = {p["id"]: p for p in PLATFORMS}

# Nomes para exibicao
PLATFORM_NAMES: List[str] = [p["id"] for p in PLATFORMS]


# ─── Funcoes de deteccao ────────────────────────────────────────────────────

def detectar_plataforma(url: str) -> Optional[Platform]:
    """
    Detecta qual plataforma a URL pertence.
    Retorna a plataforma ou None se nao reconhecer.
    """
    url = url.strip()

    if not url:
        return None

    # Tenta cada plataforma (exceto "outro" que e generico)
    for platform in PLATFORMS:
        if platform["id"] == "outro":
            continue
        for padrao in platform["padroes_url"]:
            if re.search(padrao, url, re.IGNORECASE):
                return platform

    # Verifica se tem http (provavelmente uma URL valida para yt-dlp)
    if url.startswith("http://") or url.startswith("https://"):
        return PLATFORMS_BY_ID["outro"]

    return None


def validar_url(url: str) -> bool:
    """
    Valida se a URL e suportada por alguma plataforma conhecida
    ou se parece ser uma URL valida.
    """
    url = url.strip()

    if not url:
        return False

    # URLs curtas do YouTube (apenas o ID de 11 caracteres)
    if re.match(r"^[\w-]{11}$", url):
        return True

    # Tenta detectar plataforma
    platform = detectar_plataforma(url)
    return platform is not None


def formatos_para_plataforma(platform_id: str) -> List[str]:
    """Retorna os formatos suportados por uma plataforma."""
    platform = PLATFORMS_BY_ID.get(platform_id)
    if platform:
        return platform["formatos_padrao"]
    return ["mp4", "mp3", "webm", "mkv"]


def qualidades_para_plataforma(platform_id: str) -> List[str]:
    """Retorna as qualidades disponiveis para uma plataforma."""
    platform = PLATFORMS_BY_ID.get(platform_id)
    if platform:
        return platform["qualidades"]
    return ["best"]


def nome_plataforma(platform_id: str) -> str:
    """Retorna o nome amigavel da plataforma."""
    platform = PLATFORMS_BY_ID.get(platform_id)
    if platform:
        return platform["nome"]
    return "Desconhecida"


def cor_plataforma(platform_id: str) -> str:
    """Retorna a cor representativa da plataforma."""
    platform = PLATFORMS_BY_ID.get(platform_id)
    if platform:
        return platform["cor"]
    return "#7f8c8d"


# ─── Atalho para compatibilidade com codigo existente ───────────────────────

def validar_url_youtube(url: str) -> bool:
    """
    Mantido para compatibilidade. Agora aceita qualquer plataforma suportada.
    Equivalente a validar_url().
    """
    return validar_url(url)


def get_platform_ids() -> List[str]:
    """Retorna lista de IDs de plataforma para exibicao."""
    return [p["id"] for p in PLATFORMS if p["id"] != "outro"]


def get_platform_names() -> List[str]:
    """Retorna lista de nomes de plataforma para exibicao."""
    return [p["nome"] for p in PLATFORMS if p["id"] != "outro"]


# ─── Teste rapido ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    urls_teste = [
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
        ("https://twitter.com/user/status/123456789", "twitter"),
        ("https://x.com/user/status/123456789", "twitter"),
        ("https://tiktok.com/@user/video/123456789", "tiktok"),
        ("https://instagram.com/p/ABC123/", "instagram"),
        ("https://instagram.com/reel/ABC123/", "instagram"),
        ("https://facebook.com/watch/?v=123456789", "facebook"),
        ("https://twitch.tv/streamer", "twitch"),
        ("https://vimeo.com/123456789", "vimeo"),
        ("https://dailymotion.com/video/abc123", "dailymotion"),
        ("https://reddit.com/r/videos/comments/abc123/", "reddit"),
        ("https://linkedin.com/posts/user-123456789", "linkedin"),
        ("https://soundcloud.com/artista/faixa-legal", "soundcloud"),
        ("https://on.soundcloud.com/abc123", "soundcloud"),
        ("https://pinterest.com/pin/123456789/", "pinterest"),
        ("https://pin.it/abc123", "pinterest"),
        ("https://www.bilibili.com/video/BV1GJ411x7h7", "bilibili"),
        ("https://b23.tv/abc123", "bilibili"),
        ("https://artista.bandcamp.com/track/faixa", "bandcamp"),
        ("https://vk.com/video-123456_7890", "vk"),
        ("https://rumble.com/vabc123", "rumble"),
        ("https://mixcloud.com/dj/faixa", "mixcloud"),
        ("https://www.nicovideo.jp/watch/sm1234567", "niconico"),
        ("https://ted.com/talks/pessoa_titulo", "ted"),
        ("https://streamable.com/abc123", "streamable"),
        ("https://kick.com/video/abc123", "kick"),
        ("https://archive.org/details/algum-video-1", "archiveorg"),
        ("https://meu.tumblr.com/post/123456789", "tumblr"),
        ("https://ok.ru/video/123456789", "okru"),
        ("https://peertube.tv/w/abc123", "peertube"),
        ("dQw4w9WgXcQ", "youtube"),  # Apenas ID
        ("https://exemplo.com/video", "outro"),  # URL generica
        ("", None),  # Invalido
    ]

    print("Teste de deteccao de plataformas:")
    print("-" * 60)
    for url, esperado in urls_teste:
        plat = detectar_plataforma(url)
        plat_id = plat["id"] if plat else None
        status = "OK" if plat_id == esperado else f"FALHOU (esperado={esperado}, obtido={plat_id})"
        nome = plat["nome"] if plat else "Nenhuma"
        print(f"  {status}: {url[:50]:50s} -> {nome}")
    print("-" * 60)
    print("Teste concluido!")
