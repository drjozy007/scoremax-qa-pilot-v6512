@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py tests\test_v6_5_11_synthetic_learner_contract.py
) else (
  python tests\test_v6_5_11_synthetic_learner_contract.py
)
exit /b %errorlevel%
