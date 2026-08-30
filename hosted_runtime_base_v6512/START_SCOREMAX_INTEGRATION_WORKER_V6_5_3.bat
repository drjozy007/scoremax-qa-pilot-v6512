@echo off
setlocal
cd /d "%~dp0"
python scoremax_integration_dispatch_v1.py --worker --evidence --strict-preflight --limit 100
pause
