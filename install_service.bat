@echo off
setlocal enabledelayedexpansion

:: ============================================
:: PrintServerLocal - Instalador de Servicio
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
echo   Instalador de PrintServerLocal
echo ========================================
echo.

:: Configuracion
set SERVICE_NAME=PrintServerLocal
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set NSSM_DIR=%SCRIPT_DIR%\nssm
set NSSM_EXE=%NSSM_DIR%\nssm.exe
set LOGS_DIR=%SCRIPT_DIR%\logs
set PYTHON_SCRIPT=%SCRIPT_DIR%\print_server.py

:: Verificar que existe print_server.py
if not exist "%PYTHON_SCRIPT%" (
    echo ERROR: No se encontro print_server.py en %SCRIPT_DIR%
    pause
    exit /b 1
)

:: Buscar Python
set PYTHON_EXE=
for %%p in (python.exe python3.exe) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%i in ('where %%p') do (
            set PYTHON_EXE=%%i
            goto :found_python
        )
    )
)

:found_python
if "%PYTHON_EXE%"=="" (
    echo ERROR: Python no encontrado en el PATH
    echo Instale Python y agregelo al PATH del sistema
    pause
    exit /b 1
)

echo [OK] Python encontrado: %PYTHON_EXE%

:: Crear directorio de logs
if not exist "%LOGS_DIR%" (
    mkdir "%LOGS_DIR%"
    echo [OK] Directorio de logs creado: %LOGS_DIR%
) else (
    echo [OK] Directorio de logs existe: %LOGS_DIR%
)

:: Descargar NSSM si no existe
if not exist "%NSSM_EXE%" (
    echo.
    echo Descargando NSSM...

    if not exist "%NSSM_DIR%" mkdir "%NSSM_DIR%"

    :: Intentar con PowerShell
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $url = 'https://nssm.cc/release/nssm-2.24.zip'; $output = '%TEMP%\nssm.zip'; Invoke-WebRequest -Uri $url -OutFile $output; Expand-Archive -Path $output -DestinationPath '%TEMP%\nssm_extract' -Force; Copy-Item '%TEMP%\nssm_extract\nssm-2.24\win64\nssm.exe' '%NSSM_EXE%' -Force; Remove-Item $output -Force; Remove-Item '%TEMP%\nssm_extract' -Recurse -Force}" 2>nul

    if not exist "%NSSM_EXE%" (
        :: Intentar version 32-bit si 64-bit fallo
        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $url = 'https://nssm.cc/release/nssm-2.24.zip'; $output = '%TEMP%\nssm.zip'; Invoke-WebRequest -Uri $url -OutFile $output; Expand-Archive -Path $output -DestinationPath '%TEMP%\nssm_extract' -Force; Copy-Item '%TEMP%\nssm_extract\nssm-2.24\win32\nssm.exe' '%NSSM_EXE%' -Force; Remove-Item $output -Force; Remove-Item '%TEMP%\nssm_extract' -Recurse -Force}" 2>nul
    )

    if not exist "%NSSM_EXE%" (
        echo.
        echo ERROR: No se pudo descargar NSSM automaticamente.
        echo.
        echo Descargue manualmente desde: https://nssm.cc/release/nssm-2.24.zip
        echo Extraiga nssm.exe (win64 o win32) a: %NSSM_DIR%
        echo.
        pause
        exit /b 1
    )

    echo [OK] NSSM descargado correctamente
) else (
    echo [OK] NSSM ya existe: %NSSM_EXE%
)

:: Verificar si el servicio ya existe
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo El servicio %SERVICE_NAME% ya existe.
    echo Deteniendo y removiendo servicio anterior...

    net stop %SERVICE_NAME% >nul 2>&1
    "%NSSM_EXE%" remove %SERVICE_NAME% confirm >nul 2>&1
    timeout /t 2 >nul
)

:: Instalar el servicio
echo.
echo Instalando servicio %SERVICE_NAME%...

"%NSSM_EXE%" install %SERVICE_NAME% "%PYTHON_EXE%"
if %errorlevel% neq 0 (
    echo ERROR: Fallo al instalar el servicio
    pause
    exit /b 1
)

:: Configurar parametros del servicio
echo Configurando servicio...

:: Script y directorio de trabajo
"%NSSM_EXE%" set %SERVICE_NAME% AppParameters "%PYTHON_SCRIPT%"
"%NSSM_EXE%" set %SERVICE_NAME% AppDirectory "%SCRIPT_DIR%"

:: Descripcion
"%NSSM_EXE%" set %SERVICE_NAME% DisplayName "Print Server Local"
"%NSSM_EXE%" set %SERVICE_NAME% Description "Servidor de impresion local para el sistema ERP AR3"

:: Inicio automatico
"%NSSM_EXE%" set %SERVICE_NAME% Start SERVICE_AUTO_START

:: Configurar logs
"%NSSM_EXE%" set %SERVICE_NAME% AppStdout "%LOGS_DIR%\service.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStderr "%LOGS_DIR%\service_error.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStdoutCreationDisposition 4
"%NSSM_EXE%" set %SERVICE_NAME% AppStderrCreationDisposition 4
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateBytes 1048576

:: Reinicio automatico en fallos (despues de 5 segundos)
"%NSSM_EXE%" set %SERVICE_NAME% AppThrottle 5000
"%NSSM_EXE%" set %SERVICE_NAME% AppExit Default Restart

:: Iniciar el servicio
echo.
echo Iniciando servicio...
net start %SERVICE_NAME%

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   INSTALACION COMPLETADA
    echo ========================================
    echo.
    echo El servicio %SERVICE_NAME% esta corriendo.
    echo.
    echo Verificando conectividad...
    timeout /t 3 >nul

    curl -s http://localhost:3003/printer/status >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Servidor respondiendo en http://localhost:3003
    ) else (
        echo [!] El servidor aun esta iniciando...
        echo     Espere unos segundos y verifique manualmente.
    )

    echo.
    echo Comandos utiles:
    echo   - Ver estado:    sc query %SERVICE_NAME%
    echo   - Detener:       net stop %SERVICE_NAME%
    echo   - Iniciar:       net start %SERVICE_NAME%
    echo   - Desinstalar:   uninstall_service.bat
    echo   - Ver logs:      %LOGS_DIR%
    echo.
) else (
    echo.
    echo ADVERTENCIA: El servicio se instalo pero no pudo iniciar.
    echo Revise los logs en: %LOGS_DIR%
    echo.
)

pause
