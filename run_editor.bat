@echo off
setlocal
set "HERE=%~dp0"
py -3 "%HERE%tdg_editor.py" %*
if errorlevel 1 python "%HERE%tdg_editor.py" %*
endlocal
