# print_server.py
# Servidor de impresion termica para Windows
# Usa win32print para compatibilidad con Windows

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import pytz
import sys

# Importar win32print para Windows
try:
    import win32print
    import win32ui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[WARN] win32print no disponible. Instale: pip install pywin32")

app = Flask(__name__)
CORS(app)

# Cargar configuracion
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def load_config():
    """Carga la configuracion desde config.json"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        default_config = {
            "printer": {
                "name": "",
                "vendor_id": "0x04b8",
                "product_id": "0x0e15"
            },
            "port": 3003
        }
        save_config(default_config)
        return default_config


def save_config(config):
    """Guarda la configuracion en config.json"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


config = load_config()


class ESCPOSCommands:
    """Comandos ESC/POS para impresoras termicas"""

    # Inicializacion
    INIT = b'\x1b\x40'

    # Alineacion
    ALIGN_LEFT = b'\x1b\x61\x00'
    ALIGN_CENTER = b'\x1b\x61\x01'
    ALIGN_RIGHT = b'\x1b\x61\x02'

    # Texto
    BOLD_ON = b'\x1b\x45\x01'
    BOLD_OFF = b'\x1b\x45\x00'
    UNDERLINE_ON = b'\x1b\x2d\x01'
    UNDERLINE_OFF = b'\x1b\x2d\x00'

    # Tamano de texto
    NORMAL_SIZE = b'\x1d\x21\x00'
    DOUBLE_HEIGHT = b'\x1d\x21\x01'
    DOUBLE_WIDTH = b'\x1d\x21\x10'
    DOUBLE_SIZE = b'\x1d\x21\x11'

    # Corte de papel
    CUT_FULL = b'\x1d\x56\x00'
    CUT_PARTIAL = b'\x1d\x56\x01'

    # Cajon de dinero
    CASH_DRAWER = b'\x1b\x70\x00\x19\xfa'

    # Beep
    BEEP = b'\x1b\x42\x03\x03'

    # Salto de linea
    LF = b'\x0a'


