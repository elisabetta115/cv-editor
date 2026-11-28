@echo off
rem CV Editor for Windows: double-click this file to open the editor in your browser.
rem Keep this window open while you use the editor: closing it closes the editor.
title CV Editor
cd /d "%~dp0"

if not exist "src\editor.py" goto :not_unzipped

rem Python 3.11 or newer: "py" comes with Python from python.org, "python" with the Microsoft Store one
set "PYTHON="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON goto :no_python

%PYTHON% src\editor.py %*
rem an error: keep the window open so that it can be read
if errorlevel 1 pause
exit /b

:no_python
echo CV Editor needs Python 3.11 or newer, which is not on this computer yet.
echo.
echo 1. Install it from https://www.python.org/downloads/ (the page opens now).
echo 2. Then double-click this file again.
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:not_unzipped
echo The CV Editor folder is still zipped.
echo.
echo Right-click the downloaded .zip file, choose "Extract All...", then double-click
echo this file in the folder that it makes.
echo.
pause
exit /b 1
