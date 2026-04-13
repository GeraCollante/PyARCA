#!/usr/bin/python
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License
# for more details.

"Módulo con funciones auxiliares para el manejo de errores y temas comunes"

from future import standard_library

standard_library.install_aliases()
from builtins import chr, str

from past.builtins import basestring
from past.utils import old_div

__author__ = "Mariano Reingart <reingart@gmail.com>"
__copyright__ = "Copyright (C) 2013-2021 Mariano Reingart"
__license__ = "LGPL-3.0-or-later"

import csv
import datetime
import functools
import locale
import mimetypes
import os
import stat
import sys
import time
import traceback
import unicodedata
import warnings
from decimal import Decimal
from io import StringIO
from urllib.parse import urlencode, urlparse

try:
    from mimetools import choose_boundary
except ImportError:
    from email.generator import _make_boundary as choose_boundary
from html.parser import HTMLParser
from http.cookies import SimpleCookie

try:
    from ConfigParser import SafeConfigParser
except ImportError:
    # python3 workaround to read config files not in utf8
    import codecs
    from configparser import ConfigParser as SafeConfigParser

    SafeConfigParser.read = lambda self, filename: self.read_file(
        codecs.open(filename, "r", "latin1")
    )

from pysimplesoap.client import (
    SimpleXMLElement,
    SoapClient,
    SoapFault,
    parse_proxy,
    set_http_wrapper,
)

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except Exception:
        print("para soporte de JSON debe instalar simplejson")
        json = None


try:
    import platform

    import httplib2

    # corregir temas de negociacion de SSL en algunas versiones de ubuntu:
    from pysimplesoap.client import SoapClient

    monkey_patch = sys.version_info < (3, ) or httplib2._build_ssl_context.__module__ != "httplib2"
    needs_patch = platform.system() in ["Linux", "Darwin"] or sys.version_info > (3, 10)
    if needs_patch and not monkey_patch:
        _build_ssl_context = httplib2._build_ssl_context

        def _build_ssl_context_new(*args, **kwargs):
            context = _build_ssl_context(*args, **kwargs)
            # fix ssl.SSLError: [SSL: DH_KEY_TOO_SMALL] dh key too small
            # alternative: context.set_ciphers("DEFAULT@SECLEVEL=1")
            context.set_ciphers("AES128-SHA")
            return context

        httplib2._build_ssl_context = _build_ssl_context_new

except ImportError as mnfe:
    if "httplib2" in str(mnfe):
        print("para soporte de WebClient debe instalar httplib2")


DEBUG = False


# Funciones para manejo de errores:


def exception_info(current_filename=None, index=-1):
    "Analizar el traceback y armar un dict con la info amigable user-friendly"
    # guardo el traceback original (por si hay una excepción):
    info = sys.exc_info()  #         exc_type, exc_value, exc_traceback
    # importante: no usar unpacking porque puede causar memory leak
    if not current_filename:
        # genero un call stack para ver quien me llamó y limitar la traza:
        # advertencia: esto es necesario ya que en py2exe no tengo __file__
        try:
            raise ZeroDivisionError
        except ZeroDivisionError:
            f = sys.exc_info()[2].tb_frame.f_back
        current_filename = os.path.normpath(os.path.abspath(f.f_code.co_filename))

    # extraer la última traza del archivo solicitado:
    # (útil para no alargar demasiado la traza con lineas de las librerías)
    ret = {"filename": "", "lineno": 0, "function_name": "", "code": ""}
    try:
        for (filename, lineno, fn, text) in traceback.extract_tb(info[2]):
            if os.path.normpath(os.path.abspath(filename)) == current_filename:
                ret = {
                    "filename": filename,
                    "lineno": lineno,
                    "function_name": fn,
                    "code": text,
                }
    except Exception:
        pass
    # obtengo el mensaje de excepcion tal cual lo formatea python:
    # (para evitar errores de encoding)
    try:
        ret["msg"] = traceback.format_exception_only(*info[0:2])[0]
    except Exception:
        ret["msg"] = "<no disponible>"
    # obtener el nombre de la excepcion (ej. "NameError")
    try:
        ret["name"] = info[0].__name__
    except Exception:
        ret["name"] = "Exception"
    # obtener la traza formateada como string:
    try:
        tb = traceback.format_exception(*info)
        ret["tb"] = "".join(tb)
    except Exception:
        ret["tb"] = ""
    return ret


