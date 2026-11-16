@echo off
REM AI Content Detector — εκκίνηση με διπλό κλικ (Windows)
REM Η κύρια λογική είναι στο launcher.py· εδώ μόνο βρίσκουμε Python και venv.
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
title AI Content Detector

echo.
echo  AI Content Detector
echo  ================================
echo.

if exist "venv\Scripts\python.exe" goto run

REM Python: προτιμάμε τον εκκινητή py των Windows, μετά το python
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto oldpython

echo  Προετοιμασία - μόνο την πρώτη φορά...
%PY% -m venv venv
if errorlevel 1 goto venvfail

:run
"venv\Scripts\python.exe" launcher.py %*
if errorlevel 1 pause
exit /b

:nopython
echo  Δεν βρέθηκε Python. Εγκατάστησέ την από τη σελίδα που ανοίγει
echo  και τσέκαρε "Add python.exe to PATH" στην εγκατάσταση.
echo  Python was not found. Install it from the page that opens.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:oldpython
echo  Χρειάζεται Python 3.10 ή νεότερη. Python 3.10+ is required.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:venvfail
echo  Δεν ήταν δυνατή η δημιουργία του περιβάλλοντος venv.
echo  Could not create the virtual environment.
pause
exit /b 1
