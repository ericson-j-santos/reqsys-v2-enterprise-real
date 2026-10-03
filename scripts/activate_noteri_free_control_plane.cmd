@echo off
setlocal EnableExtensions
if /I not "%COMPUTERNAME%"=="Noteri" (
  echo {"ok":false,"error":"host_not_authorized"}
  exit /b 2
)
where python >nul 2>nul || (
  echo {"ok":false,"error":"python_not_found"}
  exit /b 2
)
python "%~dp0activate_noteri_free_control_plane.py" --confirm ACTIVATE-NOTERI-FREE-CONTROL-PLANE --repo-root "%~dp0.."
exit /b %ERRORLEVEL%
