// print-server.js
const express = require('express');
const cors = require('cors');
const { ThermalPrinter, PrinterTypes } = require('node-thermal-printer');

const app = express();
const PORT = 3003;

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));



class ImpresionesService {
    constructor() {
        this.printers = new Map(); // Cache de conexiones
    }

    async createPrinterConnection(ip, port = '9100') {
        const key = `${ip}:${port}`;

        if (this.printers.has(key)) {
            return this.printers.get(key);
        }

        const printer = new ThermalPrinter({
            type: PrinterTypes.EPSON,
            interface: `tcp://${ip}:${port}`,
            removeSpecialCharacters: true,
            options: {
                timeout: 5000,
            },
            driver: {
                encoding: 'UTF-8'
            }
        });

        let isConnected = false;
        let retryCount = 0;
        const maxRetries = 4;
        const retryDelay = 1000;

        while (!isConnected && retryCount < maxRetries) {
            try {
                isConnected = await printer.isPrinterConnected();
                if (!isConnected) {
                    retryCount++;
                    console.log(`Intento de conexión ${retryCount} de ${maxRetries}`);
                    await new Promise(resolve => setTimeout(resolve, retryDelay));
                }
            } catch (error) {
                retryCount++;
                console.log(`Error en intento ${retryCount}: ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, retryDelay));
            }
        }

        if (!isConnected) {
            throw new Error(`No se pudo establecer conexión con la impresora ${ip} después de ${maxRetries} intentos`);
        }

        this.printers.set(key, printer);
        return printer;
    }

    async executePrint(printer) {
        try {
            await printer.execute();
        } finally {
            printer.clear();
        }
    }

    formatCurrency(amount) {
        if (typeof amount !== 'number') {
            return amount;
        }
        if (amount === 0) {
            return '0.00';
        }
        return amount.toFixed(2);
    }

    convertWithTime = (str) => {
        // Crear fecha UTC
        const utcDate = new Date(str);

        // Convertir a tiempo de El Salvador (UTC-6)
        const svOptions = {
            timeZone: 'America/El_Salvador',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true // Cambiar a true para formato AM/PM
        };

        // Formatear la fecha según la zona horaria de El Salvador
        const svDateTime = utcDate.toLocaleString('es-SV', svOptions);

        // Reformatear al formato deseado DD-MM-YYYY hh:mm AM/PM
        const [date, time] = svDateTime.split(', ');
        const [day, month, year] = date.split('/');

        // Extraer solo hora y minutos con AM/PM
        const timeFormat = time.split(':').slice(0, 2).join(':');
        const period = time.includes('p.') ? 'pm' : 'am';

        return `${day}-${month}-${year} ${timeFormat}`;
    }
    printSingleLine(printer) {
        const line = printer.getWidth() / 2;
        printer.println('-'.repeat(line) + '\n');
    }

    async aperturarCajon(ip) {
        try {
            const printer = await this.createPrinterConnection(ip);
            printer.openCashDrawer();
            try {
                printer.raw(Buffer.from([0x1B, 0x70, 0x00, 0x19, 0xFA]));
            } catch (error) {
                console.log(error.message);
                console.log("no se pudo mandar a abrir el cajon");
            }
            return { success: true, message: 'Cajón abierto' };
        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }

    async printPreCuenta(data, printerIp) {
        try {
            const printer = await this.createPrinterConnection(printerIp);

            const validateData = (item) => {
                return {
                    cantidad: item.cantidad?.toString() || '0',
                    nombre: item.nombre?.toString() || '',
                    precio_unitario: item.precio_unitario || 0,
                    precio_total: item.precio_total || 0
                };
            };

            // Header
            printer.alignCenter();
            // printer.println(data?.lugar_origen == "Restaurante" ? "MESAS" : data?.lugar_origen || '');
            printer.bold(true);
            printer.setTextSize(1, 1);
            printer.println(data?.nombre_comercial);
            printer.bold(false);
            printer.setTextSize(0, 0);

            printer.println(data?.direccion);
            printer.drawLine();

            printer.alignLeft();
            printer.println("Emp." + `${data?.Usuarios?.nombres} ${data?.Usuarios?.apellidos}`);

            const leftText = `Clientes ${data?.numero_personas}`;
            let rightText = ``;
            if (data.Mesa !== null && data.Mesa !== undefined) {
                rightText = `Mesa ${data?.Mesa.numero}`;
            }
            printer.leftRight(leftText, rightText);

            printer.alignLeft();
            printer.println('');
            printer.drawLine();
            printer.bold(true);
            printer.tableCustom([
                { text: "Cant.", width: 0.15, align: 'CENTER' },
                { text: "Descripción", width: 0.40, align: 'LEFT' },
                { text: "Precio", width: 0.2, align: 'RIGHT' },
                { text: "Total", width: 0.2, align: 'RIGHT' }
            ]);

            printer.bold(false);

            data?.OrdenesDeRestauranteDetalle?.forEach(item => {
                const validatedItem = validateData(item);
                printer.tableCustom([
                    { text: validatedItem.cantidad, width: 0.1, align: 'CENTER' },
                    { text: validatedItem.nombre, width: 0.50, align: 'LEFT' },
                    { text: `${this.formatCurrency(validatedItem.precio_unitario)}`, width: 0.2, align: 'RIGHT' },
                    { text: `${this.formatCurrency(validatedItem.precio_total)}`, width: 0.2, align: 'RIGHT' }
                ]);
            });

            printer.drawLine();
            printer.alignRight();
            let descuentos = '';
            if (data.Descuento != null) {
                descuentos = `Descuento $-${data?.monto_descuento ?? 0} (${data.Descuento.porcentaje ?? 0}%)`;
            }

            printer.leftRight('Subtotal:', descuentos + `   $${data?.subtotal}`);
            printer.leftRight('Propina (10%):', `$${data?.propina}`);

            printer.setTextSize(1, 1);
            const totalText = "Total:";
            const totalAmount = `$${this.formatCurrency(data?.total)}`;
            const espaciosTotales = printer.getWidth() / 2;
            const espaciosUsados = totalText.length + totalAmount.length;
            const spaces = " ".repeat(espaciosTotales - espaciosUsados);
            printer.println(totalText + spaces + totalAmount);
            printer.setTextSize(0, 0);

            printer.leftRight('ESTADO:', `${data?.estado}`);
            printer.drawLine();

            let metodoPago = '';
            data?.OrdenesHistorialPago?.forEach(item => {
                if (data.lugar_origen == "Restaurante" || data.lugar_origen == "Llevar") {
                    printer.leftRight(item.tipo_pago + (item.tipo_pago == 'Tarjeta' ? '(' + item.pos + ')' : ''), `$${this.formatCurrency(item?.monto)}`);
                } else {
                    printer.leftRight(data.lugar_origen, `$${item?.monto}`);
                }
                metodoPago = item.tipo_pago;
            });

            if (metodoPago == 'Efectivo') {
                printer.drawLine();
                printer.leftRight('Cambio:', `$${this.formatCurrency(data?.monto_cambio)}`);
                printer.drawLine();
            }

            printer.drawLine();
            printer.bold(false);
            printer.alignCenter();
            printer.println('¡Gracias por su visita!');
            printer.bold(true);
            printer.println(`ORDEN #: ${data?.numero_orden}`);
            printer.bold(false);
            printer.println(`Fecha: ${data?.fecha_creacion}`);

            printer.cut();
            await this.executePrint(printer);
            return { success: true, message: 'Impresión exitosa' };
        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }

    async imprimirComanda(data, printerIp) {
        try {
            const printer = await this.createPrinterConnection(printerIp);

            printer.setTextSize(1, 1);
            printer.alignLeft();
            printer.println((data?.lugar_origen == "Restaurante" ? "MESAS" : data?.lugar_origen || '') + ` ORDEN #: ${data?.numero_orden}`);
            printer.println(data?.lugar_origen == "Restaurante" ? `Mesa ${data?.Mesa?.numero}` : data?.cliente || '');
            printer.println("EMPLEADO: " + `${data?.Usuarios?.nombres} ${data?.Usuarios?.apellidos}`);

            this.printSingleLine(printer);
            let fecha_creacion = new Date();
            data?.detalleItems?.forEach(item => {
                printer.println(`(${item.cantidad}) ${item.nombre}`);
                if (item.comentario != null && item.comentario != "") {
                    printer.println(`  - ${item.comentario}`);
                }
                this.printSingleLine(printer);
                try {
                    fecha_creacion = new Date(item.fecha_creacion);
                } catch (error) { }
            });
            printer.println(`${this.convertWithTime(fecha_creacion.toString())}`);

            printer.cut();
            printer.beep(3, 3);
            await this.executePrint(printer);

            return { success: true, message: 'Impresión exitosa' };
        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }

    async imprimirCierreCaja(data, con_detalle, printerIp) {
        try {
            const printer = await this.createPrinterConnection(printerIp);

            // Header
            printer.alignCenter();
            printer.setTextSize(1, 1);
            printer.println(data.nombre_sistema);
            printer.setTextSize(0, 0);
            printer.println(data.direccion);
            printer.drawLine();

            printer.println(`${data.Usuarios?.nombres} ${data.Usuarios?.apellidos}`);
            printer.drawLine();
            printer.println(data.fecha_cierre);
            printer.drawLine();

            printer.alignCenter();
            printer.println('RESUMEN DE EFECTIVO');
            printer.alignLeft();
            printer.println('Efectivo Inicial');
            printer.alignRight();
            printer.println(`$ ${data.monto_inicial}`);

            printer.alignLeft();
            printer.println('Efectivo (+)');
            printer.alignRight();
            printer.println(`$ ${data.efectivoReal > 0 ? data.efectivoReal : data.totalEfectivo}`);

            printer.alignLeft();
            printer.println('Compras (-)');
            printer.alignRight();
            printer.println(`$ ${data.totalCompras}`);

            printer.alignLeft();
            printer.println('Efectivo Total En Caja');
            printer.alignRight();
            printer.println(`$ ${data.efectivoTotal}`);

            printer.drawLine();

            // Resumen de Otras Transacciones
            printer.alignCenter();
            printer.println('RESUMEN DE OTRAS TRANSACCIONES');

            // Tarjetas
            if (data.totalTarjetaSERFINSA > 0) {
                printer.alignLeft();
                printer.println(`SERFINSA(${data.contadorTarjetaSERFINSA})`);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaSERFINSA}`);
            }

            if (data.totalTarjetaBAC > 0) {
                printer.alignLeft();
                printer.println(`BAC(${data.contadorTarjetaBAC})`);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaBAC}`);
            }

            if (data.totalTarjetaAGRICOLA > 0) {
                printer.alignLeft();
                printer.println(`AGRICOLA(${data.contadorTarjetaAGRICOLA})`);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaAGRICOLA}`);
            }

            if (data.totalTarjetaCREDOMATIC > 0) {
                printer.alignLeft();
                printer.println(`CREDOMATIC(${data.contadorTarjetaCREDOMATIC})`);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaCREDOMATIC}`);
            }

            if (data.totalTarjetaPROMERICA > 0) {
                printer.alignLeft();
                printer.println(`PROMERICA `);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaPROMERICA}`);
            }

            if (data.totalTarjetaCUSCA > 0) {
                printer.alignLeft();
                printer.println(`CUSCA `);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaCUSCA}`);
            }

