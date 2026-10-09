@echo off
rem Trener Doty: igra vdvoem odnim fajlom (reshenie D14). Zapuskaet host; vsyo ostalnoe delaet coach\play.py:
rem klyuch, kastomka v Dotu, tunnel Cloudflare, server, fajl dlya druga, zapusk Doty.
rem Etot fajl mozhno skachat otdelno: ryadom poyavitsya papka DotaCoach s fajlami igry.
setlocal EnableExtensions DisableDelayedExpansion
title Dota coach - igra vdvoem
cd /d "%~dp0"
set "HERE=%~dp0"
set "RAW=https://raw.githubusercontent.com/131ymm-commits/Neu/ccr-9d6c6e9e-yuegyb/games/Dota2_VoiceCoach"
set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command [Net.ServicePointManager]::SecurityProtocol='Tls12'; $ProgressPreference='SilentlyContinue';"

rem --- papka igry: ryadom s etim fajlom ili DotaCoach ---
if exist "%HERE%coach\voicecoach\play.py" (set "PROJ=%HERE%") else (set "PROJ=%HERE%DotaCoach\")
set "RT=%PROJ%.runtime"
if not exist "%RT%" mkdir "%RT%"

rem --- Python 3.10+: ustanovlennyj (py) ili svoj v .runtime\python ---
set "PYEXE="
set "PYARG="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYEXE=py" && set "PYARG=-3"
if not defined PYEXE if exist "%RT%\python\python.exe" set "PYEXE=%RT%\python\python.exe"
if defined PYEXE goto have_python
echo Skachivayu Python - odin raz, okolo 10 MB...
%PS% Invoke-WebRequest -UseBasicParsing -Uri '%PYURL%' -OutFile '%RT%\python.zip'; Expand-Archive -Force '%RT%\python.zip' '%RT%\python'; Remove-Item '%RT%\python.zip'
if exist "%RT%\python\python.exe" set "PYEXE=%RT%\python\python.exe"
if defined PYEXE goto have_python
echo Ne udalos skachat Python. Postavte ego s python.org i zapustite etot fajl snova.
pause
exit /b 1
:have_python

rem --- obnovit fajly igry: git pull dlya kopii iz git, inache - izmenivshiesya fajly s GitHub ---
if exist "%PROJ%..\..\.git" goto git_copy
if exist "%PROJ%coach\voicecoach\update.py" goto run_update
if not exist "%PROJ%coach\voicecoach" mkdir "%PROJ%coach\voicecoach"
%PS% Invoke-WebRequest -UseBasicParsing -Uri '%RAW%/coach/voicecoach/update.py' -OutFile '%PROJ%coach\voicecoach\update.py'
:run_update
"%PYEXE%" %PYARG% -X utf8 "%PROJ%coach\voicecoach\update.py" "%PROJ%."
if errorlevel 1 (
  pause
  exit /b 1
)
goto launch
:git_copy
where git >nul 2>nul && git -C "%PROJ%..\.." pull --ff-only --quiet
:launch

rem --- launcher ---
"%PYEXE%" %PYARG% -X utf8 "%PROJ%coach\play.py" %*
echo.
pause
endlocal
