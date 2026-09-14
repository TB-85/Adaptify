@echo off
title Push Adaptify to GitHub
cd /d "c:\Users\Thomas\Desktop\AdaptiH5P"
echo ============================================================
echo   INITIALISERE GIT UND ADAPTIFY REPOSITORY...
echo ============================================================
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" init
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" config user.name "TB-85"
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" config user.email "thomas.benke@schule.bayern.de"
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" add .
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" commit -m "Upload complete Adaptify project for Render deploy"
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" branch -M main
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" remote remove origin 2>nul
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" remote add origin https://github.com/TB-85/Adaptify.git

echo ============================================================
echo   UPLOADE ADAPTIFY ZU GITHUB (https://github.com/TB-85/Adaptify)...
echo ============================================================
"c:\Users\Thomas\Desktop\AdaptiH5P\tools\git\cmd\git.exe" push -u origin main --force

echo ============================================================
echo   FERTIG! Das Projekt ist jetzt auf GitHub hochgeladen.
echo ============================================================
pause
