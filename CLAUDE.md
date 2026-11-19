# Contexto para Claude

Proyecto de Fede (habla español rioplatense, voseo): caja de herramientas para
su canal de YouTube "meditawork" (meditación, breathwork, charlas). Responder
en español.

## Objetivo
Producir videos rápido y gratis: audio de Audacity → mp4 → miniatura, sin
Kdenlive ni Canva por video. El usuario solo cambia el título (y a veces el
subtítulo) en cada video.

## Estructura y convenciones
- Esta carpeta es la caja de herramientas; nada de un video concreto se guarda acá.
- Los proyectos viven en `D:\Videos\01-PROJECTS\AAAA_MM_DD-slug`. Dentro: nombres
  cortos por rol; el video final lleva el nombre de la carpeta (con fecha).
- Los scripts ubican recursos con `RAIZ` = carpeta padre de `scripts/`.
- El entorno de Claude puede no tener terminal en su PC (solo bridge de archivos):
  no se puede probar en Windows real; verificar en una réplica.

## Decisiones de diseño
- `crear_video.py`: `--modo meditacion|charla` obligatorio. Meditación: estilo
  noche, SIN cortar silencios (los controla en Audacity; `--con-cortes` lo fuerza).
  Charla: estilo día, auto-editor `--margin 0.2sec`; `--mantener DESDE-HASTA`
  (repetible) conserva pausas largas vía `--add-in` (requiere unidades: `8s,14s`).
- `fondo.py`: dibuja título/subtítulo/marca con Pillow (supersampling x4, kerning
  y tracking por carácter) replicando posiciones de Canva. Títulos de 2 líneas con
  `|`; si es largo se parte y/o achica solo. `reparar_marca()` tapa una marca
  residual en `dia_limpio.png`.
- Tipografías: título Cardo; subtítulos Aileron (ambos estilos); marca "meditawork"
  en Raleway ("medita" Bold + "work" Regular); miniatura Cardo Bold; insignia Cardo.
- Fondo animado con zoom lento + insignia con foto: para variar el contenido y
  no parecer imagen estática repetitiva (política de contenido inauténtico de YouTube).

## Gotchas de Windows
- Decodificar subprocess con `encoding="utf-8", errors="replace"` (cp1252 rompía).
- auto-editor con `--no-open` (si no abría Windows Media Player).
- Archivos entregados con saltos de línea CRLF. Notepad lee mal `.md`: la
  documentación para el usuario es `LEEME.txt`; `README.md` es para GitHub.
- Imprimir mensajes de progreso ANTES de operaciones largas.

## Git
- Remoto: https://github.com/fpradomacat/video-making.git
- `*.wav` está en `.gitignore` (GitHub rechaza archivos >100 MB).

## Al cambiar cosas
- Verificar contra los fondos y fuentes reales; no afirmar sin comprobar.
- Mantener `LEEME.txt` actualizado si cambian opciones.
