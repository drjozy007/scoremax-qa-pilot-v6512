@echo off
setlocal
cd /d "%~dp0"
if /I not "%SCOREMAX_QA_SYNTHETIC_STAGE_CONFIRM%"=="YES" (
  echo REFUSED: set SCOREMAX_QA_SYNTHETIC_STAGE_CONFIRM=YES explicitly.
  echo Also set SCOREMAX_DB to the intended disposable/pilot database.
  exit /b 2
)
if "%SCOREMAX_DB%"=="" (
  echo REFUSED: SCOREMAX_DB must point to the intended disposable/pilot database.
  exit /b 2
)
where py >nul 2>nul
if %errorlevel%==0 (
  py stage_qa_synthetic_pilot_fixture_v6_5_11.py
) else (
  python stage_qa_synthetic_pilot_fixture_v6_5_11.py
)
exit /b %errorlevel%