def inicializar_y_capturar_excepciones(func):
    "Decorador para inicializar y capturar errores (version para webservices)"

    @functools.wraps(func)
    def capturar_errores_wrapper(self, *args, **kwargs):
        try:
            # inicializo (limpio variables)
            self.Errores = []  # listas de str para lenguajes legados
            self.Observaciones = []
            self.errores = []  # listas de dict para usar en python
            self.observaciones = []
            self.Eventos = []
            self.Traceback = self.Excepcion = ""
            self.ErrCode = self.ErrMsg = self.Obs = ""
            # limpio variables especificas del webservice:
            self.inicializar()
            # actualizo los parámetros
            kwargs.update(self.params_in)
            # limpio los parámetros
            self.params_in = {}
            self.params_out = {}
            # llamo a la función (con reintentos)
            retry = self.reintentos + 1
            while retry:
                try:
                    retry -= 1
                    return func(self, *args, **kwargs)
                except OSError as e:
                    if e[0] not in (10054, 10053):
                        # solo reintentar si el error es de conexión
                        # (10054, 'Connection reset by peer')
                        # (10053, 'Software caused connection abort')
                        raise
                    else:
                        if DEBUG:
                            print(e, "Reintentando...")
                        self.log(exception_info().get("msg", ""))

        except SoapFault as e:
            # guardo destalle de la excepción SOAP
            self.ErrCode = str(e.faultcode)
            self.ErrMsg = str(e.faultstring)
            self.Excepcion = f"{e.faultcode}: {e.faultstring}"
            if self.LanzarExcepciones:
                raise
        except Exception:
            ex = exception_info()
            self.Traceback = ex.get("tb", "")
            try:
                self.Excepcion = ex.get("msg", "")
            except Exception:
                self.Excepcion = "<no disponible>"
            if self.LanzarExcepciones:
                raise
            else:
                self.ErrMsg = self.Excepcion
        finally:
            # guardo datos de depuración
            if self.client:
                self.XmlRequest = self.client.xml_request
                self.XmlResponse = self.client.xml_response

    return capturar_errores_wrapper


def inicializar_y_capturar_excepciones_simple(func):
    "Decorador para inicializar y capturar errores (versión básica indep.)"

    @functools.wraps(func)
    def capturar_errores_wrapper(self, *args, **kwargs):
        self.inicializar()
        try:
            return func(self, *args, **kwargs)
        except Exception:
            ex = exception_info()
            self.Excepcion = ex["name"]
            self.Traceback = ex["msg"]
            if self.LanzarExcepciones:
                raise
            else:
                return False

    return capturar_errores_wrapper


