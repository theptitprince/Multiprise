@echo off
rem Multiprise -- repartiteur de flux UDP (NMEA 0183) pour Windows
rem Copyright (C) 2026 ETDEL -- GPL-3.0-or-later (voir LICENSE)
rem Multiprise, par ETDEL -- https://github.com/theptitprince/Multiprise
rem Licence GPL-3.0-or-later avec conditions additionnelles (article 7) :
rem voir le fichier NOTICE, qui impose de conserver la mention ci-dessus.
rem
rem Installe ce qui manque pour faire tourner multiprise.py :
rem   1. Python 3.8 ou plus recent, avec tkinter : verifies seulement. Ils
rem      ne s'installent pas avec pip ; s'ils manquent, le script dit quoi
rem      faire.
rem   2. pip : remis en place par "ensurepip" s'il a disparu.
rem   3. pystray et pillow : installes s'ils sont absents. Facultatifs, mais
rem      c'est grace a eux que la croix range la multiprise pres de
rem      l'horloge au lieu de couper le flux, et que la fenetre a son icone.
rem
rem Il faut une connexion internet pour l'etape 3. Python installe "pour
rem tous les utilisateurs" (Program Files) : pip installe alors les modules
rem dans le profil de l'utilisateur, sans droits d'administrateur.
rem
rem Les succes et echecs se lisent avec && et || plutot qu'avec
rem "if errorlevel 1" : ce dernier teste "code >= 1" et prendrait pour un
rem succes un Python qui plante (codes Windows negatifs).
rem
rem Usage : double-clic, ou "installer_dependances.bat" en invite de commande.

setlocal EnableExtensions
title Multiprise - installation des dependances
pushd "%~dp0" || goto :no_folder

echo ==============================================================
echo   Multiprise - installation des dependances
echo ==============================================================
echo.

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

%PY% -c "import tkinter" >nul 2>&1 || goto :no_tk
echo [OK]  tkinter est present.

rem ---------------------------------------------------------------------
rem 2. pystray et pillow deja la : rien a faire.
rem ---------------------------------------------------------------------
rem pystray 0.19 ou plus (run_detached) : plus ancien, la croix quitterait.
%PY% -c "import sys, pystray, PIL.ImageTk; sys.exit(0 if hasattr(pystray.Icon, 'run_detached') else 1)" >nul 2>&1 && goto :already

rem ---------------------------------------------------------------------
rem 3. pip, puis pystray et pillow
rem ---------------------------------------------------------------------
%PY% -m pip --version >nul 2>&1 && goto :have_pip
echo [--]  pip est absent : remise en place avec ensurepip...
%PY% -m ensurepip --upgrade >nul 2>&1
%PY% -m pip --version >nul 2>&1 || goto :no_pip
:have_pip
echo [OK]  pip est present.
echo.
echo Installation de pystray et pillow...
echo --------------------------------------------------------------
%PY% -m pip install --disable-pip-version-check --upgrade "pystray>=0.19" "pillow>=8.2"
echo --------------------------------------------------------------
%PY% -c "import sys, pystray, PIL.ImageTk; sys.exit(0 if hasattr(pystray.Icon, 'run_detached') else 1)" >nul 2>&1 || goto :pip_failed
echo.
echo [OK]  pystray et pillow sont installes.
goto :done

:already
echo [OK]  pystray et pillow sont deja installes.

:done
echo.
echo ==============================================================
echo   Tout est en place. Lancez Multiprise par double-clic sur
echo   Multiprise.bat.
echo ==============================================================
goto :end_ok

rem ---------------------------------------------------------------------
:no_folder
echo [!!]  Impossible d'entrer dans le dossier de ce script.
goto :end_error_nopop

:no_python
echo [!!]  Aucun Python 3.8 ou plus recent n'a ete trouve.
echo       Installez-le depuis https://www.python.org/downloads/ en cochant
echo       "Add Python to PATH" (premier ecran) et "tcl/tk and IDLE"
echo       (ecran "Optional Features"), puis relancez ce script.
goto :end_error

:no_tk
echo [!!]  tkinter est absent de ce Python : il dessine toute la fenetre,
echo       Multiprise ne peut pas s'ouvrir sans lui. Relancez
echo       l'installateur de Python, choisissez "Modify", cochez
echo       "tcl/tk and IDLE", puis relancez ce script.
goto :end_error

:no_pip
echo [!!]  pip est absent et n'a pas pu etre remis en place. Relancez
echo       l'installateur de Python, choisissez "Modify" et cochez "pip".
goto :end_error

:pip_failed
echo.
echo [!!]  pystray et pillow n'ont pas pu etre installes (voir les messages
echo       ci-dessus). Cause frequente : pas de connexion internet.
echo       Multiprise fonctionne sans eux : la croix ferme alors le
echo       programme au lieu de le ranger pres de l'horloge.
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
