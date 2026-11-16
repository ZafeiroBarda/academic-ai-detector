@echo off
REM AI Content Detector — μεταφορά ρυθμίσεων/δεδομένων από παλιό φάκελο (ή git pull)
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title AI Content Detector - update

set "PY="
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

%PY% tools\update.py %*
pause
exit /b

:nopython
echo  Δεν βρέθηκε Python. Python was not found: https://www.python.org/downloads/
pause
exit /b 1