            if (data.totalTarjetaDAVIVIENDA > 0) {
                printer.alignLeft();
                printer.println(`DAVIVIENDA `);
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaDAVIVIENDA}`);
            }

            // Servicios de entrega
            if (data.pedidosYa > 0) {
                printer.alignLeft();
                printer.println(`PEDIDOS YA(${data.contadorPedidosYa})`);
                printer.alignRight();
                printer.println(`$ ${data.pedidosYa}`);
            }

            if (data.uberEats > 0) {
                printer.alignLeft();
                printer.println(`UBER EATS(${data.contadoruberEats})`);
                printer.alignRight();
                printer.println(`$ ${data.uberEats}`);
            }

            // Otros
            if (data.totalCortecia > 0) {
                printer.alignLeft();
                printer.println(`CORTESIA(${data.contadorCortecia})`);
                printer.alignRight();
                printer.println(`$ ${data.totalCortecia}`);
            }

            if (data.totalCertificado > 0) {
                printer.alignLeft();
                printer.println(`Certificado(${data.contadorCertificado})`);
                printer.alignRight();
                printer.println(`$ ${data.totalCertificado}`);
            }

            if (data.totalCredito > 0) {
                printer.alignLeft();
                printer.println(`Credito(${data.contadorCredito})`);
                printer.alignRight();
                printer.println(`$ ${data.totalCredito}`);
            }

            if (data.llevar > 0) {
                printer.drawLine();
                printer.alignLeft();
                printer.println(`PARA LLEVAR(${data.contadorLlevar})`);
                printer.alignRight();
                printer.println(`$ ${data.llevar}`);
                printer.drawLine();
            }

            printer.alignCenter();
            printer.println('RESUMEN DE TOTAL DE VENTAS');
            printer.drawLine();
            printer.alignLeft();
            printer.println('VENTA BRUTA');
            printer.alignRight();
            printer.println(`$ ${data.ventaTotal}`);

            printer.alignLeft();
            printer.println('VENTA SIN PROPINA');
            printer.alignRight();
            printer.println(`$ ${data.ventaSinPropina}`);

            printer.alignLeft();
            printer.println('VENTA SIN IVA');
            printer.alignRight();
            printer.println(`$ ${data.ventaSinIva}`);

            if (data.ordenesActivas > 0) {
                printer.drawLine();
                printer.alignLeft();
                printer.println('ORDENES ACTIVAS');
                printer.alignRight();
                printer.println(`$ ${data.ordenesActivas}`);
            }

            printer.drawLine();
            printer.alignLeft();
            printer.leftRight('Estado:', `${data.estado_caja}`);
            printer.drawLine();
            printer.println('Observaciones');
            printer.println(`${data.observaciones ?? ''}`);
            printer.drawLine();

            // Imprimir listado de ordenes
            if (con_detalle == 1) {
                printer.drawLine();
                printer.alignCenter();
                printer.println('LISTADO DE ORDENES');
                printer.alignLeft();
                data.OrdenesDeRestaurante?.forEach(orden => {
                    printer.println(`Orden #${orden.numero_orden} | Fecha: ${this.convertWithTime(orden.fecha_creacion.toString())} | Total: $${orden.total}`);
                    orden.OrdenesHistorialPago?.forEach(detalle => {
                        printer.tableCustom([
                            { text: detalle.tipo_pago, width: 0.3, align: 'CENTER' },
                            { text: detalle.pos ?? '', width: 0.50, align: 'LEFT' },
                            { text: `${this.formatCurrency(detalle.monto ?? '0')}`, width: 0.2, align: 'RIGHT' }
                        ]);
                    });
                    printer.drawLine();
                });
            }

            printer.cut();
            await this.executePrint(printer);

            return { success: true, message: 'Impresión exitosa' };
        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }

    async imprimirCierreDiario(data, printerIp) {
        try {
            const printer = await this.createPrinterConnection(printerIp);

            const fecha_cierre = this.convertWithTime(data.fecha);

            // Header
            printer.alignCenter();
            printer.setTextSize(1, 1);
            printer.println('CIERRE DIARIO');
            printer.setTextSize(0, 0);
            printer.println(fecha_cierre);
            printer.drawLine();

            if (data.Usuarios) {
                printer.alignCenter();
                printer.println(`${data.Usuarios.nombres} ${data.Usuarios.apellidos}`);
            }

            printer.drawLine();
            printer.alignCenter();
            printer.println('RESUMEN DE VENTAS');
            printer.drawLine();

            printer.alignLeft();
            printer.println('VENTA BRUTA');
            printer.alignRight();
            printer.println(`$ ${data.ventaBruta.toFixed(2)}`);

            printer.alignLeft();
            printer.println('VENTA SIN PROPINA');
            printer.alignRight();
            printer.println(`$ ${data.ventaSinPropina.toFixed(2)}`);

            printer.alignLeft();
            printer.println('VENTA SIN IVA');
            printer.alignRight();
            printer.println(`$ ${data.ventaSinIva.toFixed(2)}`);

            // Métodos de pago
            printer.alignCenter();
            printer.println('MÉTODOS DE PAGO');
            printer.drawLine();

            printer.alignLeft();
            printer.println('EFECTIVO');
            printer.alignRight();
            printer.println(`$ ${data.efectivo.toFixed(2)}`);

            if (data.redomati > 0) {
                printer.alignLeft();
                printer.println('CREDOMATIC');
                printer.alignRight();
                printer.println(`$ ${data.redomati.toFixed(2)}`);
            }

            if (data.serfinsa > 0) {
                printer.alignLeft();
                printer.println('SERFINSA');
                printer.alignRight();
                printer.println(`$ ${data.serfinsa.toFixed(2)}`);
            }

            if (data.promerica > 0) {
                printer.alignLeft();
                printer.println('PROMERICA');
                printer.alignRight();
                printer.println(`$ ${data.promerica.toFixed(2)}`);
            }

            if (data.totalTarjetaCredito > 0) {
                printer.alignLeft();
                printer.println('TOTAL POS');
                printer.alignRight();
                printer.println(`$ ${data.totalTarjetaCredito.toFixed(2)}`);
            }

            // Servicios de entrega
            printer.alignCenter();
            printer.println('SERVICIOS DE ENTREGA');
            printer.drawLine();

            if (data.paraLlevar > 0) {
                printer.alignLeft();
                printer.println('PARA LLEVAR');
                printer.alignRight();
                printer.println(`$ ${data.paraLlevar.toFixed(2)}`);
            }

            if (data.uberEats > 0) {
                printer.alignLeft();
                printer.println('UBER EATS');
                printer.alignRight();
                printer.println(`$ ${data.uberEats.toFixed(2)}`);
            }

            if (data.pedidoYa > 0) {
                printer.alignLeft();
                printer.println('PEDIDOS YA');
                printer.alignRight();
                printer.println(`$ ${data.pedidoYa.toFixed(2)}`);
            }

            printer.drawLine();

            if (data.propina > 0) {
                printer.alignLeft();
                printer.println('PROPINA');
                printer.alignRight();
                printer.println(`$ ${data.propina.toFixed(2)}`);
            }

            if (data.cortesia > 0) {
                printer.alignLeft();
                printer.println('CORTESÍA');
                printer.alignRight();
                printer.println(`$ ${data.cortesia.toFixed(2)}`);
            }

            if (data.certificadoRegalo > 0) {
                printer.alignLeft();
                printer.println('CERTIFICADO REGALO');
                printer.alignRight();
                printer.println(`$ ${data.certificadoRegalo.toFixed(2)}`);
            }

            if (data.foundever > 0) {
                printer.alignLeft();
                printer.println('CREDITO');
                printer.alignRight();
                printer.println(`$ ${data.foundever.toFixed(2)}`);
            }

            printer.drawLine();

            printer.bold(true);
            printer.alignLeft();
            printer.println('COMPRAS');
            printer.alignRight();
            printer.println(`$ ${data.compras.toFixed(2)}`);

            printer.alignLeft();
            printer.println('EFECTIVO');
            printer.alignRight();
            printer.println(`$ ${data.entregaEfectivo.toFixed(2)}`);
            printer.bold(false);

            printer.drawLine();
            printer.drawLine();
            printer.alignLeft();
            printer.println('ESTADO');
            printer.alignRight();
            printer.println((data.id_cierre || 0) > 0 ? 'CERRADO' : 'ABIERTO');

            printer.drawLine();
            printer.drawLine();

            printer.bold(true);
            printer.setTextSize(1, 1);
            printer.alignCenter();
            printer.println('REMESA');
            printer.println(`$ ${data.remesaDonVitto.toFixed(2)}`);
            printer.setTextSize(0, 0);
            printer.bold(false);

            printer.drawLine();
            printer.drawLine();
            printer.cut();

            await this.executePrint(printer);

            return { success: true, message: 'Impresión de cierre diario exitosa' };
        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }

    async printOrdenAnulados(data, printerIp) {
        try {
            const printer = await this.createPrinterConnection(printerIp);

            const validateData = (item) => {
                return {
                    cantidad: item.cantidad?.toString() || '0',
                    nombre: item.nombre?.toString() || '',
                    precio_unitario: item.precio_unitario || 0,
                    precio_total: item.precio_total || 0,
                    motivo: item.motivo || 'Sin motivo especificado',
                    fecha_creacion: item.fecha_creacion || new Date()
                };
            };

            // Header
            printer.alignCenter();
            printer.println(data?.lugar_origen == "Restaurante" ? "MESAS" : data?.lugar_origen || '');
            printer.bold(true);
            printer.setTextSize(1, 1);
            printer.println("REPORTE DE ANULACIONES");
            printer.println(data?.nombre_comercial);
            printer.bold(false);
            printer.setTextSize(0, 0);

            printer.println(data?.direccion);
            printer.drawLine();

            printer.alignLeft();
            printer.println("Emp." + `${data?.Usuarios?.nombres} ${data?.Usuarios?.apellidos}`);

            const leftText = `Clientes ${data?.numero_personas}`;
            let rightText = ``;
            if (data.Mesa) {
                rightText = `Mesa ${data?.Mesa.numero}`;
            }
            printer.leftRight(leftText, rightText);

            printer.println('');
            printer.drawLine();
            printer.bold(true);
            printer.println("ITEMS ANULADOS");
            printer.tableCustom([
                { text: "Cant.", width: 0.1, align: 'CENTER' },
                { text: "Descripción", width: 0.4, align: 'LEFT' },
                { text: "Precio", width: 0.2, align: 'RIGHT' },
                { text: "Total", width: 0.2, align: 'RIGHT' }
            ]);
            printer.bold(false);

            data?.OrdenesDetalleEliminados?.forEach(item => {
                const validatedItem = validateData(item);
                printer.tableCustom([
                    { text: validatedItem.cantidad, width: 0.1, align: 'CENTER' },
                    { text: validatedItem.nombre, width: 0.4, align: 'LEFT' },
                    { text: `${this.formatCurrency(validatedItem.precio_unitario)}`, width: 0.2, align: 'RIGHT' },
                    { text: `${this.formatCurrency(validatedItem.precio_total)}`, width: 0.2, align: 'RIGHT' }
                ]);
                printer.println(`Motivo: ${validatedItem.motivo}`);
                printer.println(`Fecha: ${new Date(validatedItem.fecha_creacion).toLocaleString()}`);
                printer.drawLine();
            });

            if (data?.OrdenesHistorialPagoEliminados?.length > 0) {
                printer.bold(true);
                printer.println("PAGOS ANULADOS");
                printer.bold(false);

                data.OrdenesHistorialPagoEliminados.forEach(pago => {
                    printer.leftRight(
                        `${pago.tipo_pago}${pago.pos ? ' (' + pago.pos + ')' : ''}`,
                        `$${this.formatCurrency(pago.monto)}`
                    );
                    printer.println(`Motivo: ${pago.motivo}`);
                    printer.println(`Fecha: ${new Date(pago.fecha_creacion).toLocaleString()}`);
                    printer.drawLine();
                });
            }

            printer.alignCenter();
            printer.bold(true);
            printer.println(`ORDEN #: ${data?.numero_orden}`);
            printer.bold(false);
            printer.println(`Fecha del reporte: ${new Date().toLocaleString()}`);

            printer.println('\n\n');
            printer.drawLine();
            printer.alignCenter();
            printer.println('RESPONSABLE DE ANULACIÓN');
            printer.println(`${data?.Usuarios?.nombres} ${data?.Usuarios?.apellidos}`);
            printer.println('\n');
            printer.println('_______________________');
            printer.println('Firma');

            printer.println('\n\n');
            printer.drawLine();
            printer.println('AUTORIZADO POR');
            printer.println('\n');
            printer.println('_______________________');
            printer.println('Nombre y Firma');
            printer.println('\n');

            printer.drawLine();
            printer.alignLeft();
            printer.println('Observaciones:');
            printer.println('_______________________');
            printer.println('_______________________');
            printer.println('_______________________');

            printer.cut();
            await this.executePrint(printer);
            return { success: true, message: 'Impresión de anulaciones exitosa' };
        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }

    async printFacturaElectronica(data, printerIp) {
        try {
            const printer = await this.createPrinterConnection(printerIp);

            // Header
            printer.alignCenter();
            printer.bold(true);
            printer.setTextSize(1, 1);
            printer.println(data.emisor.nombreComercial);
            printer.setTextSize(0, 0);
            printer.bold(false);

            if (data.emisor.telefono) {
                printer.println(`Tel: ${data.emisor.telefono}`);
            }
            printer.println(data.emisor.direccion);
            printer.drawLine();

            printer.alignCenter();
            printer.bold(true);
            printer.println("DOCUMENTO TRIBUTARIO ELECTRÓNICO");
            printer.println(data.nombreFactura);
            printer.bold(false);
            printer.alignLeft();

            printer.println(`Código de Generación:`);
            printer.println(`${data.identificacion.codigoGeneracion}`);
            printer.println(`Número de Control:`);
            printer.println(`${data.identificacion.numeroControl}`);
            printer.println(`Sello: ${data.selloRecibido}`);
            printer.println(`Número de Orden: ${data.numero_orden}`);
            printer.println(`Fecha: ${data.identificacion.fecEmi} ${data.identificacion.horEmi}`);
            printer.drawLine();

            // Información del emisor
            printer.bold(true);
            printer.println("EMISOR");
            printer.bold(false);
            printer.println(`NIT: ${data.emisor.nit}`);
            printer.println(`NRC: ${data.emisor.nrc}`);
            printer.println(`Actividad económica: ${data.emisor.descActividad}`);
            printer.println(`Número de teléfono: ${data.emisor.telefono}`);
            printer.println(`Correo electrónico: ${data.emisor.correo}`);
            printer.println(`Nombre Comercial: ${data.emisor.nombreComercial}`);
            printer.println(`Tipo de establecimiento: ${data.emisor.tipoEstablecimiento} `);
            printer.drawLine();

            // Información del receptor
            printer.bold(true);
            printer.println("RECEPTOR");
            printer.bold(false);
            printer.println(`Nombre: ${data.receptor.nombre}`);
            if (data.identificacion.tipoDte === '03') {
                printer.println(`NIT: ${data.receptor.nit}`);
            } else if (data.receptor.numDocumento != null) {
                printer.println(`Doc: ${data.receptor.numDocumento}`);
            }
            if (data.receptor.nrc) printer.println(`NRC: ${data.receptor.nrc}`);
            if (data.receptor.descActividad) printer.println(`Actividad: ${data.receptor.descActividad}`);
            if (data.receptor.direccion) printer.println(`Dirección: ${data.receptor.direccion}`);
            if (data.receptor.telefono) printer.println(`Teléfono: ${data.receptor.telefono}`);
            if (data.receptor.correo) printer.println(`Correo: ${data.receptor.correo}`);
            printer.drawLine();

            // Detalles de productos
            printer.bold(true);
            printer.tableCustom([
                { text: "Cant", width: 0.1, align: 'CENTER' },
                { text: "Descripción", width: 0.40, align: 'LEFT' },
                { text: "P.Unit", width: 0.2, align: 'RIGHT' },
                { text: "Total", width: 0.2, align: 'RIGHT' }
            ]);
            printer.bold(false);

            data.cuerpoDocumento.forEach(item => {
                const preciosTotal = item.ventaGravada > 0 ? item.ventaGravada : item.ventaExenta;
                if (item.codigo != "0000") {
                    printer.tableCustom([
                        { text: item.cantidad.toString(), width: 0.1, align: 'CENTER' },
                        { text: item.descripcion, width: 0.4, align: 'LEFT' },
                        { text: item.precioUni.toString(), width: 0.2, align: 'RIGHT' },
                        { text: preciosTotal.toString(), width: 0.2, align: 'RIGHT' }
                    ]);
                }
            });

            printer.drawLine();

            // Totales
            printer.alignRight();
            printer.println(`Subtotal: $${data.resumen.subTotalVentas}`);
            printer.println(`Propina: $${data.resumen.totalNoGravado}`);
            if (data.resumen.descuGravada > 0) {
                printer.println(`Descuento: $${data.resumen.descuGravada}`);
            }

            if (data.resumen.tributos) {
                data.resumen.tributos.forEach(tributo => {
                    printer.println(`${tributo.descripcion}: $${tributo.valor}`);
                });
            }

            printer.bold(true);
            printer.setTextSize(1, 1);
            printer.println(`TOTAL: $${data.resumen.totalPagar}`);
            printer.setTextSize(0, 0);
            printer.bold(false);

            printer.drawLine();

            printer.alignCenter();
            printer.println(`Total en letras:`);
            printer.println(data.resumen.totalLetras);
            printer.drawLine();

            if (data.qr) {
                printer.printQR(data.qrTicket, {
                    cellSize: 7,
                    correction: 'M'
                });
            }

            printer.println('');
            printer.bold(true);
            printer.println('Gracias por su compra');
            printer.bold(false);

            if (data.identificacion.ambiente == "00") {
                printer.setTextSize(1, 1);
                printer.println('Documento de prueba');
                printer.println('No tiene validez');
                printer.setTextSize(0, 0);
                printer.println('');
                printer.println('');
            }

            printer.cut();
            await this.executePrint(printer);
            return { success: true, message: 'Impresión exitosa' };

        } catch (error) {
            console.log(error.message);
            return { success: false, message: error.message };
        }
    }
}

// Instancia del servicio
const impresionesService = new ImpresionesService();

// Endpoints
app.post('/print/precuenta', async (req, res) => {
    try {
        const { data  } = req.body;
        const result = await impresionesService.printPreCuenta(data, data.printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/print/comanda', async (req, res) => {
    try {
        const { data  } = req.body;
        const result = await impresionesService.imprimirComanda(data.data, data.printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/print/cierre-caja', async (req, res) => {
    try {
        const { data  } = req.body;
        const result = await impresionesService.imprimirCierreCaja(data.data, data.con_detalle, data.printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/print/cierre-diario', async (req, res) => {
    try {
        const { data  } = req.body;
        const result = await impresionesService.imprimirCierreDiario(data, data.printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/print/anulados', async (req, res) => {
    try {
        const { data  } = req.body;
        const result = await impresionesService.printOrdenAnulados(data.data, data.printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/print/factura-electronica', async (req, res) => {
    try {
        const { data  } = req.body;
        const result = await impresionesService.printFacturaElectronica(data, data.printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/print/abrir-cajon', async (req, res) => {
    try {
        const { printerIp } = req.body;
        const result = await impresionesService.aperturarCajon(printerIp);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.get('/printer/status/:ip', async (req, res) => {
    try {
        const { ip } = req.params;
        const printer = await impresionesService.createPrinterConnection(ip);
        const isConnected = await printer.isPrinterConnected();

        res.json({
            success: true,
            connected: isConnected,
            ip: ip
        });

    } catch (error) {
        res.json({
            success: false,
            connected: false,
            message: error.message
        });
    }
});

app.listen(PORT, () => {
    console.log(`Print Server corriendo en http://localhost:${PORT}`);
});