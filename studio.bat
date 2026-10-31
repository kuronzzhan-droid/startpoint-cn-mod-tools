@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
python -m wf.studio.frontend_build
if errorlevel 2 exit /b 1
if not errorlevel 1 goto launch
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required to build the studio frontend.
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm is required to build the studio frontend.
  exit /b 1
)
pushd studio
if exist node_modules goto build
call npm ci
if errorlevel 1 goto build_failed
:build
call npm run build
if errorlevel 1 goto build_failed
popd
:launch
python -m wf.studio %*
exit /b %errorlevel%
:build_failed
popd
exit /b 1
