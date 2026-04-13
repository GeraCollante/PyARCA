#!/usr/bin/env python3
"""
Facturación Electrónica - Factura C (Monotributo)
Emite facturas y notas de crédito por servicios de desarrollo de software via AFIP/ARCA.

Uso:
    python facturar.py factura \
        --monto 50000 \
        --cliente "Empresa SRL" \
        --descripcion "Desarrollo de software - Marzo 2026" \
        --desde 20260301 --hasta 20260331 --produccion

    python facturar.py nota-credito \
        --monto 50000 \
        --cliente "Empresa SRL" \
        --descripcion "Anulación FC 0003-00000001" \
        --factura-asociada 1 \
        --produccion

    python facturar.py listar
    python facturar.py consultar --numero 1
"""

import argparse
import datetime
import json
import os
import sys

from pyafipws.facturacion.wsfev1 import WSFEv1
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
    },
    "prod": {
        "wsaa": "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl",
        "wsfev1": "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
    },
}

# Tipos de comprobante
FACTURA_C = 11
NOTA_CREDITO_C = 13
CONCEPTO = 2  # Servicios

# Directorio de facturas y registro
FACTURAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facturas")
REGISTRO_PATH = os.path.join(FACTURAS_DIR, "registro.json")


def autenticar(produccion=False):
    """Autenticarse contra WSAA y conectar a WSFEv1."""
    env = "prod" if produccion else "homo"
    url_wsaa = URLS[env]["wsaa"]
    url_wsfev1 = URLS[env]["wsfev1"]

    wsaa = WSAA()
    ta = wsaa.Autenticar("wsfe", CERT, PRIVATEKEY, wsdl=url_wsaa, cache=CACHE)
    if not ta:
        print("ERROR: No se pudo autenticar contra WSAA")
        print(f"  Verificar que existan {CERT} y {PRIVATEKEY}")
        sys.exit(1)

    wsfev1 = WSFEv1()
    wsfev1.Cuit = CUIT
    wsfev1.SetTicketAcceso(ta)
    wsfev1.Conectar(CACHE, url_wsfev1)

    wsfev1.Dummy()
    print(f"Conexión AFIP ({env}): App={wsfev1.AppServerStatus} "
          f"DB={wsfev1.DbServerStatus} Auth={wsfev1.AuthServerStatus}")

    return wsfev1


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
        description="Facturación Electrónica - Monotributo (Factura C)"
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