class ThermalPrinter:
    """Clase para manejar impresora termica via Windows Print Spooler"""

    def __init__(self, printer_name=None):
        self.printer_name = printer_name
        self.buffer = bytearray()
        self.width = 48  # Caracteres por linea (80mm)
        self.encoding = 'cp437'  # Codificacion para caracteres especiales

        # Inicializar impresora
        self.buffer.extend(ESCPOSCommands.INIT)

    def _text_to_bytes(self, text):
        """Convierte texto a bytes con manejo de caracteres especiales"""
        # Reemplazar caracteres especiales
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
            'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U',
            '¿': '?', '¡': '!'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        try:
            return text.encode(self.encoding)
        except:
            return text.encode('ascii', errors='replace')

    def text(self, content):
        """Agrega texto al buffer"""
        self.buffer.extend(self._text_to_bytes(content))

    def println(self, content=''):
        """Agrega texto con salto de linea"""
        self.text(content + '\n')

    def set(self, align=None, bold=None, width=1, height=1):
        """Configura formato de texto"""
        if align == 'left':
            self.buffer.extend(ESCPOSCommands.ALIGN_LEFT)
        elif align == 'center':
            self.buffer.extend(ESCPOSCommands.ALIGN_CENTER)
        elif align == 'right':
            self.buffer.extend(ESCPOSCommands.ALIGN_RIGHT)

        if bold is True:
            self.buffer.extend(ESCPOSCommands.BOLD_ON)
        elif bold is False:
            self.buffer.extend(ESCPOSCommands.BOLD_OFF)

        # Tamano de texto
        if width == 2 and height == 2:
            self.buffer.extend(ESCPOSCommands.DOUBLE_SIZE)
        elif width == 2:
            self.buffer.extend(ESCPOSCommands.DOUBLE_WIDTH)
        elif height == 2:
            self.buffer.extend(ESCPOSCommands.DOUBLE_HEIGHT)
        else:
            self.buffer.extend(ESCPOSCommands.NORMAL_SIZE)

    def cut(self):
        """Corta el papel"""
        self.buffer.extend(ESCPOSCommands.LF)
        self.buffer.extend(ESCPOSCommands.LF)
        self.buffer.extend(ESCPOSCommands.LF)
        self.buffer.extend(ESCPOSCommands.CUT_PARTIAL)

    def cashdraw(self):
        """Abre el cajon de dinero"""
        self.buffer.extend(ESCPOSCommands.CASH_DRAWER)

    def buzzer(self, times=1, duration=1):
        """Emite beep"""
        self.buffer.extend(ESCPOSCommands.BEEP)

    def qr(self, content, size=6):
        """Genera codigo QR"""
        # Comando QR para EPSON
        # Modelo QR
        self.buffer.extend(b'\x1d\x28\x6b\x04\x00\x31\x41\x32\x00')
        # Tamano
        self.buffer.extend(b'\x1d\x28\x6b\x03\x00\x31\x43' + bytes([size]))
        # Error correction
        self.buffer.extend(b'\x1d\x28\x6b\x03\x00\x31\x45\x31')
        # Datos
        data = content.encode('utf-8')
        length = len(data) + 3
        self.buffer.extend(b'\x1d\x28\x6b' + bytes([length % 256, length // 256]) + b'\x31\x50\x30' + data)
        # Imprimir QR
        self.buffer.extend(b'\x1d\x28\x6b\x03\x00\x31\x51\x30')

    def print_raw(self):
        """Envia los datos a la impresora usando win32print"""
        if not WIN32_AVAILABLE:
            raise Exception("win32print no disponible")

        printer_name = self.printer_name
        if not printer_name:
            printer_name = win32print.GetDefaultPrinter()

        if not printer_name:
            raise Exception("No hay impresora configurada")

        try:
            # Abrir impresora
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                # Iniciar documento
                job = win32print.StartDocPrinter(hprinter, 1, ("ESC/POS Print", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hprinter)
                    win32print.WritePrinter(hprinter, bytes(self.buffer))
                    win32print.EndPagePrinter(hprinter)
                finally:
                    win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)

            return True
        except Exception as e:
            raise Exception(f"Error imprimiendo: {str(e)}")

    def clear(self):
        """Limpia el buffer"""
        self.buffer = bytearray()
        self.buffer.extend(ESCPOSCommands.INIT)


class ImpresionesService:
    """Servicio de impresion termica"""

    def __init__(self):
        self.printer_width = 48

    def get_printer_name(self):
        """Obtiene el nombre de la impresora configurada"""
        name = config.get('printer', {}).get('name', '')
        if not name and WIN32_AVAILABLE:
            name = win32print.GetDefaultPrinter()
        return name

    def create_printer(self):
        """Crea instancia de impresora"""
        printer_name = self.get_printer_name()
        return ThermalPrinter(printer_name)

    def to_number(self, value, default=0):
        """Convierte un valor a numero de forma segura"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        return default

    def format_currency(self, amount):
        """Formatea cantidad a formato moneda"""
        amount = self.to_number(amount)
        if amount == 0:
            return '0.00'
        return f"{amount:.2f}"

    def convert_with_time(self, date_str):
        """Convierte fecha a zona horaria de El Salvador"""
        try:
            if isinstance(date_str, str):
                for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                    try:
                        utc_date = datetime.strptime(date_str.split(' GMT')[0].split('+')[0], fmt)
                        break
                    except:
                        continue
                else:
                    utc_date = datetime.now()
            else:
                utc_date = datetime.now()

            utc_zone = pytz.UTC
            sv_zone = pytz.timezone('America/El_Salvador')
            utc_date = utc_zone.localize(utc_date)
            sv_date = utc_date.astimezone(sv_zone)
            return sv_date.strftime('%d-%m-%Y %H:%M')
        except:
            return datetime.now().strftime('%d-%m-%Y %H:%M')

    def draw_line(self, printer):
        """Imprime linea completa"""
        printer.println('-' * self.printer_width)

    def print_single_line(self, printer):
        """Imprime linea divisora"""
        printer.println('-' * (self.printer_width // 2))

    def left_right(self, printer, left_text, right_text):
        """Imprime texto alineado a izquierda y derecha"""
        spaces = self.printer_width - len(left_text) - len(right_text)
        if spaces < 1:
            spaces = 1
        printer.println(left_text + ' ' * spaces + right_text)

    def table_custom(self, printer, columns):
        """Imprime tabla personalizada"""
        line = ""
        for col in columns:
            width = int(self.printer_width * col.get('width', 0.25))
            text = str(col.get('text', ''))[:width]
            align = col.get('align', 'LEFT')

            if align == 'CENTER':
                text = text.center(width)
            elif align == 'RIGHT':
                text = text.rjust(width)
            else:
                text = text.ljust(width)
            line += text
        printer.println(line)

    def aperturar_cajon(self):
        """Abre el cajon de dinero"""
        try:
            printer = self.create_printer()
            printer.cashdraw()
            printer.print_raw()
            return {'success': True, 'message': 'Cajon abierto'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def print_precuenta(self, data):
        """Imprime pre-cuenta/ticket"""
        try:
            printer = self.create_printer()

            def validate_data(item):
                return {
                    'cantidad': str(item.get('cantidad', '0')),
                    'nombre': str(item.get('nombre', '')),
                    'precio_unitario': item.get('precio_unitario', 0),
                    'precio_total': item.get('precio_total', 0)
                }

            # Header
            printer.set(align='center')
            printer.set(bold=True, width=2, height=2)
            printer.println(data.get('nombre_comercial', '') or '')
            printer.set(bold=False, width=1, height=1)

            printer.println(data.get('direccion', '') or '')
            self.draw_line(printer)

            printer.set(align='left')
            usuarios = data.get('Usuarios', {}) or {}
            printer.println(f"Emp.{usuarios.get('nombres', '')} {usuarios.get('apellidos', '')}")

            left_text = f"Clientes {data.get('numero_personas', '')}"
            right_text = ''
            mesa = data.get('Mesa')
            if mesa is not None:
                right_text = f"Mesa {mesa.get('numero', '')}"
            self.left_right(printer, left_text, right_text)

            printer.println('')
            self.draw_line(printer)
            printer.set(bold=True)
            self.table_custom(printer, [
                {'text': 'Cant.', 'width': 0.15, 'align': 'CENTER'},
                {'text': 'Descripcion', 'width': 0.40, 'align': 'LEFT'},
                {'text': 'Precio', 'width': 0.2, 'align': 'RIGHT'},
                {'text': 'Total', 'width': 0.2, 'align': 'RIGHT'}
            ])
            printer.set(bold=False)

            for item in data.get('OrdenesDeRestauranteDetalle', []) or []:
                validated = validate_data(item)
                self.table_custom(printer, [
                    {'text': validated['cantidad'], 'width': 0.1, 'align': 'CENTER'},
                    {'text': validated['nombre'], 'width': 0.50, 'align': 'LEFT'},
                    {'text': self.format_currency(validated['precio_unitario']), 'width': 0.2, 'align': 'RIGHT'},
                    {'text': self.format_currency(validated['precio_total']), 'width': 0.2, 'align': 'RIGHT'}
                ])

            self.draw_line(printer)
            printer.set(align='right')

            descuentos = ''
            if data.get('Descuento'):
                descuento = data['Descuento']
                descuentos = f"Descuento $-{data.get('monto_descuento', 0)} ({descuento.get('porcentaje', 0)}%)"

            self.left_right(printer, 'Subtotal:', f"{descuentos}   ${data.get('subtotal', 0)}")
            self.left_right(printer, 'Propina (10%):', f"${data.get('propina', 0)}")

            printer.set(width=2, height=2)
            total_text = "Total:"
            total_amount = f"${self.format_currency(data.get('total', 0))}"
            espacios_totales = self.printer_width // 2
            espacios_usados = len(total_text) + len(total_amount)
            spaces = " " * max(1, espacios_totales - espacios_usados)
            printer.println(total_text + spaces + total_amount)
            printer.set(width=1, height=1)

            self.left_right(printer, 'ESTADO:', data.get('estado', ''))
            self.draw_line(printer)

            metodo_pago = ''
            for item in data.get('OrdenesHistorialPago', []) or []:
                lugar_origen = data.get('lugar_origen', '')
                if lugar_origen in ['Restaurante', 'Llevar']:
                    tipo_pago = item.get('tipo_pago', '')
                    pos_text = f"({item.get('pos', '')})" if tipo_pago == 'Tarjeta' else ''
                    self.left_right(printer, tipo_pago + pos_text, f"${self.format_currency(item.get('monto', 0))}")
                else:
                    self.left_right(printer, lugar_origen, f"${item.get('monto', 0)}")
                metodo_pago = item.get('tipo_pago', '')

            if metodo_pago == 'Efectivo':
                self.draw_line(printer)
                self.left_right(printer, 'Cambio:', f"${self.format_currency(data.get('monto_cambio', 0))}")
                self.draw_line(printer)

            self.draw_line(printer)
            printer.set(bold=False, align='center')
            printer.println('Gracias por su visita!')
            printer.set(bold=True)
            printer.println(f"ORDEN #: {data.get('numero_orden', '')}")
            printer.set(bold=False)
            printer.println(f"Fecha: {data.get('fecha_creacion', '')}")

            printer.cut()
            printer.print_raw()

            return {'success': True, 'message': 'Impresion exitosa'}
        except Exception as e:
            print(f"Error en print_precuenta: {str(e)}")
            return {'success': False, 'message': str(e)}

    def imprimir_comanda(self, data):
        """Imprime comanda de cocina"""
        try:
            printer = self.create_printer()

            printer.set(width=2, height=2, align='left')
            lugar_origen = data.get('lugar_origen', '')
            origen_text = "MESAS" if lugar_origen == "Restaurante" else lugar_origen
            printer.println(f"{origen_text} ORDEN #: {data.get('numero_orden', '')}")

            mesa = data.get('Mesa', {}) or {}
            mesa_text = f"Mesa {mesa.get('numero', '')}" if lugar_origen == "Restaurante" else data.get('cliente', '')
            printer.println(mesa_text)

            usuarios = data.get('Usuarios', {}) or {}
            printer.println(f"EMPLEADO: {usuarios.get('nombres', '')} {usuarios.get('apellidos', '')}")

            self.print_single_line(printer)

            fecha_creacion = datetime.now()
            for item in data.get('detalleItems', []) or []:
                printer.println(f"({item.get('cantidad', 0)}) {item.get('nombre', '')}")
                comentario = item.get('comentario')
                if comentario:
                    printer.println(f"  - {comentario}")
                self.print_single_line(printer)
                try:
                    fecha_creacion = datetime.fromisoformat(item.get('fecha_creacion', '').replace('Z', '+00:00'))
                except:
                    pass

            printer.println(self.convert_with_time(str(fecha_creacion)))

            printer.cut()
            printer.buzzer(3, 3)
            printer.print_raw()

            return {'success': True, 'message': 'Impresion exitosa'}
        except Exception as e:
            print(f"Error en imprimir_comanda: {str(e)}")
            return {'success': False, 'message': str(e)}

    def imprimir_cierre_caja(self, data, con_detalle):
        """Imprime cierre de caja"""
        try:
            printer = self.create_printer()

            # Header
            printer.set(align='center', width=2, height=2)
            printer.println(data.get('nombre_sistema', ''))
            printer.set(width=1, height=1)
            printer.println(data.get('direccion', ''))
            self.draw_line(printer)

            usuarios = data.get('Usuarios', {}) or {}
            printer.println(f"{usuarios.get('nombres', '')} {usuarios.get('apellidos', '')}")
            self.draw_line(printer)
            printer.println(data.get('fecha_cierre', ''))
            self.draw_line(printer)

            printer.set(align='center')
            printer.println('RESUMEN DE EFECTIVO')
            printer.set(align='left')
            printer.println('Efectivo Inicial')
            printer.set(align='right')
            printer.println(f"$ {data.get('monto_inicial', 0)}")

            printer.set(align='left')
            printer.println('Efectivo (+)')
            printer.set(align='right')
            efectivo_real = self.to_number(data.get('efectivoReal', 0))
            total_efectivo = self.to_number(data.get('totalEfectivo', 0))
            printer.println(f"$ {efectivo_real if efectivo_real > 0 else total_efectivo}")

            printer.set(align='left')
            printer.println('Compras (-)')
            printer.set(align='right')
            printer.println(f"$ {data.get('totalCompras', 0)}")

            printer.set(align='left')
            printer.println('Efectivo Total En Caja')
            printer.set(align='right')
            printer.println(f"$ {data.get('efectivoTotal', 0)}")

            self.draw_line(printer)

            # Resumen de Otras Transacciones
            printer.set(align='center')
            printer.println('RESUMEN DE OTRAS TRANSACCIONES')

            tarjetas = [
                ('SERFINSA', 'totalTarjetaSERFINSA', 'contadorTarjetaSERFINSA'),
                ('BAC', 'totalTarjetaBAC', 'contadorTarjetaBAC'),
                ('AGRICOLA', 'totalTarjetaAGRICOLA', 'contadorTarjetaAGRICOLA'),
                ('CREDOMATIC', 'totalTarjetaCREDOMATIC', 'contadorTarjetaCREDOMATIC'),
                ('PROMERICA', 'totalTarjetaPROMERICA', None),
                ('CUSCA', 'totalTarjetaCUSCA', None),
                ('DAVIVIENDA', 'totalTarjetaDAVIVIENDA', None),
            ]

            for nombre, total_key, contador_key in tarjetas:
                total = self.to_number(data.get(total_key, 0))
                if total > 0:
                    printer.set(align='left')
                    contador = f"({data.get(contador_key, '')})" if contador_key and data.get(contador_key) else ''
                    printer.println(f"{nombre}{contador}")
                    printer.set(align='right')
                    printer.println(f"$ {total}")

            if self.to_number(data.get('pedidosYa', 0)) > 0:
                printer.set(align='left')
                printer.println(f"PEDIDOS YA({data.get('contadorPedidosYa', '')})")
                printer.set(align='right')
                printer.println(f"$ {data.get('pedidosYa', 0)}")

            if self.to_number(data.get('uberEats', 0)) > 0:
                printer.set(align='left')
                printer.println(f"UBER EATS({data.get('contadoruberEats', '')})")
                printer.set(align='right')
                printer.println(f"$ {data.get('uberEats', 0)}")

            otros = [
                ('CORTESIA', 'totalCortecia', 'contadorCortecia'),
                ('Certificado', 'totalCertificado', 'contadorCertificado'),
                ('BITCOIN', 'bitcoinReal', None),
                ('TRANSFERENCIA', 'transferenciaReal', None),
                ('Credito', 'totalCredito', 'contadorCredito'),
            ]

            for nombre, total_key, contador_key in otros:
                total = self.to_number(data.get(total_key, 0))
                if total > 0:
                    printer.set(align='left')
                    contador = f"({data.get(contador_key, '')})" if contador_key and data.get(contador_key) else ''
                    printer.println(f"{nombre}{contador}")
                    printer.set(align='right')
                    printer.println(f"$ {total}")

            if self.to_number(data.get('llevar', 0)) > 0:
                self.draw_line(printer)
                printer.set(align='left')
                printer.println(f"PARA LLEVAR({data.get('contadorLlevar', '')})")
                printer.set(align='right')
                printer.println(f"$ {data.get('llevar', 0)}")
                self.draw_line(printer)

            printer.set(align='center')
            printer.println('RESUMEN DE TOTAL DE VENTAS')
            self.draw_line(printer)

            printer.set(align='left')
            printer.println('VENTA BRUTA')
            printer.set(align='right')
            printer.println(f"$ {data.get('ventaTotal', 0)}")

            printer.set(align='left')
            printer.println('VENTA SIN PROPINA')
            printer.set(align='right')
            printer.println(f"$ {data.get('ventaSinPropina', 0)}")

            printer.set(align='left')
            printer.println('VENTA SIN IVA')
            printer.set(align='right')
            printer.println(f"$ {data.get('ventaSinIva', 0)}")

            if self.to_number(data.get('ordenesActivas', 0)) > 0:
                self.draw_line(printer)
                printer.set(align='left')
                printer.println('ORDENES ACTIVAS')
                printer.set(align='right')
                printer.println(f"$ {data.get('ordenesActivas', 0)}")

            self.draw_line(printer)
            printer.set(align='left')
            self.left_right(printer, 'Estado:', data.get('estado_caja', ''))
            self.draw_line(printer)
            printer.println('Observaciones')
            printer.println(data.get('observaciones', '') or '')
            self.draw_line(printer)

            if con_detalle == 1:
                self.draw_line(printer)
                printer.set(align='center')
                printer.println('LISTADO DE ORDENES')
                printer.set(align='left')

                for orden in data.get('OrdenesDeRestaurante', []) or []:
                    fecha_orden = self.convert_with_time(str(orden.get('fecha_creacion', '')))
                    printer.println(f"Orden #{orden.get('numero_orden', '')} | Fecha: {fecha_orden} | Total: ${orden.get('total', 0)}")

                    for detalle in orden.get('OrdenesHistorialPago', []) or []:
                        self.table_custom(printer, [
                            {'text': detalle.get('tipo_pago', ''), 'width': 0.3, 'align': 'CENTER'},
                            {'text': detalle.get('pos', '') or '', 'width': 0.50, 'align': 'LEFT'},
                            {'text': self.format_currency(detalle.get('monto', 0)), 'width': 0.2, 'align': 'RIGHT'}
                        ])
                    self.draw_line(printer)

            printer.cut()
            printer.print_raw()

            return {'success': True, 'message': 'Impresion exitosa'}
        except Exception as e:
            print(f"Error en imprimir_cierre_caja: {str(e)}")
            return {'success': False, 'message': str(e)}

    def imprimir_cierre_diario(self, data):
        """Imprime cierre diario"""
        try:
            printer = self.create_printer()

            fecha_cierre = self.convert_with_time(data.get('fecha', ''))

            printer.set(align='center', width=2, height=2)
            printer.println('CIERRE DIARIO')
            printer.println(data.get('nombre_sistema', ''))
            printer.set(width=1, height=1)
            printer.println(fecha_cierre)
            self.draw_line(printer)

            usuarios = data.get('Usuarios', {})
            if usuarios:
                printer.set(align='center')
                printer.println(f"{usuarios.get('nombres', '')} {usuarios.get('apellidos', '')}")

            self.draw_line(printer)
            printer.set(align='center')
            printer.println('RESUMEN DE VENTAS')
            self.draw_line(printer)

            printer.set(align='left')
            printer.println('VENTA BRUTA')
            printer.set(align='right')
            printer.println(f"$ {self.to_number(data.get('ventaBruta', 0)):.2f}")

            printer.set(align='left')
            printer.println('VENTA SIN PROPINA')
            printer.set(align='right')
            printer.println(f"$ {self.to_number(data.get('ventaSinPropina', 0)):.2f}")

            printer.set(align='left')
            printer.println('VENTA SIN IVA')
            printer.set(align='right')
            printer.println(f"$ {self.to_number(data.get('ventaSinIva', 0)):.2f}")

            printer.set(align='center')
            printer.println('METODOS DE PAGO')
            self.draw_line(printer)

            printer.set(align='left')
            printer.println('EFECTIVO')
            printer.set(align='right')
            printer.println(f"$ {self.to_number(data.get('efectivo', 0)):.2f}")

            metodos_pago = [
                ('CREDOMATIC', 'redomati'),
                ('SERFINSA', 'serfinsa'),
                ('PROMERICA', 'promerica'),
            ]

            for nombre, key in metodos_pago:
                valor = self.to_number(data.get(key, 0))
                if valor > 0:
                    printer.set(align='left')
                    printer.println(nombre)
                    printer.set(align='right')
                    printer.println(f"$ {valor:.2f}")

            if self.to_number(data.get('totalTarjetaCredito', 0)) > 0:
                printer.set(align='left')
                printer.println('TOTAL POS')
                printer.set(align='right')
                printer.println(f"$ {self.to_number(data.get('totalTarjetaCredito', 0)):.2f}")

            printer.set(align='center')
            printer.println('SERVICIOS DE ENTREGA')
            self.draw_line(printer)

            servicios = [
                ('PARA LLEVAR', 'paraLlevar'),
                ('UBER EATS', 'uberEats'),
                ('PEDIDOS YA', 'pedidoYa'),
            ]

            for nombre, key in servicios:
                valor = self.to_number(data.get(key, 0))
                if valor > 0:
                    printer.set(align='left')
                    printer.println(nombre)
                    printer.set(align='right')
                    printer.println(f"$ {valor:.2f}")

            self.draw_line(printer)

            otros = [
                ('PROPINA', 'propina'),
                ('CORTESIA', 'cortesia'),
                ('BITCOIN', 'bitcoinReal'),
                ('CERTIFICADO REGALO', 'certificadoRegalo'),
                ('TRANSFERENCIA', 'transferencia'),
                ('CREDITO', 'foundever'),
            ]

            for nombre, key in otros:
                valor = self.to_number(data.get(key, 0))
                if valor > 0:
                    printer.set(align='left')
                    printer.println(nombre)
                    printer.set(align='right')
                    printer.println(f"$ {valor:.2f}")

            self.draw_line(printer)

            printer.set(bold=True, align='left')
            printer.println('COMPRAS')
            printer.set(align='right')
            printer.println(f"$ {self.to_number(data.get('compras', 0)):.2f}")

            printer.set(align='left')
            printer.println('EFECTIVO')
            printer.set(align='right')
            printer.println(f"$ {self.to_number(data.get('entregaEfectivo', 0)):.2f}")
            printer.set(bold=False)

            self.draw_line(printer)
            self.draw_line(printer)
            printer.set(align='left')
            printer.println('ESTADO')
            printer.set(align='right')
            estado = 'CERRADO' if (data.get('id_cierre', 0) or 0) > 0 else 'ABIERTO'
            printer.println(estado)

            self.draw_line(printer)
            self.draw_line(printer)

            printer.set(bold=True, width=2, height=2, align='center')
            printer.println('REMESA')
            printer.println(f"$ {self.to_number(data.get('remesaDonVitto', 0)):.2f}")
            printer.set(width=1, height=1, bold=False)

            self.draw_line(printer)
            self.draw_line(printer)
            printer.cut()
            printer.print_raw()

            return {'success': True, 'message': 'Impresion de cierre diario exitosa'}
        except Exception as e:
            print(f"Error en imprimir_cierre_diario: {str(e)}")
            return {'success': False, 'message': str(e)}

    def print_orden_anulados(self, data):
        """Imprime reporte de anulaciones"""
        try:
            printer = self.create_printer()

            def validate_data(item):
                return {
                    'cantidad': str(item.get('cantidad', '0')),
                    'nombre': str(item.get('nombre', '')),
                    'precio_unitario': item.get('precio_unitario', 0),
                    'precio_total': item.get('precio_total', 0),
                    'motivo': item.get('motivo', 'Sin motivo especificado'),
                    'fecha_creacion': item.get('fecha_creacion', datetime.now().isoformat())
                }

            printer.set(align='center')
            lugar_origen = data.get('lugar_origen', '')
            printer.println('MESAS' if lugar_origen == 'Restaurante' else lugar_origen)
            printer.set(bold=True, width=2, height=2)
            printer.println('REPORTE DE ANULACIONES')
            printer.println(data.get('nombre_comercial', ''))
            printer.set(bold=False, width=1, height=1)

            printer.println(data.get('direccion', ''))
            self.draw_line(printer)

            printer.set(align='left')
            usuarios = data.get('Usuarios', {}) or {}
            printer.println(f"Emp.{usuarios.get('nombres', '')} {usuarios.get('apellidos', '')}")

            left_text = f"Clientes {data.get('numero_personas', '')}"
            right_text = ''
            mesa = data.get('Mesa')
            if mesa:
                right_text = f"Mesa {mesa.get('numero', '')}"
            self.left_right(printer, left_text, right_text)

            printer.println('')
            self.draw_line(printer)
            printer.set(bold=True)
            printer.println('ITEMS ANULADOS')
            self.table_custom(printer, [
                {'text': 'Cant.', 'width': 0.1, 'align': 'CENTER'},
                {'text': 'Descripcion', 'width': 0.4, 'align': 'LEFT'},
                {'text': 'Precio', 'width': 0.2, 'align': 'RIGHT'},
                {'text': 'Total', 'width': 0.2, 'align': 'RIGHT'}
            ])
            printer.set(bold=False)

            for item in data.get('OrdenesDetalleEliminados', []) or []:
                validated = validate_data(item)
                self.table_custom(printer, [
                    {'text': validated['cantidad'], 'width': 0.1, 'align': 'CENTER'},
                    {'text': validated['nombre'], 'width': 0.4, 'align': 'LEFT'},
                    {'text': self.format_currency(validated['precio_unitario']), 'width': 0.2, 'align': 'RIGHT'},
                    {'text': self.format_currency(validated['precio_total']), 'width': 0.2, 'align': 'RIGHT'}
                ])
                printer.println(f"Motivo: {validated['motivo']}")
                try:
                    fecha = datetime.fromisoformat(validated['fecha_creacion'].replace('Z', '+00:00'))
                    printer.println(f"Fecha: {fecha.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    printer.println(f"Fecha: {validated['fecha_creacion']}")
                self.draw_line(printer)

            pagos_eliminados = data.get('OrdenesHistorialPagoEliminados', []) or []
            if pagos_eliminados:
                printer.set(bold=True)
                printer.println('PAGOS ANULADOS')
                printer.set(bold=False)

                for pago in pagos_eliminados:
                    tipo_pago = pago.get('tipo_pago', '')
                    pos = pago.get('pos', '')
                    pos_text = f" ({pos})" if pos else ''
                    self.left_right(printer, f"{tipo_pago}{pos_text}", f"${self.format_currency(pago.get('monto', 0))}")
                    printer.println(f"Motivo: {pago.get('motivo', '')}")
                    try:
                        fecha = datetime.fromisoformat(pago.get('fecha_creacion', '').replace('Z', '+00:00'))
                        printer.println(f"Fecha: {fecha.strftime('%Y-%m-%d %H:%M:%S')}")
                    except:
                        printer.println(f"Fecha: {pago.get('fecha_creacion', '')}")
                    self.draw_line(printer)

            printer.set(align='center', bold=True)
            printer.println(f"ORDEN #: {data.get('numero_orden', '')}")
            printer.set(bold=False)
            printer.println(f"Fecha del reporte: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            printer.println('')
            printer.println('')
            self.draw_line(printer)
            printer.set(align='center')
            printer.println('RESPONSABLE DE ANULACION')
            printer.println(f"{usuarios.get('nombres', '')} {usuarios.get('apellidos', '')}")
            printer.println('')
            printer.println('_______________________')
            printer.println('Firma')

            printer.println('')
            printer.println('')
            self.draw_line(printer)
            printer.println('AUTORIZADO POR')
            printer.println('')
            printer.println('_______________________')
            printer.println('Nombre y Firma')
            printer.println('')

            self.draw_line(printer)
            printer.set(align='left')
            printer.println('Observaciones:')
            printer.println('_______________________')
            printer.println('_______________________')
            printer.println('_______________________')

            printer.cut()
            printer.print_raw()

            return {'success': True, 'message': 'Impresion de anulaciones exitosa'}
        except Exception as e:
            print(f"Error en print_orden_anulados: {str(e)}")
            return {'success': False, 'message': str(e)}

    def print_factura_electronica(self, data):
        """Imprime factura electronica DTE"""
        try:
            printer = self.create_printer()

            emisor = data.get('emisor', {}) or {}
            receptor = data.get('receptor', {}) or {}
            identificacion = data.get('identificacion', {}) or {}
            resumen = data.get('resumen', {}) or {}

            printer.set(align='center', bold=True, width=2, height=2)
            printer.println(emisor.get('nombreComercial', ''))
            printer.set(width=1, height=1, bold=False)

            if emisor.get('telefono'):
                printer.println(f"Tel: {emisor.get('telefono')}")
            printer.println(emisor.get('direccion', ''))
            self.draw_line(printer)

            printer.set(align='center', bold=True)
            printer.println('DOCUMENTO TRIBUTARIO ELECTRONICO')
            printer.println(data.get('nombreFactura', ''))
            printer.set(bold=False, align='left')

            printer.println('Codigo de Generacion:')
            printer.println(identificacion.get('codigoGeneracion', ''))
            printer.println('Numero de Control:')
            printer.println(identificacion.get('numeroControl', ''))
            printer.println(f"Sello: {data.get('selloRecibido', '')}")
            printer.println(f"Numero de Orden: {data.get('numero_orden', '')}")
            printer.println(f"Fecha: {identificacion.get('fecEmi', '')} {identificacion.get('horEmi', '')}")
            self.draw_line(printer)

            printer.set(bold=True)
            printer.println('EMISOR')
            printer.set(bold=False)
            printer.println(f"NIT: {emisor.get('nit', '')}")
            printer.println(f"NRC: {emisor.get('nrc', '')}")
            printer.println(f"Actividad economica: {emisor.get('descActividad', '')}")
            printer.println(f"Numero de telefono: {emisor.get('telefono', '')}")
            printer.println(f"Correo electronico: {emisor.get('correo', '')}")
            printer.println(f"Nombre Comercial: {emisor.get('nombreComercial', '')}")
            printer.println(f"Tipo de establecimiento: {emisor.get('tipoEstablecimiento', '')}")
            self.draw_line(printer)

            printer.set(bold=True)
            printer.println('RECEPTOR')
            printer.set(bold=False)
            printer.println(f"Nombre: {receptor.get('nombre', '')}")

            tipo_dte = identificacion.get('tipoDte', '')
            if tipo_dte == '03':
                printer.println(f"NIT: {receptor.get('nit', '')}")
            elif receptor.get('numDocumento'):
                printer.println(f"Doc: {receptor.get('numDocumento', '')}")

            if receptor.get('nrc'):
                printer.println(f"NRC: {receptor.get('nrc')}")
            if receptor.get('descActividad'):
                printer.println(f"Actividad: {receptor.get('descActividad')}")
            if receptor.get('direccion'):
                printer.println(f"Direccion: {receptor.get('direccion')}")
            if receptor.get('telefono'):
                printer.println(f"Telefono: {receptor.get('telefono')}")
            if receptor.get('correo'):
                printer.println(f"Correo: {receptor.get('correo')}")
            self.draw_line(printer)

            printer.set(bold=True)
            self.table_custom(printer, [
                {'text': 'Cant', 'width': 0.1, 'align': 'CENTER'},
                {'text': 'Descripcion', 'width': 0.40, 'align': 'LEFT'},
                {'text': 'P.Unit', 'width': 0.2, 'align': 'RIGHT'},
                {'text': 'Total', 'width': 0.2, 'align': 'RIGHT'}
            ])
            printer.set(bold=False)

            for item in data.get('cuerpoDocumento', []) or []:
                if item.get('codigo') != '0000':
                    venta_gravada = item.get('ventaGravada', 0)
                    venta_exenta = item.get('ventaExenta', 0)
                    no_gravado = item.get('noGravado', 0)
                    precios_total = venta_gravada if venta_gravada > 0 else venta_exenta

                    precio_unitario = str(no_gravado) if no_gravado > 0 else str(item.get('precioUni', 0))
                    precio_total = str(no_gravado) if no_gravado > 0 else str(precios_total)
                    sufijo = ' NG' if no_gravado > 0 else ' G'

                    self.table_custom(printer, [
                        {'text': str(item.get('cantidad', 0)), 'width': 0.1, 'align': 'CENTER'},
                        {'text': item.get('descripcion', ''), 'width': 0.4, 'align': 'LEFT'},
                        {'text': precio_unitario, 'width': 0.2, 'align': 'RIGHT'},
                        {'text': precio_total + sufijo, 'width': 0.2, 'align': 'RIGHT'}
                    ])

            self.draw_line(printer)

            printer.set(bold=True)
            printer.println('NG= No Gravado  G= Gravado')
            printer.set(bold=False)

            printer.set(align='right')
            printer.println(f"Subtotal: ${resumen.get('subTotalVentas', 0)}")
            printer.println(f"Subtotal no grabado: ${resumen.get('totalNoGravado', 0)}")

            if self.to_number(resumen.get('descuGravada', 0)) > 0:
                printer.println(f"Descuento: ${resumen.get('descuGravada', 0)}")

            tributos = resumen.get('tributos', []) or []
            for tributo in tributos:
                printer.println(f"{tributo.get('descripcion', '')}: ${tributo.get('valor', 0)}")

            printer.set(bold=True, width=2, height=2)
            printer.println(f"TOTAL: ${resumen.get('totalPagar', 0)}")
            printer.set(width=1, height=1, bold=False)

            self.draw_line(printer)

            for item in data.get('metodosPago', []) or []:
                tipo_pago = item.get('tipo_pago', '')
                pos = item.get('pos', '')
                pos_text = f" ({pos})" if pos else ''
                self.table_custom(printer, [
                    {'text': tipo_pago + pos_text, 'width': 0.4, 'align': 'LEFT'},
                    {'text': f"${item.get('monto', 0)}", 'width': 0.5, 'align': 'RIGHT'}
                ])

            self.draw_line(printer)

            printer.set(align='center')
            printer.println('Total en letras:')
            printer.println(resumen.get('totalLetras', ''))
            self.draw_line(printer)

            if data.get('qr'):
                try:
                    printer.qr(data.get('qrTicket', ''), size=7)
                except:
                    pass

            printer.println('')
            printer.set(bold=True)
            printer.println('Gracias por su compra')
            printer.set(bold=False)

            if identificacion.get('ambiente') == '00':
                printer.set(width=2, height=2)
                printer.println('Documento de prueba')
                printer.println('No tiene validez')
                printer.set(width=1, height=1)
                printer.println('')
                printer.println('')

            printer.cut()
            printer.print_raw()

            return {'success': True, 'message': 'Impresion exitosa'}
        except Exception as e:
            print(f"Error en print_factura_electronica: {str(e)}")
            return {'success': False, 'message': str(e)}


# Instancia del servicio
impresiones_service = ImpresionesService()


# Endpoints
@app.route('/print/precuenta', methods=['POST'])
def print_precuenta():
    try:
        body = request.get_json()
        data = body.get('data', {})
        result = impresiones_service.print_precuenta(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/print/comanda', methods=['POST'])
def print_comanda():
    try:
        body = request.get_json()
        data = body.get('data', {})
        result = impresiones_service.imprimir_comanda(data.get('data', data))
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/print/cierre-caja', methods=['POST'])
def print_cierre_caja():
    try:
        body = request.get_json()
        data = body.get('data', {})
        con_detalle = body.get('con_detalle', 0)
        result = impresiones_service.imprimir_cierre_caja(data, con_detalle)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/print/cierre-diario', methods=['POST'])
def print_cierre_diario():
    try:
        body = request.get_json()
        data = body.get('data', {})
        result = impresiones_service.imprimir_cierre_diario(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/print/anulados', methods=['POST'])
def print_anulados():
    try:
        body = request.get_json()
        data = body.get('data', {})
        result = impresiones_service.print_orden_anulados(data.get('data', data))
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/print/factura-electronica', methods=['POST'])
def print_factura_electronica():
    try:
        body = request.get_json()
        data = body.get('data', {})
        result = impresiones_service.print_factura_electronica(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/print/abrir-cajon', methods=['POST'])
def abrir_cajon():
    try:
        result = impresiones_service.aperturar_cajon()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/printer/status', methods=['GET'])
def printer_status():
    try:
        printer_name = impresiones_service.get_printer_name()
        if not printer_name:
            return jsonify({
                'success': False,
                'connected': False,
                'message': 'No hay impresora configurada'
            })

        return jsonify({
            'success': True,
            'connected': True,
            'name': printer_name,
            'config': config['printer']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'connected': False,
            'message': str(e)
        })


@app.route('/printer/list', methods=['GET'])
def printer_list():
    """Lista todas las impresoras instaladas en Windows"""
    try:
        if not WIN32_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'win32print no disponible. Instale: pip install pywin32',
                'printers': []
            })

        printers = []
        default_printer = win32print.GetDefaultPrinter()

        # Obtener todas las impresoras
        printer_info = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )

        for printer in printer_info:
            printers.append({
                'name': printer[2],
                'is_default': printer[2] == default_printer
            })

        return jsonify({
            'success': True,
            'printers': printers,
            'default': default_printer
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'printers': []
        })


@app.route('/printer/config', methods=['GET'])
def get_config():
    """Obtiene la configuracion actual"""
    return jsonify(config)


@app.route('/printer/config', methods=['POST'])
def update_config():
    """Actualiza la configuracion de la impresora"""
    try:
        body = request.get_json()

        if 'name' in body:
            config['printer']['name'] = body['name']
        if 'vendor_id' in body:
            config['printer']['vendor_id'] = body['vendor_id']
        if 'product_id' in body:
            config['printer']['product_id'] = body['product_id']

        save_config(config)

        return jsonify({
            'success': True,
            'message': 'Configuracion actualizada',
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/printer/test', methods=['POST'])
def test_print():
    """Imprime una pagina de prueba"""
    try:
        printer = impresiones_service.create_printer()

        printer.set(align='center', bold=True, width=2, height=2)
        printer.println('PRUEBA DE IMPRESION')
        printer.set(width=1, height=1, bold=False)
        printer.println('')
        printer.println(f'Impresora: {impresiones_service.get_printer_name()}')
        printer.println(f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        printer.println('')
        impresiones_service.draw_line(printer)
        printer.println('Si puede leer esto, la')
        printer.println('impresora esta funcionando')
        printer.println('correctamente.')
        impresiones_service.draw_line(printer)
        printer.println('')
        printer.set(align='center')
        printer.println('Print Server Python')
        printer.println('Version 1.0')
        printer.cut()

        printer.print_raw()

        return jsonify({
            'success': True,
            'message': 'Prueba enviada a la impresora'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


if __name__ == '__main__':
    port = config.get('port', 3003)
    print(f"=" * 50)
    print(f"  Print Server (Python) v1.0")
    print(f"=" * 50)
    print(f"Servidor: http://localhost:{port}")
    print(f"")

    if WIN32_AVAILABLE:
        try:
            default_printer = win32print.GetDefaultPrinter()
            configured_printer = config.get('printer', {}).get('name', '')
            printer_to_use = configured_printer if configured_printer else default_printer
            print(f"Impresora: {printer_to_use}")
        except:
            print("Impresora: No configurada")
    else:
        print("[WARN] win32print no disponible")
        print("       Instale: pip install pywin32")

    print(f"")
    print(f"Endpoints disponibles:")
    print(f"  POST /print/precuenta")
    print(f"  POST /print/comanda")
    print(f"  POST /print/cierre-caja")
    print(f"  POST /print/cierre-diario")
    print(f"  POST /print/anulados")
    print(f"  POST /print/factura-electronica")
    print(f"  POST /print/abrir-cajon")
    print(f"  POST /printer/test")
    print(f"  GET  /printer/status")
    print(f"  GET  /printer/list")
    print(f"  GET  /printer/config")
    print(f"  POST /printer/config")
    print(f"=" * 50)

    app.run(host='0.0.0.0', port=port, debug=False)
