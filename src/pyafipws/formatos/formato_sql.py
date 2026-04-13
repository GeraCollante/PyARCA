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

"Módulo para manejo de archivos SQL"

from builtins import str

from past.builtins import basestring
from past.utils import old_div

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2014 Mariano Reingart"
__license__ = "LGPL-3.0-or-later"

from decimal import Decimal

DEBUG = False
CHARSET = "utf-8"
CAE_NULL = None
FECHA_VTO_NULL = None
RESULTADO_NULL = None
NULL = None


def esquema_sql(tipos_registro, conf=None):
    if conf is None:
        conf = {}
    from formato_txt import IMPORTE, A, N

    for tabla, formato in tipos_registro:
        sql = []
        sql.append(f"CREATE TABLE {tabla} (")
        if tabla != "encabezado":
            # agrego id como fk
            id = [("id", 15, N)]
        else:
            id = []
        for (clave, longitud, tipo) in id + formato:
            clave_orig = clave
            if conf:
                if tabla == "encabezado":
                    clave = conf["encabezado"].get(clave, clave)
                if tabla == "detalle":
                    clave = conf["detalle"].get(clave, clave)
                if tabla == "iva":
                    clave = conf["iva"].get(clave, clave)
                if tabla == "tributo":
                    clave = conf["tributo"].get(clave, clave)
                if tabla == "cmp_asoc":
                    clave = conf["cmp_asoc"].get(clave, clave)
                if tabla == "permiso":
                    clave = conf["permiso"].get(clave, clave)
            if isinstance(longitud, (tuple, list)):
                longitud, decimales = longitud
            else:
                decimales = 2
            sql.append(
                "    {} {} {}{}{}".format(
                    clave,
                    {N: "INTEGER", IMPORTE: "NUMERIC", A: "VARCHAR"}[tipo],
                    {
                        IMPORTE: f"({longitud}, {decimales})",
                        A: f"({longitud})",
                        N: "",
                    }[tipo],
                    clave == "id"
                    and (
                        tabla == "encabezado"
                        and " PRIMARY KEY"
                        or " FOREING KEY encabezado"
                    )
                    or "",
                    formato[-1][0] != clave_orig and "," or "",
                )
            )
        sql.append(")")
        sql.append(";")
        if DEBUG:
            print("\n".join(sql))
        yield "\n".join(sql)


def configurar(schema):
    tablas = {}
    campos = {}
    campos_rev = {}
    if not schema:
        for tabla in "encabezado", "detalle", "cmp_asoc", "permiso", "tributo", "iva":
            tablas[tabla] = tabla
            campos[tabla] = {"id": "id"}
            campos_rev[tabla] = dict([(v, k) for k, v in list(campos[tabla].items())])
    return tablas, campos, campos_rev


def ejecutar(cur, sql, params=None):
    ##print sql, params
    if params is None:
        return cur.execute(sql)
    else:
        return cur.execute(sql, params)


def max_id(db, schema=None):
    if schema is None:
        schema = {}
    cur = db.cursor()
    tablas, campos, campos_rev = configurar(schema)
    query = ("SELECT MAX(%(id)s) FROM {encabezado}".format(**tablas)) % campos["encabezado"]
    if DEBUG:
        print("ejecutando", query)
    ret = None
    try:
        ejecutar(cur, query)
        for row in cur:
            ret = row[0]
        if not ret:
            ret = 0
        ##print "MAX_ID = ", ret
        return ret
    finally:
        cur.close()


def redondear(formato, clave, valor):
    # corregir redondeo (aparentemente sqlite no guarda correctamente los decimal)
    import decimal

    from formato_txt import A, N

    try:
        [fmt[1] for fmt in formato if fmt[0] == clave]
        tipo = [fmt[2] for fmt in formato if fmt[0] == clave]
        if not tipo:
            return valor
        tipo = tipo[0]
        if DEBUG:
            print("tipo", tipo, clave, valor, int)
        if valor is None:
            return None
        if valor == "":
            return ""
        if tipo == A:
            return valor
        if tipo == N:
            return int(valor)
        if isinstance(valor, (int, float)):
            valor = str(valor)
        if isinstance(valor, basestring):
            valor = Decimal(valor)
        if int and isinstance(int[0], (tuple, list)):
            decimales = old_div(Decimal("1"), Decimal(10 ** (int[0][1])))
        else:
            decimales = Decimal(".01")
        valor1 = valor.quantize(decimales, rounding=decimal.ROUND_DOWN)
        if valor != valor1 and DEBUG:
            print("REDONDEANDO ", clave, decimales, valor, valor1)
        return valor1
    except Exception as e:
        print("IMPOSIBLE REDONDEAR:", clave, valor, e)


