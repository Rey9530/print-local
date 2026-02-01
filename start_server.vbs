' start_server.vbs
' Script para iniciar el Print Server USB de forma silenciosa (sin ventana de consola)
' Copiar este archivo a: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
' para que se ejecute automaticamente al iniciar Windows

Option Explicit

Dim WshShell, scriptPath, serverPath, pythonPath

Set WshShell = CreateObject("WScript.Shell")

' Obtener directorio del script
scriptPath = Replace(WScript.ScriptFullName, WScript.ScriptName, "")

' Si el script esta en Startup, buscar en la ubicacion de instalacion
If InStr(LCase(scriptPath), "startup") > 0 Then
    ' Intentar encontrar el servidor en ubicaciones comunes
    Dim possiblePaths, path, fso
    Set fso = CreateObject("Scripting.FileSystemObject")

    possiblePaths = Array( _
        WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\Documents\GitHub\print-local\", _
        WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\print-local\", _
        "C:\print-local\", _
        WshShell.ExpandEnvironmentStrings("%ProgramFiles%") & "\print-local\" _
    )

    For Each path In possiblePaths
        If fso.FileExists(path & "print_server.py") Then
            scriptPath = path
            Exit For
        End If
    Next
End If

' Rutas del servidor
serverPath = scriptPath & "print_server.py"
pythonPath = scriptPath & "venv\Scripts\python.exe"

' Verificar si existe el entorno virtual
Dim fso2
Set fso2 = CreateObject("Scripting.FileSystemObject")

If Not fso2.FileExists(pythonPath) Then
    ' Usar Python del sistema si no hay venv
    pythonPath = "python"
End If

' Cambiar al directorio del servidor
WshShell.CurrentDirectory = scriptPath

' Ejecutar el servidor de forma oculta (0 = hidden)
WshShell.Run """" & pythonPath & """ """ & serverPath & """", 0, False

Set WshShell = Nothing
