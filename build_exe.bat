@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---- Localiza o Python ------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
    echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/windows/
    pause
    exit /b 1
)
echo Python: %PY%

REM ---- Dependencias -----------------------------------------------------
echo === Instalando dependencias ===
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :fail

REM ---- Limpa build anterior --------------------------------------------
echo === Limpando builds anteriores ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM ---- PyInstaller ------------------------------------------------------
echo === Empacotando com PyInstaller ===
%PY% -m PyInstaller build.spec --noconfirm
if errorlevel 1 goto :fail

REM ---- Copia vendor/ImageMagick para dentro do build -------------------
set "DIST_DIR=dist\Processador de DTFs"
if exist "vendor\ImageMagick\magick.exe" (
    echo === Copiando ImageMagick portable para o build ===
    if not exist "%DIST_DIR%\vendor\ImageMagick" mkdir "%DIST_DIR%\vendor\ImageMagick"
    xcopy /E /I /Y "vendor\ImageMagick" "%DIST_DIR%\vendor\ImageMagick" >nul
) else (
    echo [AVISO] vendor\ImageMagick\magick.exe nao encontrado.
    echo         O EXE vai precisar que o cliente tenha ImageMagick instalado.
    echo         Baixe o portable e extraia em vendor\ImageMagick\ antes de distribuir.
)

REM ---- Inno Setup (instalador profissional) ----------------------------
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if defined ISCC (
    echo === Gerando instalador com Inno Setup ===
    "%ISCC%" installer.iss
    if errorlevel 1 goto :fail
    echo.
    echo === OK ===
    echo Pasta portatil:    "%DIST_DIR%"
    echo Instalador final:  "installer_output\Setup_Tecnosup_DTF_1.0.0.exe"
) else (
    echo [AVISO] Inno Setup 6 nao encontrado.
    echo         Baixe em https://jrsoftware.org/isdl.php e instale.
    echo         Depois rode novamente este script para gerar o instalador.
    echo.
    echo === OK (sem instalador) ===
    echo Pasta portatil: "%DIST_DIR%"
)
pause
exit /b 0

:fail
echo.
echo === FALHOU ===
pause
exit /b 1
