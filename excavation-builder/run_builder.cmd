@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PIT_PYTHON=E:\pyt\python.exe"
if not exist "%PIT_PYTHON%" (
  echo ERROR: Python was not found at E:\pyt\python.exe.
  echo Please configure PIT_PYTHON in run_builder.cmd.
  pause
  exit /b 1
)
if not exist "%~dp0builder.py" (
  echo ERROR: builder.py was not found beside this launcher.
  echo Extract the complete ZIP before running this tool.
  pause
  exit /b 1
)
"%PIT_PYTHON%" "%~dp0builder.py" %*
set "PIT_EXIT=%ERRORLEVEL%"
if not "%PIT_EXIT%"=="0" echo ERROR: Builder exited with code %PIT_EXIT%. See the message above.
pause
exit /b %PIT_EXIT%
