#!/usr/bin/env python3
"""
gerar_icone.py - Gera o icone do YouTube Downloader (youtube_icon.ico)
em multiplas resolucoes (16x16 ate 256x256) usando Pillow.

Uso:
    python gerar_icone.py
"""

from pathlib import Path
from PIL import Image, ImageDraw


# ─── Configuracao ───────────────────────────────────────────────────────────
SAIDA = Path(__file__).parent / "youtube_icon.ico"

# Tamanhos recomendados para ICO (Windows)
TAMANHOS = [16, 20, 24, 32, 40, 48, 64, 128, 256]

# Cores
VERMELHO = (230, 33, 23, 255)       # Vermelho YouTube
VERMELHO_ESCURO = (179, 25, 18, 255)
BRANCO = (255, 255, 255, 255)


def desenhar_icone(tamanho: int) -> Image.Image:
    """Desenha um icone estilo YouTube: fundo vermelho arredondado + play branco."""
    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ─── Fundo vermelho arredondado ────────────────────────────────────────
    margem = max(1, tamanho // 12)
    raio = max(2, tamanho // 5)
    d.rounded_rectangle(
        [margem, margem, tamanho - margem, tamanho - margem],
        radius=raio,
        fill=VERMELHO,
    )

    # ─── Triangulo de play branco ──────────────────────────────────────────
    # Centralizado levemente a direita para efeito visual
    cx = tamanho * 0.40
    ponta = tamanho * 0.72
    topo = tamanho * 0.28
    base = tamanho * 0.72
    d.polygon(
        [(cx, topo), (ponta, tamanho / 2), (cx, base)],
        fill=BRANCO,
    )

    return img


def main():
    """Gera o arquivo .ico com todas as resolucoes."""
    imagens = [desenhar_icone(s) for s in TAMANHOS]

    # Salva como ICO com multiplas resolucoes
    imagens[0].save(
        SAIDA,
        format="ICO",
        sizes=[(s, s) for s in TAMANHOS],
    )

    print(f"Icone gerado: {SAIDA}")
    print(f"Resolucoes: {', '.join(f'{s}x{s}' for s in TAMANHOS)}")
    print("Pronto!")


if __name__ == "__main__":
    main()
