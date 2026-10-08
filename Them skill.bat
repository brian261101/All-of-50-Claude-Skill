@echo off
chcp 65001 >nul
title Them skill len GitHub
cd /d "%~dp0"
if "%~1"=="" (
  echo.
  echo   Keo tha THU MUC skill vao file nay de day len GitHub.
  echo.
  echo   Hoac chay:  python add-skill.py "duong\dan\den\skill"
  echo.
  pause
  exit /b
)
python add-skill.py %*
pause
