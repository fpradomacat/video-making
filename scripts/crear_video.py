#!/usr/bin/env python3
"""
crear_video.py - De un audio (mp3/wav) a un mp4 listo para subir + miniatura.

Hace todo en un paso:
  1. Corta silencios con auto-editor SOLO en modo charla (en meditación no corta nada:
     el audio queda tal cual lo dejaste en Audacity; usá --con-cortes si querés cortar).
  2. Arma el video con tu fondo, con un zoom muy lento. El fondo puede ser un PNG que ya
     tengas (fondo.png) o generarse acá con --titulo (usa fondo.py: título + subtítulo).
  3. Superpone tu foto circular + "Voz: Fede" que aparece y desaparece.
  4. Genera la miniatura (usa miniatura.py, que debe estar en la misma carpeta).

Requisitos: Python 3, Pillow (pip install pillow), ffmpeg y auto-editor
(pip install auto-editor) en el PATH.

Ejemplos:
  (desde la carpeta del proyecto)
  python crear_video.py audio.mp3 --modo meditacion --titulo "Sentir sin cambiar nada" --palabra "CALMA"
  python crear_video.py audio.mp3 --modo charla --titulo "Mitos de la meditación" --subtitulo "Cómo empezar sin complicarte"
  (o con un fondo.png ya hecho en la carpeta)
  python crear_video.py audio.mp3 --modo meditacion --palabra "CALMA"
  python crear_video.py charla.mp3 --modo charla --palabra "ENFOQUE"
  python crear_video.py audio.mp3 --modo meditacion --fondo otro.png --sin-foto
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

AQUI = Path(__file__).resolve().parent
# Carpeta "madre" de los recursos: si el script vive en ...\05-VIDEO_MAKING\scripts,
# los recursos están en ...\05-VIDEO_MAKING\fondos, \foto y \fuentes.
RAIZ = AQUI.parent if AQUI.name.lower() == "scripts" else AQUI
ANCHO, ALTO, FPS = 1920, 1080, 24

FUENTES_RESPALDO = [
    "C:/Windows/Fonts/georgiai.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/google-fonts/ofl/gelasio/Gelasio-Italic[wght].ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/Library/Fonts/Georgia.ttf",
]


def correr(cmd, descripcion):
    print(f"-> {descripcion}")
    # encoding explícito: en Windows el default (cp1252) rompe con la salida UTF-8 de auto-editor
    r = subprocess.run([str(c) for c in cmd], capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"\nFalló: {descripcion}\n{' '.join(map(str, cmd))}\n\n{r.stderr[-1500:]}")
    return r.stdout


def duracion(archivo: Path) -> float:
    out = correr(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", archivo],
        f"Leyendo duración de {archivo.name}",
    )
    return float(out.strip())


def a_segundos(txt: str) -> float:
    """'85', '85.5', '1:25' o '1:02:05' -> segundos."""
    partes = [float(x) for x in txt.strip().split(":")]
    seg = 0.0
    for x in partes:
        seg = seg * 60 + x
    return seg


def rangos_a_auto_editor(rangos):
    """['1:25-1:32', '4:10-4:16'] -> ['85s,92s', '250s,256s'] (auto-editor exige unidad)."""
    salida = []
    for r in rangos:
        try:
            ini, fin = r.split("-", 1)
            ini, fin = a_segundos(ini), a_segundos(fin)
        except ValueError:
            sys.exit(f"Rango inválido: '{r}'. Usá DESDE-HASTA, por ejemplo 1:25-1:32 o 85-92")
        if fin <= ini:
            sys.exit(f"Rango inválido: '{r}' (el final tiene que ser mayor que el inicio)")
        salida.append(f"{ini:g}s,{fin:g}s")
    return salida


def cargar_fuente(ruta, tam):
    for c in ([ruta] if ruta else []) + FUENTES_RESPALDO:
        try:
            return ImageFont.truetype(c, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def crear_insignia(foto: Path, texto: str, fuente: str | None, destino: Path):
    """PNG con la foto circular (aro crema) + texto a la derecha. Devuelve (ancho, alto)."""
    D, aro, sep = 220, 6, 28
    f = cargar_fuente(fuente, 44)
    medidor = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    l, t, r, b = medidor.textbbox((0, 0), texto, font=f)
    w_texto = r - l
    W, H = D + 2 * aro + sep + w_texto + 30, D + 2 * aro
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # aro
    d = ImageDraw.Draw(lienzo)
    d.ellipse((0, 0, D + 2 * aro - 1, D + 2 * aro - 1), fill=(255, 246, 234, 235))

    # foto circular (recorte cuadrado centrado, con suavizado de borde)
    img = Image.open(foto).convert("RGB")
    lado = min(img.size)
    x0, y0 = (img.width - lado) // 2, (img.height - lado) // 2
    img = img.crop((x0, y0, x0 + lado, y0 + lado)).resize((D, D), Image.LANCZOS)
    mascara = Image.new("L", (D * 4, D * 4), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, D * 4 - 1, D * 4 - 1), fill=255)
    mascara = mascara.resize((D, D), Image.LANCZOS)
    lienzo.paste(img, (aro, aro), mascara)

    # texto con sombra suave
    tx, ty = D + 2 * aro + sep, H // 2
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text((tx + 2, ty + 3), texto, font=f, fill=(0, 0, 0, 150), anchor="lm")
    sombra = sombra.filter(ImageFilter.GaussianBlur(3))
    lienzo = Image.alpha_composite(lienzo, sombra)
    ImageDraw.Draw(lienzo).text((tx, ty), texto, font=f, fill=(255, 246, 234, 255), anchor="lm")
    lienzo.save(destino)
    return W, H


def ventanas(modo, total, inicio, dur, cada):
    """Lista de (desde, hasta) en segundos en que aparece la foto."""
    v = []
    if inicio + dur <= total:
        v.append((inicio, inicio + dur))
    if cada and cada > 0:
        t = inicio + cada
        while t + dur <= total - 2:
            v.append((t, t + dur))
            t += cada
    elif modo == "meditacion" and total > 4 * dur + inicio:
        fin = total - dur - 5          # una vez más hacia el final
        v.append((fin, fin + dur))
    return v


def main():
    for flujo in (sys.stdout, sys.stderr):      # que la consola nunca rompa por acentos
        try:
            flujo.reconfigure(errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="Audio -> video mp4 + miniatura.")
    p.add_argument("audio", help="Audio grabado/exportado (mp3, wav, ...)")
    p.add_argument("--modo", choices=["meditacion", "charla"], required=True)
    p.add_argument("--fondo", help="PNG 1920x1080 exportado de Canva (default: fondo.png en la carpeta actual)")
    p.add_argument("--palabra", help="Palabra para la miniatura (si se omite, no se genera)")
    p.add_argument("--titulo", help="Título del video: genera el fondo (fondo.png) con fondo.py. Usá | para saltos de línea")
    p.add_argument("--subtitulo", help="Subtítulo del fondo (meditación: 'Meditación guiada' por defecto)")
    p.add_argument("--estilo", choices=["noche", "dia"], help="Estilo del fondo (default: noche en meditación, dia en charla)")
    p.add_argument("--fuente-subtitulo", choices=["cardo", "aileron"], help="Fuente del subtítulo del fondo")
    p.add_argument("--sombra", action="store_true", help="Sombra suave en los textos del fondo")
    p.add_argument("--fondo-miniatura", help="PNG sin texto para la miniatura (default: fondos/noche_limpio.png o dia_limpio.png según el modo; si no existe, el mismo --fondo)")
    p.add_argument("--salida", default="listo", help="Carpeta de salida (default: ./listo)")
    p.add_argument("--nombre", help="Nombre base de los archivos (default: el del audio)")
    p.add_argument("--sin-cortes", action="store_true", help="No cortar silencios (en charla; en meditación ya es el default)")
    p.add_argument("--con-cortes", action="store_true", help="Cortar silencios también en meditación (por defecto no corta)")
    p.add_argument("--mantener", action="append", metavar="DESDE-HASTA",
                   help="Tramo del audio original que NO se corta aunque sea silencio (pausas que valen). "
                        "Ej: --mantener 1:25-1:32  (se puede repetir). Tiempos como en Audacity.")
    p.add_argument("--margen", default="0.2sec", help="Margen de auto-editor en modo charla (default 0.2sec)")
    p.add_argument("--sin-foto", action="store_true", help="No superponer la foto")
    p.add_argument("--foto", help="Foto (se recorta en círculo). Default: foto/avatar_circulo.png junto a los scripts")
    p.add_argument("--texto-foto", default="Voz: Fede")
    p.add_argument("--fuente", help="Ruta a un .ttf para el texto de la foto y la miniatura (default: primer .ttf/.otf de fuentes/)")
    p.add_argument("--foto-inicio", type=float, default=3, help="Segundo en que aparece la primera vez (default 3)")
    p.add_argument("--foto-dur", type=float, default=6, help="Segundos visible cada vez (default 6)")
    p.add_argument("--foto-cada", type=float, default=None,
                   help="Repetir cada N segundos. Default: 0 en meditación (inicio y final), 120 en charla")
    p.add_argument("--zoom", type=float, default=0.08, help="Zoom máximo del fondo, 0 = sin zoom (default 0.08)")
    p.add_argument("--calidad", type=int, default=20, help="CRF de x264, menor = mejor (default 20)")
    a = p.parse_args()

    # --- valores por defecto a partir de la carpeta de recursos -------------
    print(f"== crear_video | modo: {a.modo} | audio: {a.audio}", flush=True)
    estilo = a.estilo or ("noche" if a.modo == "meditacion" else "dia")
    if a.titulo:
        if a.fondo:
            print("Aviso: se indicó --fondo y --titulo; se usa --fondo y se ignora el título.", flush=True)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location("fondo", AQUI / "fondo.py")
            fondo_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fondo_mod)
            print(f"-> Generando fondo ({estilo}): {a.titulo.replace('|', ' / ')}", flush=True)
            img_fondo = fondo_mod.generar(a.titulo, estilo, a.subtitulo, a.fuente_subtitulo, sombra=a.sombra)
            img_fondo.save("fondo.png")
            a.fondo = "fondo.png"
    if not a.fondo:
        a.fondo = "fondo.png"
        if not Path(a.fondo).exists():
            sys.exit("No hay fondo: poné un fondo.png en la carpeta o usá --titulo \"Tu título\" para generarlo.")
    if not a.foto:
        for c in (RAIZ / "foto" / "avatar_circulo.png", AQUI / "avatar_circulo.png"):
            if c.exists():
                a.foto = str(c)
                break
        else:
            a.foto = str(RAIZ / "foto" / "avatar_circulo.png")
    cardo = RAIZ / "fuentes" / "Cardo"
    fuente_badge = a.fuente or (str(cardo / "Cardo-Regular.ttf") if (cardo / "Cardo-Regular.ttf").exists() else None)
    fuente_mini = a.fuente or (str(cardo / "Cardo-Bold.ttf") if (cardo / "Cardo-Bold.ttf").exists() else None)
    if not a.fondo_miniatura:
        limpio = RAIZ / "fondos" / f"{estilo}_limpio.png"
        a.fondo_miniatura = str(limpio) if limpio.exists() else None

    print(f"   fondo: {a.fondo}", flush=True)
    audio, fondo = Path(a.audio), Path(a.fondo)
    for f in (audio, fondo):
        if not f.exists():
            sys.exit(f"No existe: {f}")
    # Meditación: NO corta silencios salvo que lo pidas (--con-cortes).
    # Charla: corta salvo que pidas --sin-cortes.
    cortar = a.con_cortes if a.modo == "meditacion" else not a.sin_cortes
    if a.sin_cortes:
        cortar = False
    for exe in ("ffmpeg", "ffprobe") + (("auto-editor",) if cortar else ()):
        if not shutil.which(exe):
            extra = " (pip install auto-editor)" if exe == "auto-editor" else ""
            sys.exit(f"No encuentro '{exe}' en el PATH{extra}")

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    base = a.nombre or audio.stem
    # Si corrés el script dentro de una carpeta de proyecto AAAA_MM_DD-slug, el video final
    # se llama como la carpeta (conserva la fecha) y la miniatura se llama "miniatura.jpg".
    carpeta = Path.cwd().name
    if not a.nombre and re.match(r"^\d{4}_\d{2}_\d{2}-", carpeta):
        nombre_video, nombre_mini = f"{carpeta}.mp4", "miniatura.jpg"
    else:
        nombre_video, nombre_mini = f"{base}_video.mp4", f"{base}_miniatura.jpg"
    tmp = Path(tempfile.mkdtemp(prefix="crear_video_"))

    # 1) cortar silencios -------------------------------------------------
    audio_final = audio
    if cortar:
        cortado = tmp / f"cortado{audio.suffix or '.mp3'}"
        cmd = ["auto-editor", audio]
        if a.modo == "charla":
            cmd += ["--margin", a.margen]
        if a.mantener:
            for rango in rangos_a_auto_editor(a.mantener):   # un --add-in por tramo
                cmd += ["--add-in", rango]
        cmd += ["-o", cortado]
        print(f"-> Cortando silencios ({a.modo})... (puede tardar según la duración del audio)", flush=True)
        # --no-open evita que Windows abra el audio cortado en el reproductor
        r = subprocess.run([str(c) for c in cmd + ["--no-open"]], capture_output=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0 and "no-open" in (r.stderr or "").lower():
            correr(cmd, f"Cortando silencios ({a.modo})")      # auto-editor viejo sin --no-open
        elif r.returncode != 0:
            sys.exit(f"\nFalló: Cortando silencios ({a.modo})\n{r.stderr[-1500:]}")
        else:
            print("   listo", flush=True)
        if not cortado.exists():
            sys.exit("auto-editor no generó el archivo de salida.")
        audio_final = cortado
    if not cortar:
        print("-> Sin cortes de silencio (se usa el audio tal cual)")
    total = duracion(audio_final)
    print(f"   duración: {total/60:.1f} min")

    # 2) filtros de video -------------------------------------------------
    if a.zoom > 0:
        amp = a.zoom / 2
        fondo_f = (
            f"[0:v]scale=w='trunc({ANCHO}*(1+{amp}-{amp}*cos(2*PI*t/120))/2)*2':h=-2:eval=frame,"
            f"crop={ANCHO}:{ALTO},format=yuv420p[bg]"
        )
    else:
        fondo_f = f"[0:v]scale={ANCHO}:{ALTO},format=yuv420p[bg]"

    entradas = ["-loop", "1", "-framerate", str(FPS), "-i", fondo, "-i", audio_final]
    partes = [fondo_f]
    ultimo = "bg"

    wins = []
    if not a.sin_foto:
        foto = Path(a.foto)
        if not foto.exists():
            sys.exit(f"No existe la foto: {foto} (usá --foto RUTA o --sin-foto)")
        cada = a.foto_cada if a.foto_cada is not None else (120 if a.modo == "charla" else 0)
        wins = ventanas(a.modo, total, a.foto_inicio, a.foto_dur, cada)

    if wins:
        insignia = tmp / "insignia.png"
        w, h = crear_insignia(Path(a.foto), a.texto_foto, fuente_badge, insignia)
        x, y = 70, ALTO - 70 - h
        entradas += ["-loop", "1", "-framerate", str(FPS), "-i", insignia]
        n = len(wins)
        etiquetas = "".join(f"[o{i}]" for i in range(n))
        partes.append(f"[2:v]format=rgba,split={n}{etiquetas}" if n > 1 else "[2:v]format=rgba[o0]")
        for i, (d, h_) in enumerate(wins):
            partes.append(
                f"[o{i}]fade=t=in:st={d:.2f}:d=0.8:alpha=1,fade=t=out:st={h_-0.8:.2f}:d=0.8:alpha=1[f{i}]"
            )
            sig = f"v{i}"
            partes.append(
                f"[{ultimo}][f{i}]overlay=x={x}:y={y}:enable='between(t,{d:.2f},{h_:.2f})'[{sig}]"
            )
            ultimo = sig
        print(f"   foto: aparece {len(wins)} vez/veces")

    # 3) render ------------------------------------------------------------
    video = salida / nombre_video
    cmd = (
        ["ffmpeg", "-y", "-loglevel", "error", "-stats"] + entradas +
        ["-filter_complex", ";".join(partes), "-map", f"[{ultimo}]", "-map", "1:a",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(a.calidad),
         "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", video]
    )
    correr(cmd, "Armando el video (puede tardar un poco en audios largos)")
    print(f"   listo: {video}")

    # 4) miniatura ---------------------------------------------------------
    if a.palabra:
        mini = salida / nombre_mini
        cmd = [sys.executable, AQUI / "miniatura.py", a.fondo_miniatura or fondo, a.palabra,
               "--salida", mini]
        if fuente_mini:
            cmd += ["--fuente", fuente_mini]
        correr(cmd, "Generando miniatura")
        print(f"   listo: {mini}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nTodo listo en:", salida.resolve())


if __name__ == "__main__":
    main()
