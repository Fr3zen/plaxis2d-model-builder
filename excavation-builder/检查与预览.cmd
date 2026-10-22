@echo off
call "%~dp0run_builder.cmd" --validate-only %*
exit /b %errorlevel%
