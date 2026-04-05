@echo off
cd /d "%~dp0"
echo 1. Dossier actuel : %cd%
echo.

echo 2. Tentative d'activation de l'environnement virtuel...
call "C:\Users\DELL\OneDrive\Documents\Prject\ma_bulle\Scripts\activate.bat"
echo.

echo 3. Lancement de l'application Python...
python app.py
echo.

echo Fin du script.
pause