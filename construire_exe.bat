@echo off
rem Multiprise -- repartiteur de flux UDP (NMEA 0183) pour Windows
rem Copyright (C) 2026 ETDEL -- GPL-3.0-or-later (voir LICENSE)
rem Multiprise, par ETDEL -- https://github.com/theptitprince/Multiprise
rem Licence GPL-3.0-or-later avec conditions additionnelles (article 7) :
rem voir le fichier NOTICE, qui impose de conserver la mention ci-dessus.
rem
rem Construit Multiprise.exe : un executable Windows AUTONOME (Python et
rem tkinter embarques), qui se lance sans rien installer sur le poste qui
rem le recoit.
rem
rem Etapes :
rem   1. trouver le Python du poste de construction ;
rem   2. verifier tkinter, reperer pystray et pillow (facultatifs) ;
rem   3. installer PyInstaller s'il manque ;
rem   4. dessiner l'icone (la multiprise bleue) -- multiprise.write_ico,
rem      aucun fichier image a distribuer ;
rem   5. empaqueter, puis poser Multiprise.exe A COTE de multiprise.py.
rem
rem Pourquoi a cote de multiprise.py : l'exe range sa configuration
rem (multiprise_config.json) a cote de LUI-MEME. Pose ici, il retrouve donc
rem les prises deja reglees en lancant multiprise.py -- et inversement.
rem
rem Les succes et echecs se lisent avec && et || plutot qu'avec
rem "if errorlevel 1" : ce dernier teste "code >= 1" et prendrait pour un
rem succes un Python qui plante (codes Windows negatifs).
rem
rem Usage : double-clic, ou "construire_exe.bat" en invite de commande.

setlocal EnableExtensions
title Multiprise - construction de Multiprise.exe
rem pushd plutot que cd : il sait aussi entrer dans un dossier reseau
rem (\\serveur\partage), en lui pretant une lettre de lecteur. Sans lui, un
rem cd rate laisserait le script travailler dans un AUTRE dossier.
pushd "%~dp0" || goto :no_folder

echo ==============================================================
echo   Multiprise - construction de Multiprise.exe
echo ==============================================================
echo.

if not exist "multiprise.py" goto :no_sources

rem ---------------------------------------------------------------------
rem 1. Python (3.8 ou plus recent) : "python" d'abord, le lanceur "py" en
rem    repli. L'alias du Microsoft Store (python.exe qui ouvre le Store)
rem    echoue au test de version et n'est donc jamais retenu.
rem ---------------------------------------------------------------------
set "PY="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PY=py -3"
)
if not defined PY goto :no_python

echo Python utilise :
%PY% -c "import sys; print('  ' + sys.executable); print('  version ' + sys.version.split()[0])"
echo.

rem ---------------------------------------------------------------------
rem 2. Ce que l'exe doit embarquer : tkinter. pystray et pillow sont
rem    facultatifs -- embarques s'ils sont la (zone de notification, icone
rem    de la fenetre et de l'exe), sinon l'exe se ferme simplement a la
rem    croix au lieu de se ranger pres de l'horloge.
rem ---------------------------------------------------------------------
%PY% -c "import tkinter" >nul 2>&1 || goto :no_tk
echo [OK]  tkinter est present.
set "TRAY_OK=0"
rem pystray 0.19 ou plus (run_detached) : plus ancien, la croix quitterait.
%PY% -c "import sys, pystray, PIL.ImageTk; sys.exit(0 if hasattr(pystray.Icon, 'run_detached') else 1)" >nul 2>&1 && set "TRAY_OK=1"
if "%TRAY_OK%"=="1" (
    echo [OK]  pystray et pillow seront embarques.
) else (
    echo [--]  pystray/pillow absents : l'exe n'aura ni zone de notification
    echo       ni icone. Pour les avoir : lancez installer_dependances.bat,
    echo       puis relancez ce script.
)
echo.

rem ---------------------------------------------------------------------
rem 3. PyInstaller
rem ---------------------------------------------------------------------
%PY% -m PyInstaller --version >nul 2>&1 && goto :have_pyinstaller
echo Installation de PyInstaller...
echo --------------------------------------------------------------
%PY% -m pip install --disable-pip-version-check pyinstaller
%PY% -m PyInstaller --version >nul 2>&1 || goto :no_pyinstaller
echo.
:have_pyinstaller
for /f "delims=" %%v in ('%PY% -m PyInstaller --version') do echo [OK]  PyInstaller %%v
echo.

