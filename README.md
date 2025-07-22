# Print Server Local

Un servidor de impresión local para impresoras térmicas que permite gestionar impresiones de tickets, comandas, reportes y facturas electrónicas para sistemas de punto de venta (POS).

## 📋 Características

- **Gestión de Impresoras Térmicas**: Soporte para impresoras EPSON a través de TCP/IP
- **Múltiples Tipos de Impresión**:
  - Pre-cuentas de restaurante
  - Comandas de cocina
  - Cierres de caja
  - Cierres diarios
  - Reportes de anulaciones
  - Facturas electrónicas
- **Apertura de Cajón**: Control remoto del cajón de dinero
- **Verificación de Estado**: Monitoreo del estado de conectividad de las impresoras
- **Zona Horaria**: Configurado para El Salvador (UTC-6)
- **Cache de Conexiones**: Reutilización de conexiones para mejor rendimiento

## 🚀 Instalación

1. **Clonar el repositorio**:
```bash
git clone <url-del-repositorio>
cd print-local
```

2. **Instalar dependencias**:
```bash
npm install
```

3. **Ejecutar el servidor**:
```bash
node print-server.js
```

El servidor se ejecutará en `http://localhost:3003`

## 📦 Dependencias

- **express**: Framework web para Node.js
- **cors**: Middleware para habilitar CORS
- **node-thermal-printer**: Librería para control de impresoras térmicas

## 🔧 Configuración

### Configuración de Impresora

- **Tipo**: EPSON
- **Conexión**: TCP/IP
- **Puerto por defecto**: 9100
- **Timeout**: 5000ms
- **Codificación**: UTF-8
- **Reintentos**: 4 intentos con delay de 1000ms

## 📡 API Endpoints

### Impresión de Documentos

#### POST `/print/precuenta`
Imprime una pre-cuenta de restaurante.
```json
{
  "data": {
    "lugar_origen": "Restaurante",
    "nombre_comercial": "Nombre del Restaurante",
    "direccion": "Dirección",
    "Usuarios": {
      "nombres": "Juan",
      "apellidos": "Pérez"
    },
    "numero_personas": 4,
    "Mesa": {
      "numero": "5"
    },
    "OrdenesDeRestauranteDetalle": [...],
    "subtotal": 25.50,
    "propina": 2.55,
    "total": 28.05,
    "estado": "Pendiente"
  },
  "printerIp": "192.168.1.100"
}
```

#### POST `/print/comanda`
Imprime una comanda para la cocina.
```json
{
  "data": {
    "lugar_origen": "Restaurante",
    "numero_orden": "001",
    "Mesa": {
      "numero": "5"
    },
    "Usuarios": {
      "nombres": "Juan",
      "apellidos": "Pérez"
    },
    "detalleItems": [
      {
        "cantidad": 2,
        "nombre": "Hamburguesa",
        "comentario": "Sin cebolla",
        "fecha_creacion": "2025-01-20T10:30:00Z"
      }
    ]
  },
  "printerIp": "192.168.1.101"
}
```

#### POST `/print/cierre-caja`
Imprime el reporte de cierre de caja.
```json
{
  "data": {
    "nombre_sistema": "Sistema POS",
    "direccion": "Dirección del negocio",
    "Usuarios": {
      "nombres": "Juan",
      "apellidos": "Pérez"
    },
    "fecha_cierre": "20-01-2025 18:00",
    "monto_inicial": 100.00,
    "efectivoReal": 250.00,
    "totalCompras": 50.00,
    "efectivoTotal": 300.00
  },
  "con_detalle": 1,
  "printerIp": "192.168.1.100"
}
```

#### POST `/print/cierre-diario`
Imprime el reporte de cierre diario.
```json
{
  "data": {
    "data": {
      "fecha": "2025-01-20T18:00:00Z",
      "Usuarios": {
        "nombres": "Juan",
        "apellidos": "Pérez"
      },
      "ventaBruta": 1500.00,
      "ventaSinPropina": 1350.00,
      "ventaSinIva": 1200.00,
      "efectivo": 800.00,
      "propina": 150.00
    },
    "printerIp": "192.168.1.100"
  }
}
```

#### POST `/print/anulados`
Imprime el reporte de items anulados.
```json
{
  "data": {
    "lugar_origen": "Restaurante",
    "nombre_comercial": "Nombre del Restaurante",
    "Usuarios": {
      "nombres": "Juan",
      "apellidos": "Pérez"
    },
    "OrdenesDetalleEliminados": [...]
  },
  "printerIp": "192.168.1.100"
}
```

#### POST `/print/factura-electronica`
Imprime una factura electrónica.
```json
{
  "data": {
    // Datos de la factura electrónica
  },
  "printerIp": "192.168.1.100"
}
```

### Control de Hardware

#### POST `/print/abrir-cajon`
Abre el cajón de dinero conectado a la impresora.
```json
{
  "printerIp": "192.168.1.100"
}
```

### Monitoreo

#### GET `/printer/status/:ip`
Verifica el estado de conectividad de una impresora.

**Parámetros**:
- `ip`: Dirección IP de la impresora

**Respuesta**:
```json
{
  "success": true,
  "connected": true,
  "ip": "192.168.1.100"
}
```

## 🛠️ Funcionalidades Técnicas

### Gestión de Conexiones
- **Cache de conexiones**: Las conexiones a impresoras se almacenan en cache para reutilización
- **Reintentos automáticos**: 4 intentos de conexión con delay progresivo
- **Timeout configurable**: 5 segundos por defecto

### Formato de Fechas
- **Zona horaria**: América/El_Salvador (UTC-6)
- **Formato**: DD-MM-YYYY HH:mm AM/PM

### Formato de Moneda
- **Decimales**: 2 decimales fijos
- **Símbolo**: Dólar estadounidense ($)

## 🔧 Desarrollo

### Estructura del Proyecto
```
print-local/
├── package.json          # Configuración del proyecto
├── print-server.js       # Servidor principal
└── README.md             # Documentación
```

### Scripts Disponibles
```bash
npm test                   # Ejecuta los tests (no implementado)
node print-server.js       # Inicia el servidor
```

## 📝 Notas Técnicas

- El servidor utiliza el puerto **3003** por defecto
- Todas las impresoras deben ser compatibles con el protocolo **EPSON**
- La conexión se realiza por **TCP/IP** en el puerto **9100**
- El servidor incluye **CORS** habilitado para todas las solicitudes
- Las fechas se manejan en la zona horaria de **El Salvador**

## 🤝 Contribución

Para contribuir al proyecto:

1. Fork del repositorio
2. Crear una rama para la nueva funcionalidad
3. Realizar los cambios necesarios
4. Ejecutar las pruebas
5. Crear un Pull Request

## 📄 Licencia

ISC License

## 🆘 Soporte

Para reportar problemas o solicitar nuevas funcionalidades, crear un issue en el repositorio del proyecto.