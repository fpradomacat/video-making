#!/usr/bin/env python3
"""
miniatura.py - Genera una miniatura de YouTube (1280x720) a partir de una
imagen o un video, escribiendo una palabra grande en el centro.

Requisitos: Python 3, Pillow (pip install pillow) y ffmpeg en el PATH
(ffmpeg solo se usa si la fuente es un video).

Ejemplos:
  python miniatura.py fondo.png "CALMA"
  python miniatura.py loop.mp4 "RESPIRA" --tiempo 5
  python miniatura.py fondo.png "FOCO" --fuente "C:/Windows/Fonts/arialbd.ttf" --salida foco.jpg
  python miniatura.py fondo.png "calma" --mayusculas --oscurecer 0.35
  python miniatura.py fondo.png "Cómo respirar mejor para dormir"      (varias palabras: se reparte solo en líneas)
  python miniatura.py fondo.png "Respirá|y soltá"                       (| fuerza el salto de línea)
"""
import argparse
import re
import subprocess
import unicodedata
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent if AQUI.name.lower() == "scripts" else AQUI
ANCHO, ALTO = 1280, 720
EXT_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

# Fuentes de respaldo comunes (Windows / Linux / macOS)
FUENTES_RESPALDO = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def extraer_frame(video: Path, segundo: float) -> Image.Image:
    tmp = Path(tempfile.mkdtemp()) / "frame.png"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(segundo), "-i", str(video),
        "-frames:v", "1", str(tmp),
    ]
    subprocess.run(cmd, check=True)
    return Image.open(tmp).convert("RGB")


def reparar_marca(img):
    """Borra una pequeña marca vertical sobrante en (273,80) que dejó un elemento de Canva."""
    if img.size != (1920, 1080):
        return img
    img = img.copy()
    caja = (258, 58, 292, 102)
    img.paste(img.crop((296, caja[1], 296 + (caja[2] - caja[0]), caja[3])), (caja[0], caja[1]))
    return img


def cubrir(img: Image.Image, ancho: int, alto: int) -> Image.Image:
    """Escala y recorta al centro para llenar ancho x alto (como 'cover')."""
    r = max(ancho / img.width, alto / img.height)
    nuevo = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    x = (nuevo.width - ancho) // 2
    y = (nuevo.height - alto) // 2
    return nuevo.crop((x, y, x + ancho, y + alto))


def cargar_fuente(ruta: str | None, tam: int) -> ImageFont.FreeTypeFont:
    candidatas = ([ruta] if ruta else []) + FUENTES_RESPALDO
    for c in candidatas:
        try:
            return ImageFont.truetype(c, tam)
        except OSError:
            continue
    sys.exit("No encontré ninguna fuente. Pasá una con --fuente RUTA.ttf")


def partir_en_lineas(palabras, k):
    """Reparte las palabras en k líneas minimizando la línea más larga (en caracteres)."""
    n = len(palabras)
    if k >= n:
        return [[w] for w in palabras]
    mejor, mejor_costo = None, None

    def rec(i, restantes, actual):
        nonlocal mejor, mejor_costo
        if restantes == 1:
            lineas = actual + [palabras[i:]]
            costo = max(len(" ".join(l)) for l in lineas)
            if mejor_costo is None or costo < mejor_costo:
                mejor, mejor_costo = lineas, costo
            return
        for j in range(i + 1, n - restantes + 2):
            rec(j, restantes - 1, actual + [palabras[i:j]])

    rec(0, k, [])
    return mejor


