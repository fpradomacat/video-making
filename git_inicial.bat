@echo off
cd /d "%~dp0"
git init -b main
git remote add origin https://github.com/fpradomacat/video-making.git
git add -A
git commit -m "Herramientas de video: crear_video, fondo, miniatura, fuentes, musica"
echo.
echo Listo el commit. Para subirlo: git push -u origin main
pause
