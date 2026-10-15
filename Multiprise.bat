@echo off
rem Multiprise -- repartiteur de flux UDP (NMEA 0183) pour Windows
rem Copyright (C) 2026 ETDEL -- GPL-3.0-or-later (voir LICENSE)
rem Multiprise, par ETDEL -- https://github.com/theptitprince/Multiprise
rem Licence GPL-3.0-or-later avec conditions additionnelles (article 7) :
rem voir le fichier NOTICE, qui impose de conserver la mention ci-dessus.
rem
rem Lance multiprise.py par double-clic, sans fenetre de console (pythonw).
rem Si Python ou tkinter manque, le dit au lieu de ne rien afficher.

setlocal EnableExtensions
pushd "%~dp0" || goto :no_folder
if not exist "multiprise.py" goto :no_sources

rem "python" d'abord, le lanceur "py" en repli ; on lance ensuite la
rem variante sans console du MEME Python (pythonw / pyw).
set "PYW="
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PYW=pythonw"
if not defined PYW (
    py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PYW=pyw -3"
)
if not defined PYW goto :no_python

start "" %PYW% "%~dp0multiprise.py"
popd
endlocal
exit /b 0

:no_folder
echo [!!]  Impossible d'entrer dans le dossier de ce script.
goto :end_error_nopop

:no_sources
echo [!!]  multiprise.py est introuvable : placez Multiprise.bat a cote.
goto :end_error

:no_python
echo [!!]  Aucun Python 3.8 ou plus recent avec tkinter n'a ete trouve.
echo       Installez-le depuis https://www.python.org/downloads/ en cochant
echo       "Add Python to PATH" et "tcl/tk and IDLE", puis relancez.
echo       installer_dependances.bat dit precisement ce qui manque.
goto :end_error

:end_error
popd
:end_error_nopop
echo.
pause
endlocal
exit /b 1
