"""pyafipws — Interfases para webservices de ARCA/AFIP.

Estructura de subpaquetes:
    pyafipws.facturacion   — Factura electrónica (WSFEv1, WSFEXv1, WSBFEv1, WSMTX, etc.)
    pyafipws.agricultura   — Granos, ganadería, tabaco, leche (WSCTG, WSLPG, WSLSP, etc.)
    pyafipws.trazabilidad  — Medicamentos, fitosanitarios, precursores (TrazaMed, etc.)
    pyafipws.remitos       — Remitos electrónicos (WSRemCarne, WSRemHarina, WSCPE, etc.)
    pyafipws.padron        — Padrón de contribuyentes (WS_SR_Padron, SIRED)
    pyafipws.provincial    — Servicios provinciales (COT, IIBB, RG3685)
    pyafipws.pdf           — Generación de PDF, QR y código de barras
    pyafipws.cli           — Interfaces CLI (rece1, receb1, recem, recet, recex1)
    pyafipws.formatos      — Parsers de formatos (CSV, TXT, XML, JSON, DBF, SQL)
"""

__author__ = "Mariano Reingart (mariano@gmail.com)"
__copyright__ = "Copyright (C) 2008-2021 Mariano Reingart"
__license__ = "LGPL-3.0-or-later"
__version__ = "3.28.0"

# Re-exports para retrocompatibilidad con imports legacy:
#   from pyafipws import wsfev1
#   from pyafipws.wsfev1 import WSFEv1
# Usamos lazy imports para evitar circular imports (cli/*.py importa from pyafipws).

import importlib as _importlib

_SUBMODULES = {
    # facturacion
    "wsfev1": "pyafipws.facturacion.wsfev1",
    "wsfexv1": "pyafipws.facturacion.wsfexv1",
    "wsbfev1": "pyafipws.facturacion.wsbfev1",
    "wsmtx": "pyafipws.facturacion.wsmtx",
    "wsct": "pyafipws.facturacion.wsct",
    "wscdc": "pyafipws.facturacion.wscdc",
    "wscoc": "pyafipws.facturacion.wscoc",
    "wsfecred": "pyafipws.facturacion.wsfecred",
    "wdigdepfiel": "pyafipws.facturacion.wdigdepfiel",
    "ws_sire": "pyafipws.facturacion.ws_sire",
    # agricultura
    "wsctg": "pyafipws.agricultura.wsctg",
    "wslpg": "pyafipws.agricultura.wslpg",
    "wslpg_datos": "pyafipws.agricultura.wslpg_datos",
    "wslsp": "pyafipws.agricultura.wslsp",
    "wsltv": "pyafipws.agricultura.wsltv",
    "wslum": "pyafipws.agricultura.wslum",
    # trazabilidad
    "trazamed": "pyafipws.trazabilidad.trazamed",
    "trazafito": "pyafipws.trazabilidad.trazafito",
    "trazaprodmed": "pyafipws.trazabilidad.trazaprodmed",
    "trazarenpre": "pyafipws.trazabilidad.trazarenpre",
    "trazavet": "pyafipws.trazabilidad.trazavet",
    # remitos
    "wsremcarne": "pyafipws.remitos.wsremcarne",
    "wsremharina": "pyafipws.remitos.wsremharina",
    "wsremazucar": "pyafipws.remitos.wsremazucar",
    "wscpe": "pyafipws.remitos.wscpe",
    "wscpe_cli": "pyafipws.remitos.wscpe_cli",
    # padron
    "padron": "pyafipws.padron.padron",
    "ws_sr_padron": "pyafipws.padron.ws_sr_padron",
    "sired": "pyafipws.padron.sired",
    # provincial
    "cot": "pyafipws.provincial.cot",
    "iibb": "pyafipws.provincial.iibb",
    "rg3685": "pyafipws.provincial.rg3685",
    # pdf
    "pyfepdf": "pyafipws.pdf.pyfepdf",
    "pyqr": "pyafipws.pdf.pyqr",
    "pyi25": "pyafipws.pdf.pyi25",
    "pyemail": "pyafipws.pdf.pyemail",
    # cli
    "rece1": "pyafipws.cli.rece1",
    "receb1": "pyafipws.cli.receb1",
    "recem": "pyafipws.cli.recem",
    "recet": "pyafipws.cli.recet",
    "recex1": "pyafipws.cli.recex1",
}


def __getattr__(name):
    if name in _SUBMODULES:
        return _importlib.import_module(_SUBMODULES[name])
    raise AttributeError(f"module 'pyafipws' has no attribute {name!r}")
