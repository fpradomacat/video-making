@echo off
cd /d "%~dp0"
echo == Usar main como rama principal ==

rem 1) Renombrar la rama local a main
git branch -M main

rem 2) Asegurar que los .wav no estan en el repo y que todo esta commiteado
git rm -r --cached --ignore-unmatch --quiet music
git add -A
git commit -m "Herramientas de video: crear_video, fondo, miniatura, fuentes, musica" 2>nul
git status --short

rem 3) Subir main
git push -u origin main
if errorlevel 1 (
  echo.
  echo No se pudo subir main. Revisa el error de arriba.
  pause
  exit /b 1
)

rem 4) Hacer main la rama por defecto en GitHub (requiere GitHub CLI: gh)
where gh >nul 2>nul
if %errorlevel%==0 (
  gh repo edit fpradomacat/video-making --default-branch main
) else (
  echo.
  echo Sin GitHub CLI: cambia la rama por defecto a mano en
  echo https://github.com/fpradomacat/video-making/settings/branches
  echo y despues vuelve a correr este script para borrar master.
  pause
  exit /b 0
)

rem 5) Borrar master remota (si existe)
git ls-remote --exit-code --heads origin master >nul 2>nul
if %errorlevel%==0 (
  git push origin --delete master
) else (
  echo No hay rama master en GitHub; nada que borrar.
)

rem 6) Borrar master local (si existe)
git branch -D master 2>nul

echo.
echo Listo. Rama principal: main
pause
