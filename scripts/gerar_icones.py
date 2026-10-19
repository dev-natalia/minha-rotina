"""Gera os ícones provisórios do PWA.

Uso: uv run --with pillow python scripts/gerar_icones.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VERDE = "#4f7d55"
PAPEL = "#f6f3ee"
DESTINO = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
FONTES = ["C:/Windows/Fonts/georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]


def fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in FONTES:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default(tamanho)


def icone(lado: int, maskable: bool) -> Image.Image:
    img = Image.new("RGB", (lado, lado), VERDE if maskable else PAPEL)
    desenho = ImageDraw.Draw(img)
    if not maskable:
        margem = lado // 16
        desenho.rounded_rectangle((margem, margem, lado - margem, lado - margem), radius=lado // 5, fill=VERDE)
    # Maskable: a letra fica dentro da zona segura (80% central).
    letra = fonte(int(lado * (0.42 if maskable else 0.55)))
    desenho.text((lado / 2, lado / 2), "R", font=letra, fill=PAPEL, anchor="mm")
    return img


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    icone(192, False).save(DESTINO / "icon-192.png")
    icone(512, False).save(DESTINO / "icon-512.png")
    icone(512, True).save(DESTINO / "icon-maskable-512.png")
    icone(180, True).save(DESTINO / "apple-touch-icon.png")
    print("Ícones gerados em", DESTINO)
