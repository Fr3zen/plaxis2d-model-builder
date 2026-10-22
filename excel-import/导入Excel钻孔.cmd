@echo off
chcp 65001 >nul
set "PLUGIN_PYTHON=%~dp0..\pyt\python.exe"
if not exist "%PLUGIN_PYTHON%" set "PLUGIN_PYTHON=E:\pyt\python.exe"
if not exist "%PLUGIN_PYTHON%" (
  echo Python runtime not found. Extract the complete plugin package first.
  pause
  exit /b 1
)
"%PLUGIN_PYTHON%" "%~dp0excel_to_plaxis.py" %*
if errorlevel 1 pause