class BaseWS:
    "Infraestructura basica para interfaces webservices de AFIP"

    def __init__(self, reintentos=1):
        self.reintentos = reintentos
        self.xml = self.client = self.Log = None
        self.params_in = {}
        self.inicializar()
        self.Token = self.Sign = ""
        self.LanzarExcepciones = True

    def inicializar(self):
        self.Excepcion = self.Traceback = ""
        self.XmlRequest = self.XmlResponse = ""

    def Conectar(
        self,
        cache=None,
        wsdl=None,
        proxy="",
        wrapper=None,
        cacert=None,
        timeout=30,
        soap_server=None,
    ):
        "Conectar cliente soap del web service"
        try:
            # analizar transporte y servidor proxy:
            if wrapper:
                Http = set_http_wrapper(wrapper)
                self.Version = self.Version + " " + Http._wrapper_version
            if isinstance(proxy, dict):
                proxy_dict = proxy
            else:
                proxy_dict = parse_proxy(proxy)
                self.log(f"Proxy Dict: {str(proxy_dict)}")
            if self.HOMO or not wsdl:
                wsdl = self.WSDL
            # agregar sufijo para descargar descripción del servicio ?WSDL o ?wsdl
            if not wsdl.endswith(self.WSDL[-5:]) and wsdl.startswith("http"):
                wsdl += self.WSDL[-5:]
            if not cache or self.HOMO:
                # use 'cache' from installation base directory
                cache = os.path.join(self.InstallDir, "cache")
            # deshabilitar verificación cert. servidor si es nulo falso vacio
            if not cacert:
                cacert = None
            elif cacert is True or cacert.lower() == "default":
                # usar certificados predeterminados que vienen en la biblioteca
                try:
                    import certifi

                    cacert = certifi.where()
                except ImportError:
                    cacert = os.path.join(httplib2.__path__[0], "cacerts.txt")
            elif cacert.startswith("-----BEGIN CERTIFICATE-----"):
                pass
            else:
                if not os.path.exists(cacert):
                    self.log("Buscando CACERT en conf...")
                    cacert = os.path.join(
                        self.InstallDir, "conf", os.path.basename(cacert)
                    )
                if cacert and not os.path.exists(cacert):
                    self.log(f"No se encuentra CACERT: {str(cacert)}")
                    warnings.warn(f"No se encuentra CACERT: {str(cacert)}")
                    cacert = None  # wrong version, certificates not found...
                    raise RuntimeError("Error de configuracion CACERT ver DebugLog")
                    return False

            if cacert and not os.path.isabs(cacert):
                self.log(f"Fixing CACERT: {cacert}")
                cacert = os.path.abspath(cacert)
                self.log(f"Fixed CACERT: {cacert}")

            ## cacert = "/etc/ssl/certs/ca-certificates.crt"
            self.log(
                f"Conectando a wsdl={wsdl} cache={cache} proxy={proxy_dict} cacert={cacert}"
            )
            # analizar espacio de nombres (axis vs .net):
            ns = "ser" if self.WSDL[-5:] == "?wsdl" else None
            self.client = SoapClient(
                wsdl=wsdl,
                cache=cache,
                proxy=proxy_dict,
                cacert=cacert,
                timeout=timeout,
                ns=ns,
                soap_server=soap_server,
                trace="--trace" in sys.argv,
            )
            self.cache = cache  # utilizado por WSLPG y WSAA (Ticket de Acceso)
            self.wsdl = wsdl  # utilizado por TrazaMed (para corregir el location)
            # corrijo ubicación del servidor (puerto http 80 en el WSDL AFIP)
            for service in list(self.client.services.values()):
                for port in list(service["ports"].values()):
                    location = port["location"]
                    if location and location.startswith("http://"):
                        warnings.warn(f"Corrigiendo WSDL ... {location}")
                        location = location.replace("http://", "https://").replace(
                            ":80", ":443"
                        )
                        # usar servidor real si en el WSDL figura "localhost"
                        localhost = "https://localhost:"
                        if location.startswith(localhost):
                            url = urlparse(wsdl)
                            location = location.replace("localhost", url.hostname)
                            location = location.replace(":9051", ":443")
                        port["location"] = location
            return True
        except Exception:
            ex = traceback.format_exception(
                sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]
            )
            self.Traceback = "".join(ex)
            try:
                self.Excepcion = traceback.format_exception_only(
                    sys.exc_info()[0], sys.exc_info()[1]
                )[0]
            except Exception:
                self.Excepcion = "<no disponible>"
            if self.LanzarExcepciones:
                raise
            return False

    def log(self, msg):
        "Dejar mensaje en bitacora de depuración (método interno)"
        if not isinstance(msg, str):
            msg = str(msg, "utf8", "ignore")
        if not self.Log:
            self.Log = StringIO()
        self.Log.write(msg)
        self.Log.write("\n\r")
        if DEBUG:
            warnings.warn(msg)

    def DebugLog(self):
        "Devolver y limpiar la bitácora de depuración"
        if self.Log:
            msg = self.Log.getvalue()
            # limpiar log
            self.Log.close()
            self.Log = None
        else:
            msg = ""
        return msg

    def LoadTestXML(self, xml):
        "Cargar un archivo de pruebas con la respuesta simulada (depuración)"
        # si el parametro es un nombre de archivo, cargar el contenido:
        if os.path.exists(xml):
            xml = open(xml).read()

        class DummyHTTP:
            def __init__(self, xml_response):
                self.xml_response = xml_response

            def request(self, location, method, body, headers):
                return {}, self.xml_response

        self.client.http = DummyHTTP(xml)

    @property
    def xml_request(self):
        return self.XmlRequest

    @property
    def xml_response(self):
        return self.XmlResponse

    def AnalizarXml(self, xml=""):
        "Analiza un mensaje XML (por defecto el ticket de acceso)"
        try:
            if not xml or xml == "XmlResponse":
                xml = self.XmlResponse
            elif xml == "XmlRequest":
                xml = self.XmlRequest
            self.xml = SimpleXMLElement(xml)
            return True
        except Exception:
            self.Excepcion = traceback.format_exception_only(
                sys.exc_info()[0], sys.exc_info()[1]
            )[0]
            return False

    def ObtenerTagXml(self, *tags):
        "Busca en el Xml analizado y devuelve el tag solicitado"
        # convierto el xml a un objeto
        try:
            if self.xml:
                xml = self.xml
                # por cada tag, lo busco segun su nombre o posición
                for tag in tags:
                    xml = xml(tag)  # atajo a getitem y getattr
                # vuelvo a convertir a string el objeto xml encontrado
                return str(xml)
        except Exception:
            self.Excepcion = traceback.format_exception_only(
                sys.exc_info()[0], sys.exc_info()[1]
            )[0]

    def SetParametros(self, cuit, token, sign):
        "Establece un parámetro general"
        self.Token = token
        self.Sign = sign
        self.Cuit = cuit
        return True

    @inicializar_y_capturar_excepciones
    def SetTicketAcceso(self, ta_string):
        "Establecer el token y sign desde un ticket de acceso XML"
        if ta_string:
            ta = SimpleXMLElement(ta_string)
            self.Token = str(ta.credentials.token)
            self.Sign = str(ta.credentials.sign)
            return True
        else:
            raise RuntimeError("Ticket de Acceso vacio!")

    def SetParametro(self, clave, valor):
        "Establece un parámetro de entrada (a usarse en llamada posterior)"
        # útil para parámetros de entrada (por ej. VFP9 no soporta más de 27)
        self.params_in[str(clave)] = valor
        return True

    def GetParametro(self, clave, clave1=None, clave2=None, clave3=None, clave4=None):
        "Devuelve un parámetro de salida (establecido por llamada anterior)"
        # útil para parámetros de salida (por ej. campos de TransaccionPlainWS)
        valor = self.params_out.get(clave)
        # busco datos "anidados" (listas / diccionarios)
        for clave in (clave1, clave2, clave3, clave4):
            if clave is not None and valor is not None:
                if isinstance(clave1, basestring) and clave.isdigit():
                    clave = int(clave)
                try:
                    valor = valor[clave]
                except (KeyError, IndexError):
                    valor = None
        if valor is not None:
            if isinstance(valor, basestring):
                return valor
            else:
                return str(valor)
        else:
            return ""

    def LeerError(self):
        "Recorro los errores devueltos y devuelvo el primero si existe"

        if self.Errores:
            # extraigo el primer item
            er = self.Errores.pop(0)
            return er
        else:
            return ""


