@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Print Server USB - Instalador
echo ============================================
echo.

:: Verificar si se ejecuta como administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Se recomienda ejecutar como Administrador
    echo para instalar drivers USB correctamente.
    echo.
    pause
)

:: Obtener directorio del script
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/7] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python no encontrado. Descargando Python 3.11.9...

    :: Descargar Python
    echo Descargando desde python.org...
    curl -L -o python_installer.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

    if not exist python_installer.exe (
        echo [ERROR] No se pudo descargar Python.
        echo Por favor descargue manualmente desde: https://www.python.org/downloads/
        pause
        exit /b 1
    )

    echo Instalando Python silenciosamente...
    python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1

    :: Esperar a que termine la instalacion
    timeout /t 10 /nobreak >nul

    :: Limpiar
    del python_installer.exe

    :: Refrescar PATH
    set "PATH=%PATH%;C:\Program Files\Python311;C:\Program Files\Python311\Scripts"

    echo Python instalado correctamente.
) else (
    for /f "tokens=*" %%i in ('python --version') do echo %%i encontrado.
)

echo.
echo [2/7] Verificando driver USB (Zadig)...
echo.
echo IMPORTANTE: Para que la impresora USB funcione correctamente,
echo es necesario instalar el driver libusb-win32 usando Zadig.
echo.
echo Si aun no ha instalado el driver:
echo   1. Descargue Zadig desde: https://zadig.akeo.ie/
echo   2. Conecte la impresora USB
echo   3. Ejecute Zadig como Administrador
echo   4. Menu Options - List All Devices
echo   5. Seleccione su impresora (ej: EPSON TM-T20)
echo   6. Seleccione driver: libusb-win32 (v1.2.6.0)
echo   7. Click en "Replace Driver"
echo.

choice /C SN /M "Desea descargar Zadig ahora? (S=Si, N=No)"
if %errorlevel% equ 1 (
    echo Descargando Zadig...
    curl -L -o zadig.exe https://github.com/pbatard/libwdi/releases/download/v1.5.0/zadig-2.8.exe
    if exist zadig.exe (
        echo Zadig descargado. Ejecutando...
        start zadig.exe
        echo.
        echo Siga las instrucciones para instalar el driver.
        echo Presione cualquier tecla cuando haya terminado...
        pause >nul
    )
)

echo.
echo [3/7] Creando entorno virtual...
if not exist venv (
    python -m venv venv
    echo Entorno virtual creado.
) else (
    echo Entorno virtual ya existe.
)

echo.
echo [4/7] Activando entorno virtual e instalando dependencias...
call venv\Scripts\activate.bat

:: Actualizar pip
python -m pip install --upgrade pip >nul 2>&1

:: Instalar dependencias
echo Instalando dependencias de requirements.txt...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [ERROR] Error instalando dependencias.
    pause
    exit /b 1
)

echo Dependencias instaladas correctamente.

echo.
echo [5/7] Verificando config.json...
if not exist config.json (
    echo Creando config.json con valores por defecto...
    (
        echo {
        echo   "printer": {
        echo     "vendor_id": "0x04b8",
        echo     "product_id": "0x0e15",
        echo     "name": "EPSON TM-T20"
        echo   },
        echo   "port": 3003
        echo }
    ) > config.json
    echo config.json creado.
) else (
    echo config.json ya existe.
)

echo.
echo [6/7] Configurando auto-arranque...

:: Crear script VBS para auto-arranque silencioso
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_FILE=%STARTUP_FOLDER%\PrintServerUSB.vbs"

:: Crear el archivo VBS
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.CurrentDirectory = "%SCRIPT_DIR%"
    echo WshShell.Run "cmd /c ""%SCRIPT_DIR%venv\Scripts\python.exe"" ""%SCRIPT_DIR%print_server.py""", 0, False
) > "%VBS_FILE%"

if exist "%VBS_FILE%" (
    echo Auto-arranque configurado en:
    echo   %VBS_FILE%
) else (
    echo [ADVERTENCIA] No se pudo crear el archivo de auto-arranque.
)

echo.
echo [7/7] Iniciando servidor...
echo.
echo ============================================
echo   INSTALACION COMPLETADA
echo ============================================
echo.
echo Servidor: http://localhost:3003
echo.
echo Endpoints disponibles:
echo   POST /print/precuenta
echo   POST /print/comanda
echo   POST /print/cierre-caja
echo   POST /print/cierre-diario
echo   POST /print/anulados
echo   POST /print/factura-electronica
echo   POST /print/abrir-cajon
echo   GET  /printer/status
echo   GET  /printer/list
echo   GET  /printer/config
echo   POST /printer/config
echo.
echo Para verificar: curl http://localhost:3003/printer/status
echo Para listar impresoras: curl http://localhost:3003/printer/list
echo.
echo Presione Ctrl+C para detener el servidor.
echo ============================================
echo.

:: Ejecutar servidor
python print_server.py

pause