def escribir(facts, db, schema=None, commit=True):
    if schema is None:
        schema = {}
    from formato_txt import CMP_ASOC, DETALLE, ENCABEZADO, IVA, PERMISO, TRIBUTO

    tablas, campos, campos_rev = configurar(schema)
    cur = db.cursor()
    try:
        for dic in facts:
            if "id" not in dic:
                dic["id"] = max_id(db, schema={}) + 1
            query = "INSERT INTO {encabezado} (%s) VALUES (%s)".format(**tablas)
            fields = ",".join(
                [campos["encabezado"].get(k, k) for k, t, n in ENCABEZADO if k in dic]
            )
            values = ",".join(["?" for k, t, n in ENCABEZADO if k in dic])
            if DEBUG:
                print(
                    f"Ejecutando2: {query % (fields, values)} {[dic[k] for k, t, n in ENCABEZADO if k in dic]}"
                )
            ejecutar(
                cur,
                query % (fields, values),
                [dic[k] for k, t, n in ENCABEZADO if k in dic],
            )
            query = (
                "INSERT INTO {detalle} (%(id)s, %%s) VALUES (?, %%s)".format(**tablas)
            ) % campos["detalle"]
            for item in dic["detalles"]:
                fields = ",".join(
                    [campos["detalle"].get(k, k) for k, t, n in DETALLE if k in item]
                )
                values = ",".join(["?" for k, t, n in DETALLE if k in item])
                if DEBUG:
                    print(
                        "Ejecutando: {} {}".format(
                            query % (fields, values),
                            [dic["id"]] + [item[k] for k, t, n in DETALLE if k in item],
                        )
                    )
                ejecutar(
                    cur,
                    query % (fields, values),
                    [dic["id"]] + [item[k] for k, t, n in DETALLE if k in item],
                )
            if "cbtes_asoc" in dic and tablas["cmp_asoc"]:
                query = (
                    "INSERT INTO {cmp_asoc} (%(id)s, %%s) VALUES (?, %%s)".format(**tablas)
                ) % campos["cmp_asoc"]
                for item in dic["cbtes_asoc"]:
                    fields = ",".join(
                        [
                            campos["cmp_asoc"].get(k, k)
                            for k, t, n in CMP_ASOC
                            if k in item
                        ]
                    )
                    values = ",".join(["?" for k, t, n in CMP_ASOC if k in item])
                    if DEBUG:
                        print(
                            "Ejecutando: {} {}".format(
                                query % (fields, values),
                                [dic["id"]]
                                + [item[k] for k, t, n in CMP_ASOC if k in item],
                            )
                        )
                    ejecutar(
                        cur,
                        query % (fields, values),
                        [dic["id"]] + [item[k] for k, t, n in CMP_ASOC if k in item],
                    )
            if "permisos" in dic:
                query = (
                    "INSERT INTO {permiso} (%(id)s, %%s) VALUES (?, %%s)".format(**tablas)
                ) % campos["permiso"]
                for item in dic["permisos"]:
                    fields = ",".join(
                        [
                            campos["permiso"].get(k, k)
                            for k, t, n in PERMISO
                            if k in item
                        ]
                    )
                    values = ",".join(["?" for k, t, n in PERMISO if k in item])
                    if DEBUG:
                        print(
                            "Ejecutando: {} {}".format(
                                query % (fields, values),
                                [dic["id"]]
                                + [item[k] for k, t, n in PERMISO if k in item],
                            )
                        )
                    ejecutar(
                        cur,
                        query % (fields, values),
                        [dic["id"]] + [item[k] for k, t, n in PERMISO if k in item],
                    )
            if "tributos" in dic:
                query = (
                    "INSERT INTO {tributo} (%(id)s, %%s) VALUES (?, %%s)".format(**tablas)
                ) % campos["tributo"]
                for item in dic["tributos"]:
                    fields = ",".join(
                        [
                            campos["tributo"].get(k, k)
                            for k, t, n in TRIBUTO
                            if k in item
                        ]
                    )
                    values = ",".join(["?" for k, t, n in TRIBUTO if k in item])
                    if DEBUG:
                        print(
                            "Ejecutando: {} {}".format(
                                query % (fields, values),
                                [dic["id"]]
                                + [item[k] for k, t, n in TRIBUTO if k in item],
                            )
                        )
                    ejecutar(
                        cur,
                        query % (fields, values),
                        [dic["id"]] + [item[k] for k, t, n in TRIBUTO if k in item],
                    )
            if "ivas" in dic:
                query = (
                    "INSERT INTO {iva} (%(id)s, %%s) VALUES (?, %%s)".format(**tablas)
                ) % campos["iva"]
                for item in dic["ivas"]:
                    fields = ",".join(
                        [campos["iva"].get(k, k) for k, t, n in IVA if k in item]
                    )
                    values = ",".join(["?" for k, t, n in IVA if k in item])
                    if DEBUG:
                        print(
                            "Ejecutando: {} {}".format(
                                query % (fields, values),
                                [dic["id"]] + [item[k] for k, t, n in IVA if k in item],
                            )
                        )
                    ejecutar(
                        cur,
                        query % (fields, values),
                        [dic["id"]] + [item[k] for k, t, n in IVA if k in item],
                    )
        if commit:
            db.commit()
    finally:
        pass


