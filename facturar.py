#!/usr/bin/env python3
"""
Facturación Electrónica - Monotributo (Factura C / NC C / Factura E / NC E).

Mercado interno (WSFEv1):
    python facturar.py factura --monto ... --cliente ... --descripcion ... \
        --desde YYYYMMDD --hasta YYYYMMDD --produccion
    python facturar.py nota-credito --factura-asociada N ...

Exportación de servicios (WSFEXv1):
    python facturar.py factura-e --monto ... --cliente "Acme Inc" \
        --cuit-pais-cliente 50000000059 --descripcion "Software services" \
        --pais-destino 212 --moneda DOL --tipo-cambio 1180.50 \
        --incoterms N/A --idioma 7 --produccion
    python facturar.py nota-credito-e --factura-asociada N ...

Otros:
    python facturar.py listar
    python facturar.py consultar --numero 1
"""

import argparse
import datetime
import json
import os
import sys

from pysimplesoap.client import SoapFault

from pyafipws.facturacion.wsfev1 import WSFEv1
from pyafipws.facturacion.wsfexv1 import WSFEXv1
from pyafipws.pdf.pyfepdf import FEPDF
from pyafipws.wsaa import WSAA

# =============================================================================
# CONFIGURACIÓN — Se lee de .env (copiar .env.example y completar con tus datos)
# =============================================================================

