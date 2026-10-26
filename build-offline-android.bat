@echo off
setlocal
set "WF_OFFLINE_SOURCE_APK=%~1"
if not defined WF_OFFLINE_SOURCE_APK set "WF_OFFLINE_SOURCE_APK=%USERPROFILE%\Downloads\base.apk.1"
python -X utf8 "%~dp0wf_offline_release.py" build-candidate --source-apk "%WF_OFFLINE_SOURCE_APK%" --snapshot-version 1.4.196
exit /b %ERRORLEVEL%
