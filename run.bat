@echo off
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
    echo [ERRO] Python nao encontrado.
    pause
    exit /b 1
)

REM Instala dependencias silenciosamente se faltar alguma
%PY% -c "import customtkinter, fitz, PIL" >nul 2>&1 || %PY% -m pip install -r requirements.txt

REM Tenta rodar com pythonw (sem janela de console)
set "PYW="
where pyw >nul 2>&1 && set "PYW=pyw -3"
if not defined PYW where pythonw >nul 2>&1 && set "PYW=pythonw"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"

if defined PYW (
    start "" %PYW% main.py
) else (
    %PY% main.py
)
