@echo off
setlocal

:: ============================================
:: PrintServerLocal - Desinstalador de Servicio
:: ============================================

:: Verificar permisos de administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo   ERROR: Se requiere ejecutar como Administrador
    echo ========================================
    echo.
    echo Haga clic derecho en este archivo y seleccione
    echo "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Desinstalador de PrintServerLocal
echo ========================================
echo.

:: Configuracion
set SERVICE_NAME=PrintServerLocal
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set NSSM_EXE=%SCRIPT_DIR%\nssm\nssm.exe

:: Verificar si el servicio existe
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo El servicio %SERVICE_NAME% no esta instalado.
    goto :cleanup_vbs
)

:: Detener el servicio
echo Deteniendo servicio %SERVICE_NAME%...
net stop %SERVICE_NAME% >nul 2>&1
timeout /t 2 >nul

:: Remover el servicio
if exist "%NSSM_EXE%" (
    echo Removiendo servicio con NSSM...
    "%NSSM_EXE%" remove %SERVICE_NAME% confirm
) else (
    echo Removiendo servicio con sc...
    sc delete %SERVICE_NAME%
)

timeout /t 2 >nul

:: Verificar que se removio
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo [OK] Servicio %SERVICE_NAME% removido correctamente.
) else (
    echo [!] El servicio puede requerir reiniciar Windows para removerse completamente.
)

:cleanup_vbs
:: Limpiar VBS del Startup (metodo anterior)
echo.
echo Limpiando acceso directo del Startup (si existe)...

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS_FILE=%STARTUP_FOLDER%\start_print_server.vbs

if exist "%VBS_FILE%" (
    del "%VBS_FILE%" 2>nul
    if not exist "%VBS_FILE%" (
        echo [OK] Archivo VBS del Startup eliminado.
    ) else (
        echo [!] No se pudo eliminar: %VBS_FILE%
    )
) else (
    echo [OK] No habia archivo VBS en Startup.
)

echo.
echo ========================================
echo   DESINSTALACION COMPLETADA
echo ========================================
echo.
echo El servidor de impresion ya no iniciara automaticamente.
echo.
echo Para ejecutar manualmente use:
echo   python print_server.py
echo.
echo O reinstale el servicio con:
echo   install_service.bat
echo.

pause