rem ---------------------------------------------------------------------
rem 4. L'icone, dessinee par le programme lui-meme (il faut pillow)
rem
rem   --icon : chemin ABSOLU, PyInstaller resout les chemins relatifs
rem   depuis le dossier du .spec, pas depuis celui-ci.
rem ---------------------------------------------------------------------
if not exist "build" mkdir "build"
set "ICON_OPT="
set "TRAY_OPT="
if "%TRAY_OK%"=="0" goto :no_icon
%PY% -c "import multiprise; multiprise.write_ico(r'build\multiprise.ico')" || goto :no_icon_warn
set ICON_OPT=--icon "%~dp0build\multiprise.ico"
set "TRAY_OPT=--hidden-import pystray._win32 --hidden-import PIL._tkinter_finder"
echo [OK]  Icone generee (la multiprise bleue).
echo.
goto :package

:no_icon_warn
echo [--]  L'icone n'a pas pu etre generee : l'exe gardera l'icone par defaut.
echo.
:no_icon

rem ---------------------------------------------------------------------
rem 5. Empaquetage
rem
rem   --onefile   un seul fichier a copier
rem   --windowed  pas de fenetre noire de console
rem   --exclude-module numpy  Pillow l'importe s'il est la, Multiprise n'en
rem               a pas besoin : une douzaine de Mo de moins dans l'exe
rem
rem Le Multiprise.exe existant n'est PAS supprime avant : si la
rem construction echoue, on garde celui qui marchait. On verifie seulement
rem qu'il n'est pas en cours d'utilisation (ouverture en ajout, sans rien
rem ecrire), sans quoi le remplacement final echouerait apres plusieurs
rem minutes de travail.
rem ---------------------------------------------------------------------
:package
if exist "Multiprise.exe" (
    2>nul (>>"Multiprise.exe" call;) || goto :exe_locked
)
echo Empaquetage (une a plusieurs minutes)...
echo --------------------------------------------------------------
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name Multiprise ^
    --exclude-module numpy ^
    %ICON_OPT% ^
    --distpath "%~dp0build\dist" ^
    --workpath "%~dp0build\work" ^
    --specpath "%~dp0build" ^
    %TRAY_OPT% ^
    multiprise.py || goto :build_failed
if not exist "build\dist\Multiprise.exe" goto :build_failed
move /y "build\dist\Multiprise.exe" "Multiprise.exe" >nul || goto :build_failed
rmdir /s /q "build" >nul 2>&1
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>&1

echo.
echo ==============================================================
echo   Multiprise.exe est pret, a cote de multiprise.py :
echo     "%~dp0Multiprise.exe"
echo ==============================================================
echo   Il partage la configuration de ce dossier
echo   (multiprise_config.json). Pour un autre poste : copiez
echo   Multiprise.exe seul, dans son propre dossier -- il y creera
echo   sa configuration.
echo.
echo   Premier lancement : autorisez Multiprise.exe dans le pare-feu
echo   Windows (reseau PRIVE), sinon les prises n'entendront rien du
echo   reseau -- le pare-feu autorise un executable, pas un programme.
echo.
echo   L'exe n'est pas signe : SmartScreen peut afficher un
echo   avertissement, "Informations complementaires" puis
echo   "Executer quand meme".
goto :end_ok

rem ---------------------------------------------------------------------
:no_folder
echo [!!]  Impossible d'entrer dans le dossier de ce script.
goto :end_error_nopop

:no_sources
echo [!!]  multiprise.py est introuvable : placez ce script dans le dossier
echo       de Multiprise, a cote de multiprise.py, puis relancez-le.
goto :end_error

:no_python
echo [!!]  Aucun Python 3.8 ou plus recent n'a ete trouve.
echo       Installez-le depuis https://www.python.org/downloads/ (cochez
echo       "Add Python to PATH" et "tcl/tk and IDLE"), puis relancez.
goto :end_error

:no_tk
echo [!!]  tkinter est absent de ce Python : relancez l'installateur de
echo       Python, choisissez "Modify" et cochez "tcl/tk and IDLE".
goto :end_error

:no_pyinstaller
echo.
echo [!!]  PyInstaller n'a pas pu etre installe (voir le message ci-dessus).
echo       Pas d'internet sur ce poste ? Telechargez ailleurs le paquet
echo       .whl de PyInstaller et ses dependances, puis installez-les avec
echo       "%PY% -m pip install --no-index --find-links <dossier> pyinstaller".
goto :end_error

:exe_locked
echo [!!]  Multiprise.exe est en cours d'utilisation : quittez Multiprise
echo       (icone pres de l'horloge -- clic droit, Quitter), puis relancez.
goto :end_error

:build_failed
echo.
echo [!!]  L'empaquetage a echoue (voir les messages ci-dessus).
echo       Cause frequente : un antivirus qui bloque PyInstaller.
echo       Le dossier build\ est conserve pour examen ; l'ancien
echo       Multiprise.exe, s'il y en avait un, est intact.
goto :end_error

:end_ok
echo.
pause
popd
endlocal
exit /b 0

:end_error
popd
:end_error_nopop
echo.
pause
endlocal
exit /b 1