class WebClient:
    "Minimal webservice client to do POST request with multipart encoded FORM data"

    def __init__(
        self,
        location,
        enctype="multipart/form-data",
        trace=False,
        cacert=None,
        timeout=30,
        proxy=None,
    ):
        kwargs = {}
        kwargs["timeout"] = timeout
        kwargs["disable_ssl_certificate_validation"] = cacert is None
        kwargs["ca_certs"] = cacert
        if proxy:
            if isinstance(proxy, dict):
                proxy_dict = proxy
            else:
                proxy_dict = parse_proxy(proxy)
                print("using proxy", proxy_dict)
            import socks

            kwargs["proxy_info"] = httplib2.ProxyInfo(
                proxy_type=socks.PROXY_TYPE_HTTP, **proxy_dict
            )
        self.http = httplib2.Http(**kwargs)
        self.trace = trace
        self.location = location
        self.enctype = enctype
        self.cookies = None
        self.method = "POST"
        self.referer = None

    def multipart_encode(self, vars):
        "Enconde form data (vars dict)"
        boundary = choose_boundary()
        buf = StringIO()
        def _is_string(val):
            return isinstance(val, str)
        for key, value in list(vars.items()):
            if _is_string(value):
                buf.write(f"--{boundary}\r\n")
                buf.write(f'Content-Disposition: form-data; name="{key}"')
                buf.write("\r\n\r\n" + value + "\r\n")
            else:
                fd = value
                os.fstat(fd.fileno())[stat.ST_SIZE]
                filename = os.path.basename(fd.name)
                contenttype = (
                    mimetypes.guess_type(filename)[0] or "application/octet-stream"
                )
                buf.write(f"--{boundary}\r\n")
                buf.write(
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                )
                buf.write(f"Content-Type: {contenttype}\r\n")
                # buffer += 'Content-Length: %s\r\n' % file_size
                fd.seek(0)
                buf.write("\r\n" + fd.read() + "\r\n")
        buf.write("--" + boundary + "--\r\n\r\n")
        buf = buf.getvalue()
        return boundary, buf

    def __call__(self, *args, **vars):
        "Perform a GET/POST request and return the response"

        location = self.location
        # extend the base URI with additional components
        if args:
            location += "/".join(args)
        if self.method == "GET":
            location += f"?{urlencode(vars)}"

        # prepare the request content suitable to be sent to the server:
        if self.enctype == "multipart/form-data":
            boundary, body = self.multipart_encode(vars)
            content_type = f"{self.enctype}; boundary={boundary}"
        elif self.enctype == "application/x-www-form-urlencoded":
            body = urlencode(vars)
            content_type = self.enctype
        else:
            body = None

        # add headers according method, cookies, etc.:
        headers = {}
        if self.method == "POST":
            headers.update(
                {
                    "Content-type": content_type,
                    "Content-length": str(len(body)),
                }
            )
        if self.cookies:
            headers["Cookie"] = self.cookies.output(attrs=(), header="", sep=";")
        if self.referer:
            headers["Referer"] = self.referer

        if self.trace:
            print("-" * 80)
            print(f"{self.method} {location}")
            print("\n".join([f"{k}: {v}" for k, v in list(headers.items())]))
            print(f"\n{body}")

        # send the request to the server and store the result:
        response, content = self.http.request(
            location, self.method, body=body, headers=headers
        )
        self.response = response
        self.content = content

        if self.trace:
            print()
            print("\n".join([f"{k}: {v}" for k, v in list(response.items())]))
            print(content)
            print("=" * 80)

        # Parse and store the cookies (if any)
        if "set-cookie" in self.response:
            if not self.cookies:
                self.cookies = SimpleCookie()
            self.cookies.load(self.response["set-cookie"])

        return content


