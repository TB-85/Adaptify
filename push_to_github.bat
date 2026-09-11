@echo off
title Push Adaptify to GitHub
cd /d "%~dp0"
echo ============================================================
echo   INITIALISERE GIT UND ADAPTIFY REPOSITORY...
echo ============================================================
tools\git\cmd\git.exe init
tools\git\cmd\git.exe config user.name "TB-85"
tools\git\cmd\git.exe config user.email "thomas.benke@schule.bayern.de"
tools\git\cmd\git.exe add .
tools\git\cmd\git.exe commit -m "Initial commit for 24/7 Render deployment"
tools\git\cmd\git.exe branch -M main
tools\git\cmd\git.exe remote remove origin 2>nul
tools\git\cmd\git.exe remote add origin https://github.com/TB-85/AdaptiH5P.git

echo ============================================================
echo   UPLOADE ADAPTIFY ZU GITHUB (https://github.com/TB-85/AdaptiH5P)...
echo ============================================================
tools\git\cmd\git.exe push -u origin main

echo ============================================================
echo   FERTIG! Das Projekt ist jetzt auf GitHub hochgeladen.
echo ============================================================
pause
