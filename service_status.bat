@echo off
setlocal enabledelayedexpansion

:: ============================================
:: PrintServerLocal - Estado del Servicio
:: ============================================

echo.
echo ========================================
echo   Estado de PrintServerLocal
echo ========================================
echo.

set SERVICE_NAME=PrintServerLocal
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set LOGS_DIR=%SCRIPT_DIR%\logs

:: Estado del servicio
echo [Servicio Windows]
sc query %SERVICE_NAME% 2>nul | findstr /i "STATE" >nul
if %errorlevel% equ 0 (
    for /f "tokens=4" %%a in ('sc query %SERVICE_NAME% ^| findstr "STATE"') do (
        set STATE=%%a
    )

    if "!STATE!"=="RUNNING" (
        echo   Estado: EJECUTANDOSE
    ) else if "!STATE!"=="STOPPED" (
        echo   Estado: DETENIDO
    ) else (
        echo   Estado: !STATE!
    )

    for /f "tokens=3" %%a in ('sc qc %SERVICE_NAME% ^| findstr "START_TYPE"') do (
        set START_TYPE=%%a
    )
    echo   Inicio: !START_TYPE!
) else (
    echo   Estado: NO INSTALADO
    echo.
    echo   Para instalar ejecute: install_service.bat
    echo.
    goto :check_manual
)

:: Conectividad
echo.
echo [Conectividad]
curl -s -o nul -w "%%{http_code}" http://localhost:3003/printer/status >%TEMP%\curl_result.txt 2>nul
set /p HTTP_CODE=<%TEMP%\curl_result.txt
del %TEMP%\curl_result.txt 2>nul

if "%HTTP_CODE%"=="200" (
    echo   Puerto 3003: RESPONDIENDO

    :: Obtener info de impresoras
    curl -s http://localhost:3003/printer/status 2>nul | findstr /i "default" >nul
    if !errorlevel! equ 0 (
        echo   API Status: OK
    )
) else (
    echo   Puerto 3003: SIN RESPUESTA
    echo   (El servicio puede estar iniciando o hay un error)
)

:: Ultimos logs
echo.
echo [Ultimos Logs]
if exist "%LOGS_DIR%\service.log" (
    echo   service.log (ultimas 5 lineas):
    powershell -Command "Get-Content '%LOGS_DIR%\service.log' -Tail 5 | ForEach-Object { Write-Host ('     ' + $_) }"
) else (
    echo   No hay logs disponibles.
)

if exist "%LOGS_DIR%\service_error.log" (
    for %%A in ("%LOGS_DIR%\service_error.log") do set ERROR_SIZE=%%~zA
    if !ERROR_SIZE! gtr 0 (
        echo.
        echo   service_error.log (ultimas 5 lineas):
        powershell -Command "Get-Content '%LOGS_DIR%\service_error.log' -Tail 5 | ForEach-Object { Write-Host ('     ' + $_) }"
    )
)

goto :end

:check_manual
:: Verificar si esta corriendo manualmente
echo [Proceso Manual]
tasklist /fi "imagename eq python.exe" 2>nul | findstr /i "python" >nul
if %errorlevel% equ 0 (
    echo   Python esta ejecutandose (posiblemente el servidor)

    curl -s -o nul http://localhost:3003/printer/status 2>nul
    if !errorlevel! equ 0 (
        echo   El servidor responde en puerto 3003
    )
) else (
    echo   No hay proceso Python ejecutandose
)

:end
echo.
echo ========================================
echo   Comandos Utiles
echo ========================================
echo.
echo   Iniciar servicio:     net start %SERVICE_NAME%
echo   Detener servicio:     net stop %SERVICE_NAME%
echo   Reinstalar:           install_service.bat
echo   Desinstalar:          uninstall_service.bat
echo   Ver logs completos:   notepad "%LOGS_DIR%\service.log"
echo.

pause