class AttrDict(dict):
    "Custom Dict to hold attributes and items"


class HTMLFormParser(HTMLParser):
    "Convert HTML form into custom named-tuple dicts"

    def __init__(self, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.forms = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "name" in attrs:
            name = attrs["name"]
        elif "id" in attrs:
            name = attrs["id"]
        else:
            name = None
        if tag == "form":
            form = AttrDict()
            for k, v in list(attrs.items()):
                setattr(form, f"_{k}", v)
            self.form = self.forms[name or len(self.forms)] = form
        elif tag == "input":
            self.form[name or len(self.form)] = attrs.get("value")


# Funciones para manejo de archivos de texto de campos de ancho fijo:


def leer(linea, formato, expandir_fechas=False):
    "Analiza una linea de texto dado un formato, devuelve un diccionario"
    dic = {}
    comienzo = 1
    for fmt in formato:
        clave, longitud, tipo = fmt[0:3]
        dec = (len(fmt) > 3 and isinstance(fmt[3], int)) and fmt[3] or 2
        valor = linea[comienzo - 1 : comienzo - 1 + longitud].strip()
        try:
            if chr(8) in valor or chr(127) in valor or chr(255) in valor:
                valor = None  # nulo
            elif (valor == "" or valor == "NULL") and tipo in (N, IMPORTE):
                valor = None
            elif tipo == N:
                if valor:
                    valor = int(valor)
                else:
                    valor = 0
            elif tipo == IMPORTE:
                if valor:
                    try:
                        if "." in valor:
                            valor = float(valor)
                        else:
                            valor = valor.strip(" ")
                            if valor[0] == "-":
                                sign = -1
                                valor = valor[1:]
                            else:
                                sign = +1
                            valor = sign * float(
                                (f"%s.%0{dec}d")
                                % (int(valor[:-dec] or "0"), int(valor[-dec:] or "0"))
                            )
                    except ValueError:
                        raise ValueError(f"Campo invalido: {clave} = '{valor}'")
                else:
                    valor = 0.00
            elif expandir_fechas and clave.lower().startswith("fec") and longitud <= 8:
                if valor:
                    valor = f"{valor[0:4]}-{valor[4:6]}-{valor[6:8]}"
                else:
                    valor = None
            else:
                if isinstance(valor, bytes):
                    valor = valor.decode("ascii", "ignore")
                # campos string completos con ~ son convertidos a nulo:
                if valor and valor == "~" * len(valor):
                    valor = None
            if not valor and clave in dic and len(linea) <= comienzo:
                pass  # ignorar - compatibilidad hacia atrás (cambios tamaño)
            else:
                dic[clave] = valor
            comienzo += longitud
        except Exception as e:
            raise ValueError(
                f"Error al leer campo {clave} pos {comienzo} val '{valor}': {str(e)}"
            )
    return dic


def escribir(dic, formato, contraer_fechas=False):
    "Genera una cadena dado un formato y un diccionario de claves/valores"
    linea = " " * sum([fmt[1] for fmt in formato])
    comienzo = 1
    for fmt in formato:
        clave, longitud, tipo = fmt[0:3]
        try:
            dec = (len(fmt) > 3 and isinstance(fmt[3], int)) and fmt[3] or 2
            if clave.capitalize() in dic:
                clave = clave.capitalize()
            s = dic.get(clave, "")
            if s is None:
                valor = chr(127)
                tipo = None
            else:
                valor = str(s)
            # reemplazo saltos de linea por tabulaci{on vertical
            valor = valor.replace("\n\r", "\v").replace("\n", "\v").replace("\r", "\v")
            if tipo == N and valor and valor != "NULL":
                valor = ("%%0%dd" % longitud) % int(valor)
            elif tipo == IMPORTE and valor:
                valor = ("%%0%d.%df" % (longitud + 1, dec) % float(valor)).replace(
                    ".", ""
                )
            elif (
                contraer_fechas
                and clave.lower().startswith("fec")
                and longitud <= 8
                and valor
            ):
                valor = valor.replace("-", "")
            else:
                valor = ("%%-0%ds" % longitud) % valor
            linea = linea[: comienzo - 1] + valor + linea[comienzo - 1 + longitud :]
            comienzo += longitud
        except Exception as e:
            warnings.warn(
                f"Error al escribir campo {clave} pos {comienzo} val '{valor}': {str(e)}"
            )
    return linea + "\n"


# Tipos de datos (código RG1361)


NUMERICO = N = "Numerico"  # 2
ALFANUMERICO = A = "Alfanumerico"  # 3
IMPORTE = "Importe"  # 4
CARACTER = C = ALFANUMERICO  # 1 (caracter alfabetico)
BLANCO = B = ALFANUMERICO  # 9 (blanco)

# Funciones para manejo de archivos de texto de ancho fijo


def formato_txt(formatos, registros):
    print("Formato:")
    for tipo_reg, estructura in sorted(registros.items()):
        formato = formatos[estructura]
        comienzo = 1
        print(f"=== {estructura} ===")
        for fmt in formato:
            clave, longitud, tipo = fmt[0:3]
            dec = len(fmt) > 3 and fmt[3] or (tipo == "I" and "2" or "")
            f = ["Campo: %-20s", "Posición: %3d", "Longitud: %4d", "Tipo: %s"]
            v = [clave, comienzo, longitud, tipo]
            if dec:
                f.append("Decimales: %s")
                v.append(dec)
            if clave == "tipo_reg":
                f.append("Valor: %s")
                v.append(tipo_reg)
            print(" *", " ".join(f) % tuple(v))
            comienzo += longitud


def leer_txt(formatos, registros, nombre_archivo):
    ret = []
    with open(nombre_archivo) as archivo:
        for linea in archivo:
            tipo_reg = str(linea[0])
            estructura = registros[tipo_reg]
            formato = formatos[estructura]
            d = leer(linea, formato)
            if estructura == "encabezado":
                ret.append(d)
                dic = d
            else:
                dic.setdefault(estructura, []).append(d)
    return ret


def grabar_txt(formatos, registros, nombre_archivo, dicts, agrega=False):
    with open(nombre_archivo, agrega and "a" or "w") as archivo:
        for dic in dicts:
            encabezado = formatos["encabezado"]
            dic["tipo_reg"] = "0"
            archivo.write(escribir(dic, encabezado))
            for tipo_reg, estructura in sorted(registros.items()):
                for it in dic.get(estructura, {}):
                    for d in ([it] if isinstance(it, dict) else it):
                        d["tipo_reg"] = tipo_reg
                        archivo.write(escribir(d, formatos[estructura]))


# Funciones para manejo de Panillas CSV y Tablas


def generar_csv(filas, formato, fn="planilla.csv", delimiter=";"):
    "Dado una lista de registros  escribe"
    ext = os.path.splitext(fn)[1].lower()
    if ext == ".csv":
        with open(fn, "wb") as f:
            fieldnames = [fmt[0] for fmt in formato]
            csv_writer = csv.DictWriter(f, fieldnames, dialect="excel", delimiter=";")
            csv_writer.writeheader()
            for fila in filas:
                csv_writer.writerow(fila)


def tabular(filas, formato):
    from tabulate import tabulate

    columnas = [fmt[0] for fmt in formato if fmt[0] not in ("tipo_reg",)]
    tabla = [[fila.get(col) for col in columnas] for fila in filas]
    return tabulate(tabla, columnas, floatfmt=".2f")


# Funciones para manejo de tablas en DBF


def guardar_dbf(formatos, agrega=False, conf_dbf=None):
    import dbf

    if DEBUG:
        print("Creando DBF...")

    for nombre, formato, registros in formatos:
        campos = {}
        claves = []
        claves_map = {}
        filename = conf_dbf.get(nombre.lower(), f"{nombre[:8]}.dbf")
        if DEBUG:
            print(f"=== tabla {nombre} ({filename}) ===")
        for fmt in formato:
            clave, longitud, tipo = fmt[0:3]
            dec = len(fmt) > 3 and fmt[3] or (tipo == "I" and "2" or "")
            if longitud > 250:
                tipo = "M"  # memo!
            elif tipo == A:
                tipo = f"C({longitud})"
            elif tipo == N:
                if longitud >= 18:
                    longitud = 17
                tipo = f"N({longitud},0)"
            elif tipo == IMPORTE:
                if not dec:
                    dec = 0
                else:
                    dec = int(dec)
                if longitud >= 18:
                    longitud = 17
                if longitud - 2 <= dec:
                    longitud += longitud - dec + 1  # ajusto long. decimales
                tipo = f"N({longitud},{dec})"
            # unificar nombre de campos duplicados por compatibilidad hacia atrás:
            clave_dbf = claves_map.get(clave, dar_nombre_campo_dbf(clave, claves))
            if clave not in claves_map:
                claves_map[clave] = clave_dbf
                claves.append(clave_dbf)
            campo = f"{clave_dbf} {tipo}"
            if DEBUG:
                print(f" * {campo} : {clave}")
            campos[clave_dbf] = campo
        if DEBUG:
            print("leyendo tabla", nombre, filename)
        if agrega:
            tabla = dbf.Table(filename, [campos[clave] for clave in claves])
        else:
            tabla = dbf.Table(filename)

        for d in registros:
            # si no es un diccionario, ignorar ya que seguramente va en otra
            # tabla (por ej. retenciones tiene su propio formato)
            if isinstance(d, basestring):
                continue
            r = {}
            claves = []
            claves_map = {}
            for fmt in formato:
                clave, longitud, tipo = fmt[0:3]
                if agrega or clave in d:
                    v = d.get(clave, None)
                    if DEBUG:
                        print(clave, v, tipo)
                    if v is None and tipo == A:
                        v = ""
                    if (v is None or v == "") and tipo in (IMPORTE, N):
                        v = 0
                    if tipo == A:
                        if isinstance(v, str):
                            v = v.encode("ascii", "replace")
                        if isinstance(v, str):
                            v = v.decode("ascii", "replace").encode("ascii", "replace")
                        if not isinstance(v, basestring):
                            v = str(v)
                        if len(v) > longitud:
                            v = v[:longitud]  # recorto el string para que quepa
                    # unificar nombre de campos duplicados por compatibilidad hacia atrás:
                    clave_dbf = claves_map.get(
                        clave, dar_nombre_campo_dbf(clave, claves)
                    )
                    if clave not in claves_map:
                        claves_map[clave] = clave_dbf
                        claves.append(clave_dbf)
                    r[clave_dbf] = v
            # agregar si lo solicitaron o si la tabla no tiene registros:
            if agrega or not tabla:
                if DEBUG:
                    print("Agregando !!!", r)
                tabla.append(r)
            else:
                if DEBUG:
                    print("Actualizando ", r)
                reg = tabla.current()
                for k, v in list(reg.scatter_fields().items()):
                    if k not in r:
                        r[k] = v
                if DEBUG:
                    print("Actualizando ", r)
                reg.write_record(**r)
                # mover de registro para no actualizar siempre el primero:
                if not tabla.eof() and len(registros) > 1:
                    if DEBUG:
                        print("Moviendo al próximo registro ", tabla.record_number)
                    next(tabla)
        tabla.close()


def leer_dbf(formatos, conf_dbf):
    import dbf

    if DEBUG:
        print("Leyendo DBF...")

    for nombre, formato, ld in formatos:
        filename = conf_dbf.get(nombre.lower(), f"{nombre[:8]}.dbf")
        if DEBUG:
            print("leyendo tabla", nombre, filename)
        if not os.path.exists(filename):
            continue
        tabla = dbf.Table(filename)
        for reg in tabla:
            r = {}
            d = reg.scatter_fields()
            if DEBUG:
                print("scatter_fields", d)
            claves = []
            for fmt in formato:
                clave, longitud, tipo = fmt[0:3]
                # import pdb; pdb.set_trace()
                clave_dbf = dar_nombre_campo_dbf(clave, claves)
                claves.append(clave_dbf)
                v = d.get(clave_dbf)
                if DEBUG:
                    print("fmt", clave, clave_dbf, v)
                if r.get(clave) is None:
                    r[clave] = v
            if isinstance(ld, dict):
                ld.update(r)
            else:
                ld.append(r)


def dar_nombre_campo_dbf(clave, claves):
    "Reducir nombre de campo a 10 caracteres, sin espacios ni _, sin repetir"
    # achico el nombre del campo para que quepa en la tabla:
    nombre = clave.replace("_", "")[:10]
    # si el campo esta repetido, le agrego un número
    i = 0
    while nombre in claves:
        i += 1
        nombre = nombre[:9] + str(i)
    return nombre.lower()


def verifica(ver_list, res_dict, difs):
    "Verificar que dos diccionarios sean iguales, actualiza lista diferencias"
    for k, v in list(ver_list.items()):
        # normalizo a float para poder comparar numericamente:
        if isinstance(v, (Decimal, int)):
            v = float(v)
        if isinstance(res_dict.get(k), (Decimal, int)):
            res_dict[k] = float(res_dict[k])
        if isinstance(v, list):
            # verifico que ambas listas tengan la misma cantidad de elementos:
            if v and k not in res_dict and v:
                difs.append(f"falta tag {k}: {repr(v)} {repr(res_dict.get(k))}")
            elif len(res_dict.get(k, [])) != len(v or []):
                difs.append(
                    f"tag {k} len !=: {repr(v)} {repr(res_dict.get(k))}"
                )
            else:
                # ordeno las listas para poder compararlas si vienen mezcladas
                rl = sorted(res_dict.get(k, []))
                # comparo los elementos uno a uno:
                for i, vl in enumerate(sorted(v)):
                    verifica(vl, rl[i], difs)
        elif isinstance(v, dict):
            # comparo recursivamente los elementos:
            verifica(v, res_dict.get(k, {}), difs)
        elif res_dict.get(k) is None or v is None:
            # alguno de los dos es nulo, verifico si ambos lo son o faltan
            if v == "":
                v = None
            r = res_dict.get(k)
            if r == "":
                r = None
            if not (r is None and v is None):
                difs.append(f"{k}: nil {repr(v)}!={repr(r)}")
        elif type(res_dict.get(k)) is type(v):
            # tipos iguales, los comparo directamente
            if res_dict.get(k) != v:
                difs.append(f"{k}: {repr(v)}!={repr(res_dict.get(k))}")
        elif isinstance(v, float) or isinstance(res_dict.get(k), float):
            # comparar numericamente
            if float(res_dict.get(k)) != float(v):
                difs.append(f"{k}: {repr(v)}!={repr(res_dict.get(k))}")
        elif str(res_dict.get(k)) != str(v):
            # tipos diferentes, comparo la representación
            difs.append(f"{k}: str {repr(v)}!={repr(res_dict.get(k))}")
        else:
            pass
            # print "%s: %s==%s" % (k, repr(v), repr(res_dict[k]))


def safe_console():
    if True or sys.stdout.encoding is None:

        class SafeWriter:
            def __init__(self, target):
                self.target = target
                self.encoding = "utf-8"
                self.errors = "replace"
                self.encode_to = "latin-1"

            def write(self, s):
                self.target.write(self.intercept(s).decode("utf8"))

            def flush(self):
                self.target.flush()

            def intercept(self, s):
                if not isinstance(s, str):
                    s = s.decode(self.encode_to, self.errors)
                return s.encode(self.encoding, self.errors)

        sys.stdout = SafeWriter(sys.stdout)
        # sys.stderr = SafeWriter(sys.stderr)
        print(f"Encodign in {locale.getpreferredencoding()}")


def norm(x, encoding="latin1"):
    "Convertir acentos codificados en ISO 8859-1 u otro, a ASCII regular"
    if not isinstance(x, basestring):
        x = str(x)
    elif isinstance(x, str):
        x = x.decode(encoding, "ignore")
    return unicodedata.normalize("NFKD", x).encode("ASCII", "ignore")


class UTC(datetime.tzinfo):
    "Python2 datetime.timezone.utc equiv"
    def utcoffset(self, dt):
        return datetime.timedelta(0)
    def dst(self, dt):
        return self.utcoffset(dt)
    def tzname(self, dt):
        return "UTC"


def date(fmt=None, timestamp=None):
    "Manejo de fechas (simil PHP)"
    if fmt == "U":  # return timestamp
        # use localtime to later convert to UTC timezone
        t = datetime.datetime.now()
        return int(time.mktime(t.timetuple()))
    if fmt == "c":  # return isoformat
        # use universal standard time to avoid timezone differences
        d = datetime.datetime.fromtimestamp(timestamp, tz=UTC())
        return d.isoformat()
    if fmt == "Ymd":
        d = datetime.datetime.now()
        return d.strftime("%Y%m%d")


def get_install_dir():
    if not hasattr(sys, "frozen"):
        basepath = __file__
    elif sys.frozen == "dll":
        import win32api

        basepath = win32api.GetModuleFileName(sys.frozendllhandle)
    else:
        basepath = sys.executable

    if hasattr(sys, "frozen"):
        # we are running as py2exe-packed executable
        try:
            import pythoncom
            pythoncom.frozen = 1
        except ImportError:
            pass
        sys.argv[0] = sys.executable

    return os.path.dirname(os.path.abspath(basepath))


def abrir_conf(config_file, debug=False):
    "Abrir el archivo de configuración (usar primer parámetro como ruta)"
    # en principio, usar el nombre de archivo predeterminado
    # si se pasa el archivo de configuración por parámetro, confirmar que exista
    # y descartar que sea una opción
    if len(sys.argv) > 1:
        if os.path.splitext(sys.argv[1])[1].lower() == ".ini":
            config_file = sys.argv.pop(1)
    if not os.path.exists(config_file) or not os.path.isfile(config_file):
        warnings.warn(f"Archivo de configuracion {config_file} invalido")

    if debug:
        print("CONFIG_FILE:", config_file)

    config = SafeConfigParser()
    config.read(config_file)

    return config


def json_serializer(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    else:
        return str(obj)


if __name__ == "__main__":
    print(get_install_dir())
    try:
        old_div(1, 0)
    except Exception:
        ex = exception_info()
        print(ex)
        assert ex["name"] == "ZeroDivisionError"
        assert ex["lineno"] == 73
        assert ex["tb"]
