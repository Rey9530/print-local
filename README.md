# Print Server Local (Python)

Servidor de impresion termica en Python que utiliza Windows Print Spooler (win32print) para maxima compatibilidad con impresoras termicas ESC/POS.

## Caracteristicas

- Usa Windows Print Spooler nativo (win32print)
- No requiere drivers especiales (Zadig)
- Compatible con impresoras termicas ESC/POS
- Puerto 3003
- Zona horaria: El Salvador (UTC-6)

## Archivos del Proyecto

| Archivo | Descripcion |
|---------|-------------|
| `print_server.py` | Servidor Flask principal |
| `requirements.txt` | Dependencias Python |
| `config.json` | Configuracion de impresora |
| `install_and_run.bat` | Instalador automatico Windows |
| `start_server.vbs` | Auto-arranque silencioso |

## Instalacion

### Opcion A: Instalador Automatico (Recomendado)

```bash
install_and_run.bat
```

Este script:
1. Crea un entorno virtual Python
2. Instala todas las dependencias
3. Inicia el servidor

### Opcion B: Instalacion Manual

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python print_server.py
```

## Configuracion

Editar `config.json`:

```json
{
  "printer": {
    "name": "Nombre de impresora Windows"
  },
  "port": 3003
}
```

Para ver las impresoras disponibles, usar el endpoint `GET /printer/list`.

## API Endpoints

### Endpoints de Impresion

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | `/print/precuenta` | Pre-cuenta de restaurante |
| POST | `/print/comanda` | Comanda de cocina |
| POST | `/print/cierre-caja` | Cierre de caja |
| POST | `/print/cierre-diario` | Cierre diario |
| POST | `/print/anulados` | Reporte de anulaciones |
| POST | `/print/factura-electronica` | Factura electronica DTE |
| POST | `/print/abrir-cajon` | Abrir cajon de dinero |
| POST | `/printer/test` | Pagina de prueba |

### Endpoints de Configuracion

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/printer/status` | Estado de impresora |
| GET | `/printer/list` | Lista impresoras Windows |
| GET | `/printer/config` | Ver configuracion actual |
| POST | `/printer/config` | Actualizar configuracion |

## Ejemplos de Uso

### Imprimir Pre-cuenta

```bash
curl -X POST http://localhost:3003/print/precuenta \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "lugar_origen": "Restaurante",
      "nombre_comercial": "Mi Restaurante",
      "Mesa": { "numero": "5" },
      "Usuarios": { "nombres": "Juan", "apellidos": "Perez" },
      "OrdenesDeRestauranteDetalle": [],
      "subtotal": 25.50,
      "propina": 2.55,
      "total": 28.05
    }
  }'
```

### Ver Impresoras Disponibles

```bash
curl http://localhost:3003/printer/list
```

### Cambiar Impresora

```bash
curl -X POST http://localhost:3003/printer/config \
  -H "Content-Type: application/json" \
  -d '{"printer": {"name": "EPSON TM-T20III"}}'
```

### Pagina de Prueba

```bash
curl -X POST http://localhost:3003/printer/test
```

### Abrir Cajon de Dinero

```bash
curl -X POST http://localhost:3003/print/abrir-cajon
```

## Dependencias Python

```
flask==3.0.0
flask-cors==4.0.0
python-escpos==3.1
pyusb==1.2.1
pytz==2024.1
libusb-package==1.0.26.2
pywin32==306
```

## Arquitectura

### Clases Principales

#### ESCPOSCommands
Comandos ESC/POS en bytes para impresoras termicas:
- `INIT` - Inicializar impresora
- `CUT` - Cortar papel
- `OPEN_DRAWER` - Abrir cajon
- `ALIGN_CENTER`, `ALIGN_LEFT`, `ALIGN_RIGHT` - Alineacion
- `BOLD_ON`, `BOLD_OFF` - Texto en negrita
- `DOUBLE_HEIGHT_ON`, `DOUBLE_HEIGHT_OFF` - Texto doble altura

#### ThermalPrinter
Clase para manejar impresion via Windows Print Spooler:
- Envia comandos RAW directamente a la impresora
- No requiere drivers especiales
- Compatible con cualquier impresora termica instalada en Windows

#### ImpresionesService
Servicio principal con metodos de impresion:
- `imprimir_precuenta()`
- `imprimir_comanda()`
- `imprimir_cierre_caja()`
- `imprimir_cierre_diario()`
- `imprimir_anulados()`
- `imprimir_factura_electronica()`
- `abrir_cajon()`
- `imprimir_test()`

## Notas Tecnicas

- **Windows Print Spooler**: Usa `win32print` para enviar comandos RAW
- **Sin drivers especiales**: No requiere Zadig ni drivers USB adicionales
- **Zona horaria**: El Salvador (UTC-6) via `pytz`
- **Manejo de tipos**: Funcion `to_number()` para conversion segura
- **CORS habilitado**: Acepta peticiones desde cualquier origen
- **Puerto**: 3003 (configurable en config.json)

## Auto-arranque con Windows

Para iniciar el servidor automaticamente al encender Windows:

1. Crear acceso directo de `start_server.vbs`
2. Presionar `Win + R`, escribir `shell:startup`
3. Copiar el acceso directo a esa carpeta

El servidor se iniciara silenciosamente en segundo plano.

## Solucion de Problemas

### La impresora no aparece en la lista
- Verificar que la impresora este instalada en Windows
- Ir a Configuracion > Dispositivos > Impresoras y escáneres

### Error de permisos
- Ejecutar como administrador
- Verificar que el usuario tenga acceso a la impresora

### El cajon no abre
- Verificar conexion del cajon a la impresora (puerto RJ11)
- Probar con `POST /printer/test` primero

## Licencia

ISC License