def modificar(fact, db, schema=None, webservice="wsfev1", ids=None, conf_db=None):
    if schema is None:
        schema = {}
    if conf_db is None:
        conf_db = {}
    from formato_txt import ENCABEZADO

    update = [
        "cae",
        "fecha_vto",
        "resultado",
        "reproceso",
        "motivo_obs",
        "err_code",
        "err_msg",
        "cbte_nro",
    ]
    tablas, campos, campos_rev = configurar(schema)
    cur = db.cursor()
    if fact["cae"] == "NULL" or fact["cae"] == "" or fact["cae"] is None:
        fact["cae"] = CAE_NULL
        fact["fecha_vto"] = FECHA_VTO_NULL
    if "null" in conf_db and fact["resultado"] is None or fact["resultado"] == "":
        fact["resultado"] = RESULTADO_NULL
    for k in ["reproceso", "motivo_obs", "err_code", "err_msg"]:
        if "null" in conf_db and k in fact and fact[k] is None or fact[k] == "":
            if DEBUG:
                print(k, "NULL")
            fact[k] = NULL
    try:
        query = ("UPDATE {encabezado} SET %%s WHERE %(id)s=?".format(**tablas)) % campos[
            "encabezado"
        ]
        fields = [
            campos["encabezado"].get(k, k)
            for k, t, n in ENCABEZADO
            if k in update and k in fact
        ]
        values = [fact[k] for k, t, n in ENCABEZADO if k in update and k in fact]
        query = query % ",".join([f"{f}=?" for f in fields])
        if DEBUG:
            print(query, values + [fact["id"]])
        ejecutar(cur, query, values + [fact["id"]])
        db.commit()
    except Exception:
        raise
    finally:
        pass


