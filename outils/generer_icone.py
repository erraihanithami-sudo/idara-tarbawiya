"""يولّد أيقونة البرنامج (idara/resources/icone.ico) وصورة الرمز (logo.png) من هندسة idara/marque.py.

الاستعمال: python outils/generer_icone.py
يُرسم الرمز بدقة مضاعفة ثم يُصغَّر لكل حجم، فتبقى الحواف ناعمة حتى 16 بكسل.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from idara import marque  # noqa: E402

TAILLES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def dessiner(cote: int = 1024, inverse: bool = False) -> Image.Image:
    k = cote / marque.COTE
    im = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for nature, couleur, g in marque.formes(inverse):
        if nature == "tuile":
            x0, y0, x1, y1, r = g
            d.rounded_rectangle((x0 * k, y0 * k, x1 * k - 1, y1 * k - 1), radius=r * k, fill=couleur)
        elif nature == "rect":
            x0, y0, x1, y1, r = g
            d.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=r * k, fill=couleur)
        else:
            d.polygon([(x * k, y * k) for x, y in g], fill=couleur)
    return im


def main() -> None:
    grand = dessiner(1024)
    res = RACINE / "idara" / "resources"
    images = [grand.resize((t, t), Image.LANCZOS) for t in TAILLES]
    images[-1].save(res / "icone.ico", format="ICO", sizes=[(t, t) for t in TAILLES],
                    append_images=images[:-1])
    grand.resize((512, 512), Image.LANCZOS).save(res / "logo.png")
    print("أيقونة:", res / "icone.ico")


if __name__ == "__main__":
    main()
