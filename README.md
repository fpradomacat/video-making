# video-making

Herramientas para producir videos de YouTube en español (canal de meditación,
respiración y charlas) sin editor de video: **audio → mp4 con fondo de marca →
miniatura**, todo desde la terminal.

Pensado para usarse con la estructura de carpetas de Fede en Windows
(`D:\Videos\03-VIDEO_MAKING`), pero los scripts encuentran sus recursos por
ubicación relativa, así que funcionan desde cualquier carpeta.

## Qué hace

| Script | Para qué |
|---|---|
| `scripts/crear_video.py` | Audio → mp4 (fondo con zoom lento, insignia "Voz: Fede" que aparece y desaparece) + miniatura. En modo charla corta silencios con auto-editor. |
| `scripts/fondo.py` | Genera el fondo 1920x1080 (título, subtítulo, marca "meditawork") a partir de fondos limpios. |
| `scripts/miniatura.py` | Miniatura 1280x720 con una palabra o frase sobre el fondo. |
| `music/meditacion_loop.py` | Generador parametrizable de música de fondo para meditaciones. |

Los `.bat` de la raíz (`crear_video.bat`, `miniatura.bat`) son lanzadores.

## Uso rápido

```
crear_video audio.mp3 --modo meditacion --titulo "Sentir sin cambiar nada" --palabra "CALMA"
crear_video audio.mp3 --modo charla --titulo "Por qué nos cuesta soltar|el control" --subtitulo "Charla sobre incertidumbre" --palabra "Soltar el control"
```

- **meditacion**: estilo noche, no corta silencios.
- **charla**: estilo día, corta silencios.

Documentación completa de opciones en [`LEEME.txt`](LEEME.txt).

## Requisitos

- Python 3 con `pillow` y `auto-editor` (`pip install pillow auto-editor`)
- `ffmpeg` y `ffprobe` en el PATH

## Estructura

```
scripts/    scripts de Python
fondos/     fondos limpios (sin texto) exportados de Canva
foto/       avatar circular para la insignia
fuentes/    Cardo, Aileron, Raleway
music/      música de fondo (los .wav no se suben a Git)
```

Las fuentes tienen licencia OFL (ver los `OFL.txt` incluidos).