def leer(db, schema=None, webservice="wsfev1", ids=None, **kwargs):
    if schema is None:
        schema = {}
    from formato_txt import DETALLE, ENCABEZADO, IVA, TRIBUTO

    tablas, campos, campos_rev = configurar(schema)
    cur = db.cursor()
    if kwargs:
        query = "SELECT * FROM {encabezado}".format(**tablas)
    elif not ids:
        query = (
            "SELECT * FROM {encabezado} WHERE (%(resultado)s IS NULL OR %(resultado)s='' OR %(resultado)s=' ') AND (%(id)s IS NOT NULL) AND %(webservice)s=? ORDER BY %(tipo_cbte)s, %(punto_vta)s, %(cbte_nro)s".format(**tablas)
        ) % campos["encabezado"]
        ids = [webservice]
    else:
        query = ("SELECT * FROM {encabezado} WHERE ".format(**tablas)) + " OR ".join(
            ["{id}=?".format(**campos["encabezado"]) for id in ids]
        )
    if DEBUG:
        print("ejecutando", query, ids)
    try:
        ejecutar(cur, query, ids)
        rows = cur.fetchall()
        description = cur.description
        for row in rows:
            detalles = []
            encabezado = {}
            for i, k in enumerate(description):
                val = row[i]
                if isinstance(val, str):
                    val = val.decode(CHARSET)
                if isinstance(val, basestring):
                    val = val.strip()
                key = campos_rev["encabezado"].get(k[0], k[0].lower())
                val = redondear(ENCABEZADO, key, val)
                encabezado[key] = val
            ##print encabezado
            detalles = []
            if DEBUG:
                print(
                    ("SELECT * FROM {detalle} WHERE %(id)s = ?".format(**tablas))
                    % campos["detalle"],
                    [encabezado["id"]],
                )
            ejecutar(
                cur,
                ("SELECT * FROM {detalle} WHERE %(id)s = ?".format(**tablas))
                % campos["detalle"],
                [encabezado["id"]],
            )
            for it in cur.fetchall():
                detalle = {}
                for i, k in enumerate(cur.description):
                    val = it[i]
                    if isinstance(val, str):
                        val = val.decode(CHARSET)
                    key = campos_rev["detalle"].get(k[0], k[0].lower())
                    val = redondear(DETALLE, key, val)
                    detalle[key] = val
                detalles.append(detalle)
            encabezado["detalles"] = detalles

            cmps_asoc = []
            if DEBUG:
                print(
                    ("SELECT * FROM {cmp_asoc} WHERE %(id)s = ?".format(**tablas))
                    % campos["cmp_asoc"],
                    [encabezado["id"]],
                )
            ejecutar(
                cur,
                ("SELECT * FROM {cmp_asoc} WHERE %(id)s = ?".format(**tablas))
                % campos["cmp_asoc"],
                [encabezado["id"]],
            )
            for it in cur.fetchall():
                cmp_asoc = {}
                for i, k in enumerate(cur.description):
                    val = it[i]
                    key = campos_rev["cmp_asoc"].get(k[0], k[0].lower())
                    cmp_asoc[key] = val
                cmps_asoc.append(cmp_asoc)
            if cmps_asoc:
                encabezado["cbtes_asoc"] = cmps_asoc

            permisos = []
            if DEBUG:
                print(
                    ("SELECT * FROM {permiso} WHERE %(id)s = ?".format(**tablas))
                    % campos["permiso"],
                    [encabezado["id"]],
                )
            ejecutar(
                cur,
                ("SELECT * FROM {permiso} WHERE %(id)s = ?".format(**tablas))
                % campos["permiso"],
                [encabezado["id"]],
            )
            for it in cur.fetchall():
                permiso = {}
                for i, k in enumerate(cur.description):
                    val = it[i]
                    key = campos_rev["permiso"].get(k[0], k[0].lower())
                    permiso[key] = val
                permisos.append(permiso)
            if permisos:
                encabezado["permisos"] = permisos

            ivas = []
            if DEBUG:
                print(
                    ("SELECT * FROM {iva} WHERE %(id)s = ?".format(**tablas))
                    % campos["iva"],
                    [encabezado["id"]],
                )
            ejecutar(
                cur,
                ("SELECT * FROM {iva} WHERE %(id)s = ?".format(**tablas)) % campos["iva"],
                [encabezado["id"]],
            )
            for it in cur.fetchall():
                iva = {}
                for i, k in enumerate(cur.description):
                    val = it[i]
                    key = campos_rev["iva"].get(k[0], k[0].lower())
                    val = redondear(IVA, key, val)
                    iva[key] = val
                ivas.append(iva)
            if ivas:
                encabezado["ivas"] = ivas

            tributos = []
            if DEBUG:
                print(
                    ("SELECT * FROM {tributo} WHERE %(id)s = ?".format(**tablas))
                    % campos["tributo"],
                    [encabezado["id"]],
                )
            ejecutar(
                cur,
                ("SELECT * FROM {tributo} WHERE %(id)s = ?".format(**tablas))
                % campos["tributo"],
                [encabezado["id"]],
            )
            for it in cur.fetchall():
                tributo = {}
                for i, k in enumerate(cur.description):
                    val = it[i]
                    key = campos_rev["tributo"].get(k[0], k[0].lower())
                    val = redondear(TRIBUTO, key, val)
                    tributo[key] = val
                tributos.append(tributo)
            if tributos:
                encabezado["tributos"] = tributos

            yield encabezado
        db.commit()
    finally:
        cur.close()


def ayuda():
    print("-- Formato:")
    from formato_txt import CMP_ASOC, DATO, DETALLE, ENCABEZADO, IVA, PERMISO, TRIBUTO

    tipos_registro = [
        ("encabezado", ENCABEZADO),
        ("detalle", DETALLE),
        ("tributo", TRIBUTO),
        ("iva", IVA),
        ("cmp_asoc", CMP_ASOC),
        ("permiso", PERMISO),
        ("dato", DATO),
    ]
    print("-- Esquema:")
    for sql in esquema_sql(tipos_registro):
        print(sql)


if __name__ == "__main__":
    ayuda()
