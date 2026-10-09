@echo off
rem Trener Doty: igra vdvoem odnim fajlom (reshenie D14). Zapuskaet host; vsyo ostalnoe delaet coach\play.py:
rem klyuch, kastomka v Dotu, tunnel Cloudflare, server, fajl dlya druga, zapusk Doty.
rem Etot fajl mozhno skachat otdelno: ryadom poyavitsya papka DotaCoach s fajlami igry.
rem Obnovlenie i zapusk igry - odnoj strokoj v konce: cmd chitaet .bat po strokam, a obnovlenie menyaet i etot fajl.
setlocal EnableExtensions DisableDelayedExpansion
title Dota coach - igra vdvoem
cd /d "%~dp0"
set "HERE=%~dp0"
set "RAW1=https://raw.githubusercontent.com/131ymm-commits/Neu/ccr-9d6c6e9e-yuegyb/games/Dota2_VoiceCoach"
set "RAW2=https://raw.githubusercontent.com/131ymm-commits/Neu/main/games/Dota2_VoiceCoach"
set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command"
set "NET=[Net.ServicePointManager]::SecurityProtocol='Tls12'; $ProgressPreference='SilentlyContinue';"

rem --- papka igry: ryadom s etim fajlom ili DotaCoach ---
if exist "%HERE%coach\voicecoach\play.py" (set "PROJ=%HERE%") else (set "PROJ=%HERE%DotaCoach\")
set "RT=%PROJ%.runtime"
if not exist "%RT%" mkdir "%RT%"

rem --- Python 3.10+ s ssl: ustanovlennyj (py) ili svoj v .runtime\python; puti - cherez $env, ne v tekste komand ---
set "PYEXE="
set "PYARG="
where py >nul 2>nul && py -3 -c "import sys, ssl, json; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PYEXE=py" && set "PYARG=-3"
if defined PYEXE goto have_python
if exist "%RT%\python\python.exe" "%RT%\python\python.exe" -c "import ssl, json" >nul 2>nul && set "PYEXE=%RT%\python\python.exe"
if defined PYEXE goto have_python
if exist "%RT%\python" rmdir /s /q "%RT%\python"
echo Skachivayu Python - odin raz, okolo 10 MB...
%PS% "%NET% $z = Join-Path $env:RT 'python.zip'; Invoke-WebRequest -UseBasicParsing -Uri $env:PYURL -OutFile $z; Expand-Archive -Force $z (Join-Path $env:RT 'python'); Remove-Item $z"
if exist "%RT%\python\python.exe" "%RT%\python\python.exe" -c "import ssl, json" >nul 2>nul && set "PYEXE=%RT%\python\python.exe"
if defined PYEXE goto have_python
if exist "%RT%\python" rmdir /s /q "%RT%\python"
echo Ne udalos skachat Python. Postavte ego s python.org i zapustite etot fajl snova.
pause
exit /b 1
:have_python

rem --- obnovit fajly igry i zapustit igru: git pull dlya kopii iz git, inache - vypusk s GitHub ---
if exist "%PROJ%..\..\.git" goto git_copy
if exist "%PROJ%coach\voicecoach\update.py" goto run_update
if not exist "%PROJ%coach\voicecoach" mkdir "%PROJ%coach\voicecoach"
%PS% "%NET% $f = Join-Path $env:PROJ 'coach\voicecoach\update.py'; $p = $f + '.part'; try { Invoke-WebRequest -UseBasicParsing -Uri ($env:RAW1 + '/coach/voicecoach/update.py') -OutFile $p } catch { Invoke-WebRequest -UseBasicParsing -Uri ($env:RAW2 + '/coach/voicecoach/update.py') -OutFile $p }; Move-Item -Force $p $f"
if exist "%PROJ%coach\voicecoach\update.py" goto run_update
echo Ne udalos skachat fajly igry s GitHub. Proverte internet i zapustite etot fajl snova.
pause
exit /b 1
:run_update
"%PYEXE%" %PYARG% -X utf8 "%PROJ%coach\voicecoach\update.py" "%PROJ%." && "%PYEXE%" %PYARG% -X utf8 "%PROJ%coach\play.py" %* & pause & exit /b
:git_copy
where git >nul 2>nul || echo Net git v PATH - obnovleniya ne budet. Obnovite papku sami, naprimer v GitHub Desktop: Fetch, Pull.
where git >nul 2>nul && git -C "%PROJ%..\.." pull --ff-only --quiet & "%PYEXE%" %PYARG% -X utf8 "%PROJ%coach\play.py" %* & pause & exit /b
