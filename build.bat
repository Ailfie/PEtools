@echo off
REM ============================================================
REM  Build PlainPaste.exe  (single-file, no console window)
REM  Requires: Python 3.8+ and PyInstaller
REM      pip install pyinstaller
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/3] Checking PyInstaller ...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo     PyInstaller not found. Installing ...
    python -m pip install --upgrade pyinstaller || goto :fail
)

echo [2/3] Cleaning previous build ...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist plain_paste.spec del /q plain_paste.spec

echo [3/3] Building ...
python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name PlainPaste ^
    --icon plainpaste.ico ^
    --add-data "plainpaste.ico;." ^
    --clean ^
    --noconfirm ^
    plain_paste.py || goto :fail

echo.
echo Done. Output: dist\PlainPaste.exe
goto :eof

:fail
echo.
echo BUILD FAILED. See the messages above.
exit /b 1
