@echo off
setlocal
cd /d "%~dp0"
if /I not "%SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM%"=="YES" (
  echo REFUSED: set SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM=YES explicitly.
  echo Also set SCOREMAX_DB to the intended disposable/pilot database.
  exit /b 2
)
if "%SCOREMAX_DB%"=="" (
  echo REFUSED: SCOREMAX_DB must point to the intended disposable/pilot database.
  exit /b 2
)
where py >nul 2>nul
if %errorlevel%==0 (
  py provision_qa_synthetic_learners_v6_5_11.py
) else (
  python provision_qa_synthetic_learners_v6_5_11.py
)
exit /b %errorlevel%
