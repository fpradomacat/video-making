#!/usr/bin/env python3
"""
fondo.py - Genera el fondo de video (1920x1080) de meditawork: título, subtítulo y
la marca "meditawork" dibujados sobre un fondo limpio (sin texto) exportado de Canva.

Replica el diseño de Canva ("Fondo de YouTube para meditawork" y "... variante clara"):
  - Título en Cardo, centrado, con el espaciado ajustado igual que en Canva.
  - Subtítulo: noche = Aileron con letras espaciadas; día = Cardo.
  - Marca: "medita" en Raleway Bold + "work" en Raleway Regular, abajo en el centro.

Requisitos: Python 3 y Pillow (pip install pillow).
Recursos (se buscan solos junto a los scripts):
  fondos/noche_limpio.png, fondos/dia_limpio.png
  fuentes/Cardo/Cardo-Regular.ttf, fuentes/Aileron/Aileron-Regular.otf,
  fuentes/Raleway/static/Raleway-Bold.ttf y Raleway-Regular.ttf

Ejemplos:
  python fondo.py "Sentir sin cambiar nada"
  python fondo.py "Mitos de la meditación" --estilo dia --subtitulo "Cómo empezar sin complicarte"
  python fondo.py "Respirar para|soltar" --subtitulo "Respiración guiada"      (| = salto de línea)
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent if AQUI.name.lower() == "scripts" else AQUI

ANCHO, ALTO = 1920, 1080
SS = 4  # supersampling para bordes suaves y posiciones sub-píxel

# Medidas tomadas de los diseños de Canva (px sobre un lienzo de 1920x1080).
# 'titulo_top'/'sub_top': borde superior de la caja de texto de una línea.
ESTILOS = {
    "noche": dict(
        base="noche_limpio.png",
        color_titulo="#f4e9d9", color_sub="#f4e9d9", color_marca="#f9f5e5",
        titulo_size=133.333, titulo_track=-0.0298, titulo_top=348.15,
        sub_size=41.7188, sub_track=0.2002, sub_top=539.48, sub_fuente="aileron",
        sub_defecto="Meditación guiada",
    ),
    "dia": dict(
        base="dia_limpio.png",
        color_titulo="#f9f5e5", color_sub="#f9f5e5", color_marca="#f9f5e5",
        titulo_size=133.333, titulo_track=0.0, titulo_top=360.33,
        sub_size=46.4062, sub_track=0.0, sub_top=520.0, sub_fuente="aileron",
        sub_defecto="",
    ),
}
MARCA_SIZE, MARCA_TOP = 41.71875, 922.43
LINEA_RATIO = 1.1975          # alto de la caja de una línea / tamaño de letra (Canva, Cardo)
MAX_ANCHO_TITULO = 1560       # margen de seguridad para que nada toque los bordes

FUENTES = {
    "cardo": ["Cardo/Cardo-Regular.ttf"],
    "aileron": ["Aileron/Aileron-Regular.otf"],
    "raleway_bold": ["Raleway/static/Raleway-Bold.ttf"],
    "raleway": ["Raleway/static/Raleway-Regular.ttf"],
}
RESPALDO = [
    "C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ruta_fuente(clave, carpeta=None):
    base = Path(carpeta) if carpeta else RAIZ / "fuentes"
    for rel in FUENTES[clave]:
        p = base / rel
        if p.exists():
            return str(p)
    # búsqueda flexible por nombre de archivo
    nombre = Path(FUENTES[clave][0]).name.lower()
    if base.exists():
        for p in base.rglob("*"):
            if p.name.lower() == nombre:
                return str(p)
    sys.exit(f"No encuentro la fuente '{nombre}' en {base}. Revisá la carpeta fuentes/.")


def cargar(clave, size, carpeta=None):
    return ImageFont.truetype(ruta_fuente(clave, carpeta), max(1, int(round(size * SS))))


def avances(texto, font, track_px):
    """Posición x (en px del lienzo supersampleado) de cada carácter, con kerning y tracking."""
    xs, x = [], 0.0
    for i, ch in enumerate(texto):
        xs.append(x)
        if i + 1 < len(texto):
            par = font.getlength(ch + texto[i + 1]) - font.getlength(texto[i + 1])
        else:
            par = font.getlength(ch)
        x += par + track_px * SS
    return xs, x - track_px * SS   # sin el espaciado final


def ancho_texto(texto, font, track_px):
    return avances(texto, font, track_px)[1] / SS


def dibujar_linea(destino, texto, font, size, track_em, color, cx, baseline_y, alineacion="centro", x_izq=0,
                  sombra=False):
    """Dibuja una línea con tracking/kerning, supersampleada. cx = centro horizontal."""
    xs, total = avances(texto, font, track_em * size)
    w = int(total + size * SS * 1.2)
    h = int(size * SS * 2.0)
    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    pad = size * SS * 0.1
    base_local = int(size * SS * 1.3)
    for ch, x in zip(texto, xs):
        d.text((pad + x, base_local), ch, font=font, fill=color + (255,), anchor="ls")
    capa = capa.resize((max(1, w // SS), max(1, h // SS)), Image.LANCZOS)
    if sombra:   # sombra suave detrás del texto (ayuda cuando el texto pisa el sol)
        alfa = capa.getchannel("A").filter(ImageFilter.GaussianBlur(max(2, size * 0.04)))
        alfa = alfa.point(lambda v: int(v * 0.55))
        oscura = Image.new("RGBA", capa.size, (8, 30, 34, 0))
        oscura.putalpha(alfa)
        capa = Image.alpha_composite(oscura, capa)
    ancho_real = total / SS
    if alineacion == "centro":
        x0 = cx - ancho_real / 2 - pad / SS
    else:
        x0 = x_izq - pad / SS
    y0 = baseline_y - base_local / SS
    destino.alpha_composite(capa, (int(round(x0)), int(round(y0))))


def reparar_marca(img):
    """Borra una pequeña marca vertical sobrante en (273,80) que dejó un elemento de Canva."""
    caja = (258, 58, 292, 102)
    fuente = img.crop((296, caja[1], 296 + (caja[2] - caja[0]), caja[3]))
    img.paste(fuente, (caja[0], caja[1]))


def ajustar_lineas(texto, font_clave, size, track, max_ancho, carpeta):
    """Devuelve (lineas, size). Respeta '|' manual; si no entra, parte en 2 líneas y/o achica."""
    manual = [l.strip() for l in texto.replace("\\n", "|").split("|") if l.strip()]
    f = cargar(font_clave, size, carpeta)
    if len(manual) > 1:
        lineas = manual
    else:
        lineas = [texto.strip()]
        if ancho_texto(lineas[0], f, track * size) > max_ancho:
            pal = lineas[0].split()
            mejor = None
            for i in range(1, len(pal)):
                a, b = " ".join(pal[:i]), " ".join(pal[i:])
                peor = max(ancho_texto(a, f, track * size), ancho_texto(b, f, track * size))
                if mejor is None or peor < mejor[0]:
                    mejor = (peor, [a, b])
            if mejor:
                lineas = mejor[1]
    # achicar si aún se pasa
    while True:
        f = cargar(font_clave, size, carpeta)
        peor = max(ancho_texto(l, f, track * size) for l in lineas)
        if peor <= max_ancho or size < 40:
            break
        size *= 0.97
    return lineas, size


def generar(titulo, estilo="noche", subtitulo=None, sub_fuente=None, base=None,
            marca=True, fuentes_dir=None, sombra=False):
    cfg = ESTILOS[estilo]
    ruta_base = Path(base) if base else RAIZ / "fondos" / cfg["base"]
    if not ruta_base.exists():
        sys.exit(f"No encuentro el fondo limpio: {ruta_base}")
    img = Image.open(ruta_base).convert("RGBA")
    if img.size != (ANCHO, ALTO):
        img = img.resize((ANCHO, ALTO), Image.LANCZOS)
    reparar_marca(img)

    sub = cfg["sub_defecto"] if subtitulo is None else subtitulo
    sub_clave = sub_fuente or cfg["sub_fuente"]

    # --- título ---------------------------------------------------------
    lineas, tsize = ajustar_lineas(titulo, "cardo", cfg["titulo_size"], cfg["titulo_track"],
                                   MAX_ANCHO_TITULO, fuentes_dir)
    ft = cargar("cardo", tsize, fuentes_dir)
    asc_t, desc_t = (v / SS for v in ft.getmetrics())
    n = len(lineas)
    pitch = (LINEA_RATIO if n == 1 else 1.08) * tsize

    # --- subtítulo ------------------------------------------------------
    sub_h = 1.185 * cfg["sub_size"]
    gap = cfg["sub_top"] - (cfg["titulo_top"] + LINEA_RATIO * cfg["titulo_size"])
    if not sub:
        sub_h, gap = 0, 0
    elif n > 1:
        gap = max(gap, 18)      # que el subtítulo no se pegue a un título de varias líneas

    # El bloque (título + subtítulo) mantiene el centro vertical del diseño original.
    alto1 = LINEA_RATIO * cfg["titulo_size"] + gap + sub_h
    centro = cfg["titulo_top"] + alto1 / 2
    alto_n = n * pitch + gap + sub_h
    top = centro - alto_n / 2

    for i, linea in enumerate(lineas):
        caja_top = top + i * pitch
        baseline = caja_top + (pitch - (asc_t + desc_t)) / 2 + asc_t
        dibujar_linea(img, linea, ft, tsize, cfg["titulo_track"], hex_rgb(cfg["color_titulo"]),
                      ANCHO / 2, baseline, sombra=sombra)

    if sub:
        fs = cargar(sub_clave, cfg["sub_size"], fuentes_dir)
        asc_s, desc_s = (v / SS for v in fs.getmetrics())
        sub_top = top + n * pitch + gap
        baseline = sub_top + (sub_h - (asc_s + desc_s)) / 2 + asc_s
        dibujar_linea(img, sub, fs, cfg["sub_size"], cfg["sub_track"], hex_rgb(cfg["color_sub"]),
                      ANCHO / 2, baseline, sombra=sombra)

    # --- marca ------------------------------------------------------------
    if marca:
        fb = cargar("raleway_bold", MARCA_SIZE, fuentes_dir)
        fr = cargar("raleway", MARCA_SIZE, fuentes_dir)
        wb, wr = fb.getlength("medita") / SS, fr.getlength("work") / SS
        x0 = ANCHO / 2 - (wb + wr) / 2
        asc, desc = (v / SS for v in fb.getmetrics())
        caja_h = 1.1883 * MARCA_SIZE
        baseline = MARCA_TOP + (caja_h - (asc + desc)) / 2 + asc
        col = hex_rgb(cfg["color_marca"])
        dibujar_linea(img, "medita", fb, MARCA_SIZE, 0.0, col, 0, baseline, "izq", x0)
        dibujar_linea(img, "work", fr, MARCA_SIZE, 0.0, col, 0, baseline, "izq", x0 + wb)

    return img.convert("RGB")


def main():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="Fondo de video meditawork con título y subtítulo.")
    p.add_argument("titulo", help="Título. Usá | para forzar saltos de línea")
    p.add_argument("--estilo", choices=list(ESTILOS), default="noche")
    p.add_argument("--subtitulo", help="Subtítulo (noche: 'Meditación guiada' por defecto; día: ninguno)")
    p.add_argument("--fuente-subtitulo", choices=["cardo", "aileron"], help="Cambiar la fuente del subtítulo")
    p.add_argument("--base", help="Fondo limpio a usar (default: fondos/<estilo>_limpio.png)")
    p.add_argument("--sin-marca", action="store_true", help="No dibujar 'meditawork' abajo")
    p.add_argument("--sombra", action="store_true", help="Sombra suave en los textos (útil si el título pisa el sol)")
    p.add_argument("--fuentes", help="Carpeta de fuentes (default: fuentes/ junto a los scripts)")
    p.add_argument("--salida", default="fondo.png", help="Archivo de salida (default: fondo.png en la carpeta actual)")
    a = p.parse_args()

    img = generar(a.titulo, a.estilo, a.subtitulo, a.fuente_subtitulo, a.base,
                  not a.sin_marca, a.fuentes, a.sombra)
    salida = Path(a.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    img.save(salida)
    print(f"Listo: {salida}")


if __name__ == "__main__":
    main()
