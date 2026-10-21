@echo off
rem Ghi bien ban hop - bam dup de mo.
rem Lan dau: tu cai thu vien Python va tai mo hinh nhan dang giong noi (~1,6 GB).
setlocal
chcp 65001 >nul
title Ghi bien ban hop
cd /d "%~dp0"

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY goto no_python

set "PYEXE="
for /f "usebackq delims=" %%i in (`%PY% -c "import sys; print(sys.executable)"`) do set "PYEXE=%%i"
if not defined PYEXE goto no_python

"%PYEXE%" -c "import faster_whisper, sounddevice, docx" >nul 2>&1
if not errorlevel 1 goto have_libs
echo Lan dau su dung: dang cai cac thu vien can thiet...
"%PYEXE%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 goto fail
:have_libs

"%PYEXE%" "%~dp0scripts\ghi_bien_ban_hop.py" --setup
if errorlevel 1 goto fail

set "PYW=%PYEXE:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PYEXE%"
start "" "%PYW%" "%~dp0scripts\ghi_bien_ban_hop.py"
exit /b 0

:no_python
echo.
echo Chua co Python tren may nay.
choice /c YN /m "Cai Python 3.13 bang winget ngay bay gio"
if errorlevel 2 goto manual
winget install -e --id Python.Python.3.13 --scope user
echo.
echo Cai xong thi dong cua so nay va bam dup lai file "Ghi bien ban hop.bat".
pause
exit /b 0

:manual
echo Tai Python tai https://www.python.org/downloads/
echo Khi cai, nho tick "Add python.exe to PATH". Xong thi chay lai file nay.
pause
exit /b 1

:fail
echo.
echo Co loi khi cai dat (chi tiet o tren). Kiem tra ket noi Internet roi chay lai.
pause
exit /b 1