def _load_env():
    """Cargar variables de .env si existe."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

_load_env()

CUIT = int(os.environ.get("CUIT", "0"))
CERT = os.environ.get("CERT", "mi_certificado.crt")
PRIVATEKEY = os.environ.get("PRIVATEKEY", "mi_clave.key")
CACHE = "./cache"

CONF_PDF = {
    "EMPRESA": os.environ.get("EMPRESA", ""),
    "MEMBRETE1": os.environ.get("MEMBRETE1", ""),
    "MEMBRETE2": os.environ.get("MEMBRETE2", ""),
    "CUIT": os.environ.get("CUIT_FMT", ""),
    "IIBB": os.environ.get("IIBB", "Exento"),
    "IVA": os.environ.get("IVA", "Responsable Monotributo"),
    "INICIO": os.environ.get("INICIO", ""),
}

# URLs de AFIP/ARCA
URLS = {
    "homo": {
        "wsaa": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl",
        "wsfev1": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
        "wsfexv1": "https://wswhomo.afip.gov.ar/wsfexv1/service.asmx?WSDL",
    },
    "prod": {
        "wsaa": "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl",
        "wsfev1": "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
        "wsfexv1": "https://servicios1.afip.gov.ar/wsfexv1/service.asmx?WSDL",
    },
}

# Tipos de comprobante
FACTURA_C = 11
NOTA_CREDITO_C = 13
FACTURA_E = 19          # Factura E (exportación de servicios)
NOTA_CREDITO_E = 21     # Nota de crédito E (exportación de servicios)
CONCEPTO = 2  # Servicios

# Directorio de facturas y registro
FACTURAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facturas")
REGISTRO_PATH = os.path.join(FACTURAS_DIR, "registro.json")


def autenticar(produccion=False, servicio="wsfe"):
    """Autenticarse contra WSAA y conectar al webservice elegido.

    servicio: "wsfe" para mercado interno (Factura C / NC C) o
              "wsfex" para exportación (Factura E / NC E).
    """
    env = "prod" if produccion else "homo"
    url_wsaa = URLS[env]["wsaa"]

    if servicio == "wsfex":
        url_ws = URLS[env]["wsfexv1"]
        cliente_cls = WSFEXv1
    else:
        url_ws = URLS[env]["wsfev1"]
        cliente_cls = WSFEv1

    wsaa = WSAA()
    try:
        ta = wsaa.Autenticar(servicio, CERT, PRIVATEKEY, wsdl=url_wsaa, cache=CACHE)
    except SoapFault as e:
        codigo = str(e.faultcode)
        if "coe.notAuthorized" in codigo:
            nombre_servicio = (
                "Factura electronica de exportacion" if servicio == "wsfex"
                else "Facturación Electrónica"
            )
            print(f"\nERROR: El Computador Fiscal no está autorizado a usar '{nombre_servicio}'.")
            print("\nPara habilitarlo:")
            print("  1. Entrá a ARCA → 'Administrador de Relaciones de Clave Fiscal'")
            print(f"  2. Nueva Relación → buscá '{nombre_servicio}'")
            print("  3. Asociala al Computador Fiscal que ya usás (ej. 'facturacion')")
            sys.exit(1)
        if "cms.cert.untrusted" in codigo:
            print(f"\nERROR: El certificado no es válido para el ambiente '{env}'.")
            print("  - Los certificados de producción NO funcionan contra homologación.")
            print("  - Para homologación necesitás generar un certificado distinto en wsaahomo.")
            sys.exit(1)
        raise
    if not ta:
        print("ERROR: No se pudo autenticar contra WSAA")
        print(f"  Verificar que existan {CERT} y {PRIVATEKEY}")
        sys.exit(1)

    ws = cliente_cls()
    ws.Cuit = CUIT
    ws.SetTicketAcceso(ta)
    ws.Conectar(CACHE, url_ws)

    ws.Dummy()
    print(f"Conexión AFIP ({env}): App={ws.AppServerStatus} "
          f"DB={ws.DbServerStatus} Auth={ws.AuthServerStatus}")

    return ws


def cargar_registro():
    """Cargar registro local de comprobantes emitidos."""
    if os.path.exists(REGISTRO_PATH):
        with open(REGISTRO_PATH) as f:
            return json.load(f)
    return []


def guardar_registro(registro):
    """Guardar registro local de comprobantes emitidos."""
    os.makedirs(FACTURAS_DIR, exist_ok=True)
    with open(REGISTRO_PATH, "w") as f:
        json.dump(registro, f, indent=2, ensure_ascii=False)


def emitir_comprobante(wsfev1, tipo_cbte, monto, cliente, descripcion,
                       desde, hasta, tipo_doc=99, nro_doc=0, punto_vta=3,
                       factura_asociada=None):
    """Emitir un comprobante (factura o nota de crédito)."""
    ultimo = wsfev1.CompUltimoAutorizado(tipo_cbte, punto_vta)
    cbte_nro = int(ultimo) + 1

    hoy = datetime.date.today().strftime("%Y%m%d")
    fecha_venc = datetime.datetime.strptime(hasta, "%Y%m%d") + datetime.timedelta(days=10)
    fecha_venc_pago = fecha_venc.strftime("%Y%m%d")

    nombre_tipo = "Nota de Crédito C" if tipo_cbte == NOTA_CREDITO_C else "Factura C"
    print(f"\nEmitiendo {nombre_tipo} #{cbte_nro:08d}...")
    print(f"  Cliente: {cliente}")
    print(f"  Monto: ${monto:,.2f}")
    print(f"  Período: {desde} - {hasta}")

    wsfev1.CrearFactura(
        concepto=CONCEPTO,
        tipo_doc=tipo_doc,
        nro_doc=nro_doc,
        tipo_cbte=tipo_cbte,
        punto_vta=punto_vta,
        cbt_desde=cbte_nro,
        cbt_hasta=cbte_nro,
        imp_total=monto,
        imp_tot_conc=0.00,
        imp_neto=monto,
        imp_iva=0.00,
        imp_trib=0.00,
        imp_op_ex=0.00,
        fecha_cbte=hoy,
        fecha_serv_desde=desde,
        fecha_serv_hasta=hasta,
        fecha_venc_pago=fecha_venc_pago,
        moneda_id="PES",
        moneda_ctz="1.000",
    )

    # Para notas de crédito, asociar la factura original
    if tipo_cbte == NOTA_CREDITO_C and factura_asociada:
        wsfev1.AgregarCmpAsoc(
            tipo=FACTURA_C,
            pto_vta=punto_vta,
            nro=factura_asociada,
            cuit=CUIT,
            fecha=hoy,
        )
        print(f"  Asociada a FC {punto_vta:04d}-{factura_asociada:08d}")

    wsfev1.CAESolicitar()

    if wsfev1.ErrMsg:
        print(f"\nERROR AFIP: {wsfev1.ErrMsg}")
        sys.exit(1)

    if wsfev1.Obs:
        print(f"  Observaciones: {wsfev1.Obs}")

    if wsfev1.Resultado != "A":
        print(f"\nComprobante RECHAZADO (Resultado: {wsfev1.Resultado})")
        sys.exit(1)

    print(f"\n  {nombre_tipo} AUTORIZADA")
    print(f"  CAE: {wsfev1.CAE}")
    print(f"  Vencimiento CAE: {wsfev1.Vencimiento}")
    print(f"  Comprobante Nro: {cbte_nro}")

    resultado = {
        "tipo_cbte": tipo_cbte,
        "tipo_nombre": nombre_tipo,
        "cbte_nro": cbte_nro,
        "cae": wsfev1.CAE,
        "fch_venc_cae": wsfev1.Vencimiento,
        "fecha_cbte": hoy,
        "punto_vta": punto_vta,
        "monto": monto,
        "cliente": cliente,
        "descripcion": descripcion,
        "tipo_doc": tipo_doc,
        "nro_doc": nro_doc,
        "desde": desde,
        "hasta": hasta,
        "fecha_venc_pago": fecha_venc_pago,
        "factura_asociada": factura_asociada,
    }

    # Guardar en registro local
    registro = cargar_registro()
    registro.append(resultado)
    guardar_registro(registro)

    return resultado


def emitir_comprobante_e(wsfexv1, tipo_cbte, monto, cliente, cuit_pais_cliente,
                         descripcion, pais_destino, moneda="DOL", tipo_cambio=None,
                         incoterms="N/A", idioma=7, punto_vta=3,
                         domicilio_cliente="", id_impositivo="",
                         factura_asociada=None):
    """Emitir Factura E o Nota de Crédito E (exportación de servicios)."""
    # Cotización: si no se provee y la moneda no es PES, pedir la del día a ARCA
    if tipo_cambio is None:
        if moneda == "PES":
            tipo_cambio = 1.0
        else:
            ctz = wsfexv1.GetParamCtz(moneda)
            if not ctz:
                print(f"ERROR: No se pudo obtener cotización para moneda '{moneda}'")
                sys.exit(1)
            try:
                tipo_cambio = float(ctz)
            except (TypeError, ValueError):
                print(f"ERROR: Cotización inválida '{ctz}' para moneda '{moneda}'")
                sys.exit(1)
            print(f"  Cotización {moneda} (ARCA): {tipo_cambio}")

    ultimo_cbte = wsfexv1.GetLastCMP(tipo_cbte, punto_vta) or 0
    cbte_nro = int(ultimo_cbte) + 1

    ultimo_id = wsfexv1.GetLastID() or 0
    id_transaccion = int(ultimo_id) + 1

    hoy = datetime.date.today().strftime("%Y%m%d")

    nombre_tipo = "Nota de Crédito E" if tipo_cbte == NOTA_CREDITO_E else "Factura E"
    print(f"\nEmitiendo {nombre_tipo} #{cbte_nro:08d}...")
    print(f"  Cliente: {cliente}")
    print(f"  Monto: {monto:,.2f} {moneda}")
    print(f"  País destino (cód. ARCA): {pais_destino}")
    print(f"  INCOTERMS: {incoterms}")

    wsfexv1.CrearFactura(
        tipo_cbte=tipo_cbte,
        punto_vta=punto_vta,
        cbte_nro=cbte_nro,
        fecha_cbte=hoy,
        imp_total=monto,
        tipo_expo=1,                # 1 = exportación definitiva
        permiso_existente="N",      # servicios no llevan permiso de embarque
        pais_dst_cmp=pais_destino,
        nombre_cliente=cliente,
        cuit_pais_cliente=cuit_pais_cliente,
        domicilio_cliente=domicilio_cliente or "NO DECLARADO",
        id_impositivo=id_impositivo,
        moneda_id=moneda,
        moneda_ctz=tipo_cambio,
        incoterms=incoterms,
        incoterms_ds=incoterms if incoterms != "N/A" else "",
        idioma_cbte=idioma,
    )

    wsfexv1.AgregarItem(
        codigo="SRV",
        ds=descripcion,
        qty=1,
        umed=7,                      # 7 = unidad
        precio=monto,
        importe=monto,
    )

    if tipo_cbte == NOTA_CREDITO_E and factura_asociada:
        wsfexv1.AgregarCmpAsoc(
            cbte_tipo=FACTURA_E,
            cbte_punto_vta=punto_vta,
            cbte_nro=factura_asociada,
            cbte_cuit=CUIT,
        )
        print(f"  Asociada a FE {punto_vta:04d}-{factura_asociada:08d}")

    wsfexv1.Authorize(id_transaccion)
    cae = wsfexv1.CAE

    if wsfexv1.ErrMsg:
        print(f"\nERROR AFIP: {wsfexv1.ErrMsg}")
        sys.exit(1)

    if wsfexv1.Obs:
        print(f"  Observaciones: {wsfexv1.Obs}")

    if wsfexv1.Resultado != "A":
        print(f"\nComprobante RECHAZADO (Resultado: {wsfexv1.Resultado})")
        sys.exit(1)

    print(f"\n  {nombre_tipo} AUTORIZADA")
    print(f"  CAE: {cae}")
    print(f"  Vencimiento CAE: {wsfexv1.Vencimiento}")
    print(f"  Comprobante Nro: {cbte_nro}")

    resultado = {
        "tipo_cbte": tipo_cbte,
        "tipo_nombre": nombre_tipo,
        "cbte_nro": cbte_nro,
        "cae": cae,
        "fch_venc_cae": wsfexv1.FchVencCAE,
        "fecha_cbte": hoy,
        "punto_vta": punto_vta,
        "monto": monto,
        "cliente": cliente,
        "descripcion": descripcion,
        "tipo_doc": 80 if cuit_pais_cliente else 99,
        "nro_doc": cuit_pais_cliente,
        "pais_destino": pais_destino,
        "moneda": moneda,
        "tipo_cambio": tipo_cambio,
        "incoterms": incoterms,
        "idioma": idioma,
        "factura_asociada": factura_asociada,
    }

    registro = cargar_registro()
    registro.append(resultado)
    guardar_registro(registro)

    return resultado


def generar_pdf(comprobante, produccion=False):
    """Generar PDF del comprobante emitido."""
    fepdf = FEPDF()

    plantilla = os.path.join(os.path.dirname(__file__), "plantillas", "factura.csv")
    fepdf.CargarFormato(plantilla)
    fepdf.FmtCantidad = "0.2"
    fepdf.FmtPrecio = "0.2"
    fepdf.CUIT = CUIT

    for k, v in CONF_PDF.items():
        fepdf.AgregarDato(k, v)

    if not produccion:
        fepdf.AgregarCampo(
            "DEMO", "T", 120, 260, 0, 0,
            text="HOMOLOGACION", size=70, rotate=45,
            foreground=0x808080, priority=-1,
        )
        fepdf.AgregarDato("motivos_obs", "SIN VALIDEZ FISCAL - HOMOLOGACION")

    if comprobante["tipo_doc"] == 80:
        id_impositivo = "CUIT"
    elif comprobante["tipo_doc"] == 96:
        id_impositivo = "DNI"
    else:
        id_impositivo = "Consumidor Final"

    fepdf.CrearFactura(
        concepto=CONCEPTO,
        tipo_doc=comprobante["tipo_doc"],
        nro_doc=comprobante["nro_doc"],
        tipo_cbte=comprobante["tipo_cbte"],
        punto_vta=comprobante["punto_vta"],
        cbte_nro=comprobante["cbte_nro"],
        imp_total=comprobante["monto"],
        imp_tot_conc=0.00,
        imp_neto=comprobante["monto"],
        imp_iva=0.00,
        imp_trib=0.00,
        imp_op_ex=0.00,
        fecha_cbte=comprobante["fecha_cbte"],
        fecha_serv_desde=comprobante["desde"],
        fecha_serv_hasta=comprobante["hasta"],
        fecha_venc_pago=comprobante["fecha_venc_pago"],
        moneda_id="PES",
        moneda_ctz="1.000",
        cae=comprobante["cae"],
        fch_venc_cae=comprobante["fch_venc_cae"],
        id_impositivo=id_impositivo,
        nombre_cliente=comprobante["cliente"],
        domicilio_cliente="",
    )

    fepdf.AgregarDetalleItem(
        u_mtx=None, cod_mtx=None,
        codigo="SRV",
        ds=comprobante["descripcion"],
        qty=1, umed=7,
        precio=comprobante["monto"],
        bonif=0.00,
        iva_id=None, imp_iva=None,
        importe=comprobante["monto"],
        despacho="",
    )

    fepdf.CrearPlantilla(papel="A4", orientacion="portrait")
    fepdf.ProcesarPlantilla(num_copias=1, lineas_max=24, qty_pos="izq")

    os.makedirs(FACTURAS_DIR, exist_ok=True)
    prefijo = "NC" if comprobante["tipo_cbte"] == NOTA_CREDITO_C else "FC"
    archivo = os.path.join(
        FACTURAS_DIR,
        f"{prefijo}-{comprobante['punto_vta']:04d}-{comprobante['cbte_nro']:08d}.pdf"
    )
    fepdf.GenerarPDF(archivo=archivo)

    print(f"\n  PDF generado: {archivo}")
    return archivo


def generar_pdf_e(comprobante, produccion=False):
    """Generar PDF de un comprobante de exportación (Factura E / NC E)."""
    fepdf = FEPDF()

    plantilla = os.path.join(os.path.dirname(__file__), "plantillas", "factura_e.csv")
    fepdf.CargarFormato(plantilla)
    fepdf.FmtCantidad = "0.2"
    fepdf.FmtPrecio = "0.2"
    fepdf.CUIT = CUIT

    for k, v in CONF_PDF.items():
        fepdf.AgregarDato(k, v)

    # Datos específicos de exportación inyectados como campos libres
    fepdf.AgregarDato("PaisDestino", str(comprobante.get("pais_destino", "")))
    fepdf.AgregarDato("Moneda", comprobante.get("moneda", ""))
    fepdf.AgregarDato("Cotizacion", f"{comprobante.get('tipo_cambio', 1):.4f}")
    fepdf.AgregarDato("Incoterms", comprobante.get("incoterms", ""))

    if not produccion:
        fepdf.AgregarCampo(
            "DEMO", "T", 120, 260, 0, 0,
            text="HOMOLOGACION", size=70, rotate=45,
            foreground=0x808080, priority=-1,
        )
        fepdf.AgregarDato("motivos_obs", "SIN VALIDEZ FISCAL - HOMOLOGACION")

    fepdf.CrearFactura(
        concepto=CONCEPTO,
        tipo_doc=comprobante["tipo_doc"],
        nro_doc=comprobante["nro_doc"],
        tipo_cbte=comprobante["tipo_cbte"],
        punto_vta=comprobante["punto_vta"],
        cbte_nro=comprobante["cbte_nro"],
        imp_total=comprobante["monto"],
        imp_tot_conc=0.00,
        imp_neto=comprobante["monto"],
        imp_iva=0.00,
        imp_trib=0.00,
        imp_op_ex=0.00,
        fecha_cbte=comprobante["fecha_cbte"],
        moneda_id=comprobante.get("moneda", "DOL"),
        moneda_ctz=comprobante.get("tipo_cambio", 1.0),
        cae=comprobante["cae"],
        fch_venc_cae=comprobante["fch_venc_cae"],
        id_impositivo=str(comprobante.get("nro_doc") or "0"),
        nombre_cliente=comprobante["cliente"],
        domicilio_cliente="",
    )

    fepdf.AgregarDetalleItem(
        u_mtx=None, cod_mtx=None,
        codigo="SRV",
        ds=comprobante["descripcion"],
        qty=1, umed=7,
        precio=comprobante["monto"],
        bonif=0.00,
        iva_id=None, imp_iva=None,
        importe=comprobante["monto"],
        despacho="",
    )

    fepdf.CrearPlantilla(papel="A4", orientacion="portrait")
    fepdf.ProcesarPlantilla(num_copias=1, lineas_max=24, qty_pos="izq")

    os.makedirs(FACTURAS_DIR, exist_ok=True)
    prefijo = "NE" if comprobante["tipo_cbte"] == NOTA_CREDITO_E else "FE"
    archivo = os.path.join(
        FACTURAS_DIR,
        f"{prefijo}-{comprobante['punto_vta']:04d}-{comprobante['cbte_nro']:08d}.pdf"
    )
    fepdf.GenerarPDF(archivo=archivo)

    print(f"\n  PDF generado: {archivo}")
    return archivo


def cmd_factura(args):
    """Comando: emitir factura."""
    if args.cuit_cliente and args.tipo_doc == 99:
        args.tipo_doc = 80
    nro_doc = args.cuit_cliente if args.cuit_cliente else 0

    env = "PRODUCCIÓN" if args.produccion else "HOMOLOGACIÓN"
    print(f"=== Factura C ({env}) ===\n")

    wsfev1 = autenticar(args.produccion)
    comprobante = emitir_comprobante(
        wsfev1, FACTURA_C, args.monto, args.cliente, args.descripcion,
        args.desde, args.hasta, args.tipo_doc, nro_doc, args.punto_vta,
    )
    generar_pdf(comprobante, args.produccion)
    print("\nListo.")


def cmd_nota_credito(args):
    """Comando: emitir nota de crédito."""
    if args.cuit_cliente and args.tipo_doc == 99:
        args.tipo_doc = 80
    nro_doc = args.cuit_cliente if args.cuit_cliente else 0

    env = "PRODUCCIÓN" if args.produccion else "HOMOLOGACIÓN"
    print(f"=== Nota de Crédito C ({env}) ===\n")

    wsfev1 = autenticar(args.produccion)
    comprobante = emitir_comprobante(
        wsfev1, NOTA_CREDITO_C, args.monto, args.cliente, args.descripcion,
        args.desde, args.hasta, args.tipo_doc, nro_doc, args.punto_vta,
        factura_asociada=args.factura_asociada,
    )
    generar_pdf(comprobante, args.produccion)
    print("\nListo.")


def cmd_factura_e(args):
    """Comando: emitir Factura E (exportación de servicios)."""
    env = "PRODUCCIÓN" if args.produccion else "HOMOLOGACIÓN"
    print(f"=== Factura E ({env}) ===\n")

    wsfexv1 = autenticar(args.produccion, servicio="wsfex")
    comprobante = emitir_comprobante_e(
        wsfexv1, FACTURA_E, args.monto, args.cliente,
        args.cuit_pais_cliente or "",
        args.descripcion, args.pais_destino,
        moneda=args.moneda, tipo_cambio=args.tipo_cambio,
        incoterms=args.incoterms, idioma=args.idioma,
        punto_vta=args.punto_vta,
    )
    generar_pdf_e(comprobante, args.produccion)
    print("\nListo.")


def cmd_nc_e(args):
    """Comando: emitir Nota de Crédito E (exportación)."""
    env = "PRODUCCIÓN" if args.produccion else "HOMOLOGACIÓN"
    print(f"=== Nota de Crédito E ({env}) ===\n")

    wsfexv1 = autenticar(args.produccion, servicio="wsfex")
    comprobante = emitir_comprobante_e(
        wsfexv1, NOTA_CREDITO_E, args.monto, args.cliente,
        args.cuit_pais_cliente or "",
        args.descripcion, args.pais_destino,
        moneda=args.moneda, tipo_cambio=args.tipo_cambio,
        incoterms=args.incoterms, idioma=args.idioma,
        punto_vta=args.punto_vta,
        factura_asociada=args.factura_asociada,
    )
    generar_pdf_e(comprobante, args.produccion)
    print("\nListo.")


def cmd_listar(args):
    """Comando: listar comprobantes emitidos."""
    registro = cargar_registro()
    if not registro:
        print("No hay comprobantes registrados.")
        return

    print(f"{'Tipo':<20} {'Número':<18} {'Fecha':<12} {'Cliente':<25} {'Monto':>12} {'CAE':<16}")
    print("-" * 105)
    for c in registro:
        pto = c["punto_vta"]
        nro = c["cbte_nro"]
        numero = f"{pto:04d}-{nro:08d}"
        print(f"{c['tipo_nombre']:<20} {numero:<18} {c['fecha_cbte']:<12} "
              f"{c['cliente'][:25]:<25} ${c['monto']:>11,.2f} {c['cae']:<16}")


def cmd_consultar(args):
    """Comando: consultar comprobante en AFIP."""
    env = "PRODUCCIÓN" if args.produccion else "HOMOLOGACIÓN"
    print(f"=== Consulta de Comprobante ({env}) ===\n")

    wsfev1 = autenticar(args.produccion)
    tipo_cbte = NOTA_CREDITO_C if args.nota_credito else FACTURA_C
    nombre = "Nota de Crédito C" if args.nota_credito else "Factura C"

    wsfev1.CompConsultar(tipo_cbte, args.punto_vta, args.numero)

    print(f"\n  {nombre} {args.punto_vta:04d}-{args.numero:08d}")
    print(f"  CAE: {wsfev1.CAE}")
    print(f"  Fecha: {wsfev1.FechaCbte}")
    print(f"  Total: ${float(wsfev1.ImpTotal):,.2f}")
    print(f"  Resultado: {wsfev1.Resultado}")
    if wsfev1.Obs:
        print(f"  Observaciones: {wsfev1.Obs}")


def main():
    parser = argparse.ArgumentParser(
        description="Facturación Electrónica - Monotributo (Factura C / NC C / Factura E / NC E)"
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    # --- Subcomando: factura ---
    p_fac = subparsers.add_parser("factura", help="Emitir Factura C")
    p_fac.add_argument("--monto", type=float, required=True)
    p_fac.add_argument("--cliente", required=True)
    p_fac.add_argument("--descripcion", required=True)
    p_fac.add_argument("--desde", required=True, help="YYYYMMDD")
    p_fac.add_argument("--hasta", required=True, help="YYYYMMDD")
    p_fac.add_argument("--cuit-cliente", type=int, default=0)
    p_fac.add_argument("--tipo-doc", type=int, default=99, choices=[80, 86, 96, 99])
    p_fac.add_argument("--punto-vta", type=int, default=3)
    p_fac.add_argument("--produccion", action="store_true")
    p_fac.set_defaults(func=cmd_factura)

    # --- Subcomando: nota-credito ---
    p_nc = subparsers.add_parser("nota-credito", help="Emitir Nota de Crédito C")
    p_nc.add_argument("--monto", type=float, required=True)
    p_nc.add_argument("--cliente", required=True)
    p_nc.add_argument("--descripcion", required=True)
    p_nc.add_argument("--desde", required=True, help="YYYYMMDD")
    p_nc.add_argument("--hasta", required=True, help="YYYYMMDD")
    p_nc.add_argument("--factura-asociada", type=int, required=True,
                      help="Número de la factura a anular/ajustar")
    p_nc.add_argument("--cuit-cliente", type=int, default=0)
    p_nc.add_argument("--tipo-doc", type=int, default=99, choices=[80, 86, 96, 99])
    p_nc.add_argument("--punto-vta", type=int, default=3)
    p_nc.add_argument("--produccion", action="store_true")
    p_nc.set_defaults(func=cmd_nota_credito)

    # --- Subcomando: factura-e (exportación) ---
    p_fe = subparsers.add_parser("factura-e", help="Emitir Factura E (exportación)")
    p_fe.add_argument("--monto", type=float, required=True)
    p_fe.add_argument("--cliente", required=True)
    p_fe.add_argument("--descripcion", required=True)
    p_fe.add_argument("--pais-destino", type=int, required=True,
                      help="Código de país ARCA (ej. 212=USA, 203=BR, 426=UK, 438=DE)")
    p_fe.add_argument("--cuit-pais-cliente", default="",
                      help="Tax ID del cliente en el exterior (opcional)")
    p_fe.add_argument("--moneda", default="DOL", help="Default: DOL (USD)")
    p_fe.add_argument("--tipo-cambio", type=float, default=None,
                      help="Cotización; si falta y moneda != PES, se consulta a ARCA")
    p_fe.add_argument("--incoterms", default="N/A",
                      help="Default: N/A (servicios). Otros: FOB, CIF, etc.")
    p_fe.add_argument("--idioma", type=int, default=7,
                      help="7=español (default), 1=inglés, 2=portugués")
    p_fe.add_argument("--punto-vta", type=int, default=3)
    p_fe.add_argument("--produccion", action="store_true")
    p_fe.set_defaults(func=cmd_factura_e)

    # --- Subcomando: nota-credito-e (exportación) ---
    p_nce = subparsers.add_parser("nota-credito-e", help="Emitir Nota de Crédito E (exportación)")
    p_nce.add_argument("--monto", type=float, required=True)
    p_nce.add_argument("--cliente", required=True)
    p_nce.add_argument("--descripcion", required=True)
    p_nce.add_argument("--pais-destino", type=int, required=True)
    p_nce.add_argument("--factura-asociada", type=int, required=True,
                       help="Número de la Factura E a anular/ajustar")
    p_nce.add_argument("--cuit-pais-cliente", default="")
    p_nce.add_argument("--moneda", default="DOL")
    p_nce.add_argument("--tipo-cambio", type=float, default=None)
    p_nce.add_argument("--incoterms", default="N/A")
    p_nce.add_argument("--idioma", type=int, default=7)
    p_nce.add_argument("--punto-vta", type=int, default=3)
    p_nce.add_argument("--produccion", action="store_true")
    p_nce.set_defaults(func=cmd_nc_e)

    # --- Subcomando: listar ---
    p_list = subparsers.add_parser("listar", help="Listar comprobantes emitidos")
    p_list.set_defaults(func=cmd_listar)

    # --- Subcomando: consultar ---
    p_con = subparsers.add_parser("consultar", help="Consultar comprobante en AFIP")
    p_con.add_argument("--numero", type=int, required=True, help="Número de comprobante")
    p_con.add_argument("--nota-credito", action="store_true", help="Consultar NC en vez de FC")
    p_con.add_argument("--punto-vta", type=int, default=3)
    p_con.add_argument("--produccion", action="store_true")
    p_con.set_defaults(func=cmd_consultar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
