#!/usr/bin/python
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation; either version 3, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License
# for more details.

"Módulo para manejo de archivos JSON"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "LGPL-3.0-or-later"


try:
    import json
except ImportError:
    try:
        import simplejson as json
    except Exception:
        print("para soporte de JSON debe instalar simplejson")


def leer(fn="entrada.json"):
    "Analiza un archivo JSON y devuelve un diccionario (confia en que el json este ok)"
    jsonfile = open(fn, "rb")
    regs = json.load(jsonfile)
    return regs


def escribir(filas, fn="salida.json", **kwargs):
    "Dado una lista de comprobantes (diccionarios), escribe JSON"
    import codecs

    jsonfile = codecs.open(fn, "w")
    json.dump(
        filas,
        jsonfile,
        sort_keys=True,
        indent=4,
        **kwargs
    )
    jsonfile.close()