def ajustar_texto(texto, ruta, ancho_max, alto_max, tam_max, max_lineas=3):
    """Elige saltos de línea y tamaño de letra para que el texto sea lo más grande posible.

    - Si el texto trae saltos manuales ('|' o '\\n'), se respetan.
    - Si no, prueba con 1, 2 y 3 líneas y se queda con la que da letra más grande.
    Devuelve (lineas, fuente, alto_de_linea).
    """
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    manual = [l.strip() for l in texto.replace("\\n", "|").split("|") if l.strip()]
    if len(manual) > 1:
        candidatos = [manual]
    else:
        palabras = texto.split()
        candidatos = [[" ".join(l) for l in partir_en_lineas(palabras, k)]
                      for k in range(1, min(max_lineas, len(palabras)) + 1)]

    mejor = None
    for lineas in candidatos:
        tam = tam_max
        while tam > 20:
            f = cargar_fuente(ruta, tam)
            alto_l = int(tam * 1.08)
            ancho = max(d.textbbox((0, 0), l, font=f)[2] - d.textbbox((0, 0), l, font=f)[0] for l in lineas)
            if ancho <= ancho_max and alto_l * len(lineas) <= alto_max:
                break
            tam -= 4
        if mejor is None or tam > mejor[0]:   # empate: gana la de menos líneas
            mejor = (tam, lineas)
    tam, lineas = mejor
    return lineas, cargar_fuente(ruta, tam), int(tam * 1.08)


def slug(texto: str) -> str:
    """'Respirá|y soltá' -> 'respira_y_solta' (minúsculas, sin acentos, guiones bajos)."""
    t = unicodedata.normalize("NFKD", texto.replace("|", " ").replace("\\n", " "))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "sin_texto"


def main():
    p = argparse.ArgumentParser(description="Miniatura de YouTube con una palabra.")
    p.add_argument("fuente_img", help="Imagen o video de fondo")
    p.add_argument("palabra", help="Palabra o frase corta. Se divide sola en hasta 3 líneas; usá | para forzar saltos")
    p.add_argument("--salida", help="Archivo de salida (default: listo/miniatura-<palabras>.png en la carpeta actual)")
    p.add_argument("--fuente", help="Ruta a un .ttf/.otf (tu tipografía de marca)")
    p.add_argument("--color", default="#FFFFFF", help="Color del texto (default blanco)")
    p.add_argument("--tiempo", type=float, default=3.0, help="Segundo del video del que sacar el frame")
    p.add_argument("--oscurecer", type=float, default=0.25,
                   help="0 a 1: cuánto oscurecer el fondo para dar contraste (default 0.25)")
    p.add_argument("--ancho-texto", type=float, default=0.80,
                   help="Fracción del ancho que puede ocupar el texto (default 0.80)")
    p.add_argument("--posicion", type=float, default=0.5,
                   help="Altura vertical del texto, 0 arriba y 1 abajo (default 0.5)")
    p.add_argument("--mayusculas", action="store_true", help="Pasar la palabra a mayúsculas")
    a = p.parse_args()

    src = Path(a.fuente_img)
    if not src.exists():
        sys.exit(f"No existe: {src}")

    img = extraer_frame(src, a.tiempo) if src.suffix.lower() in EXT_VIDEO \
        else Image.open(src).convert("RGB")
    img = cubrir(reparar_marca(img), ANCHO, ALTO)

    if a.oscurecer > 0:
        img = ImageEnhance.Brightness(img).enhance(1 - min(a.oscurecer, 0.9))

    if not a.fuente:
        cb = RAIZ / "fuentes" / "Cardo" / "Cardo-Bold.ttf"
        a.fuente = str(cb) if cb.exists() else None
    texto = a.palabra.upper() if a.mayusculas else a.palabra
    lineas, f, alto_l = ajustar_texto(texto, a.fuente, int(ANCHO * a.ancho_texto), int(ALTO * 0.7), 400)

    # Sombra suave para legibilidad
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    cx, cy = ANCHO // 2, int(ALTO * a.posicion)
    y0 = cy - (alto_l * (len(lineas) - 1)) // 2
    for i, linea in enumerate(lineas):
        y = y0 + i * alto_l
        d.text((cx + 4, y + 6), linea, font=f, fill=(0, 0, 0, 140), anchor="mm")
        d.text((cx, y), linea, font=f, fill=a.color, anchor="mm")
    img = Image.alpha_composite(img.convert("RGBA"), capa).convert("RGB")

    if a.salida:
        salida = Path(a.salida)
    else:
        salida = Path.cwd() / "listo" / f"miniatura-{slug(a.palabra)}.png"
    salida.parent.mkdir(parents=True, exist_ok=True)
    img.save(salida, quality=92)
    print(f"Listo: {salida}")


if __name__ == "__main__":
    main()
