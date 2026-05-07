#!/usr/bin/env python3
"""Tests para facturar.py — CLI de facturación electrónica.

Todos los tests corren sin conexión a ARCA. WSAA, WSFEv1 y FEPDF
están 100% mockeados.
"""

import argparse
import datetime
import json
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Importar el módulo bajo test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import facturar  # noqa: E402 — root-level CLI script, not a package module

# Evitar que el conftest de pyafipws intente autenticar contra WSAA
pytestmark = [pytest.mark.dontusefix]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tmp_facturas(tmp_path, monkeypatch):
    """Redirige FACTURAS_DIR y REGISTRO_PATH a tmpdir."""
    facturas_dir = str(tmp_path / "facturas")
    registro_path = os.path.join(facturas_dir, "registro.json")
    monkeypatch.setattr(facturar, "FACTURAS_DIR", facturas_dir)
    monkeypatch.setattr(facturar, "REGISTRO_PATH", registro_path)
    return tmp_path


@pytest.fixture
def mock_wsfev1():
    """WSFEv1 mockeado con respuestas exitosas por defecto."""
    mock = Mock()
    mock.CompUltimoAutorizado.return_value = "7"
    mock.CAE = "86151425715928"
    mock.Vencimiento = "20260423"
    mock.Resultado = "A"
    mock.ErrMsg = ""
    mock.Obs = ""
    mock.CAESolicitar.return_value = mock.CAE
    mock.AppServerStatus = "OK"
    mock.DbServerStatus = "OK"
    mock.AuthServerStatus = "OK"
    mock.FechaCbte = "20260413"
    mock.ImpTotal = "2060038.06"
    mock.CbteNro = 8
    mock.PuntoVenta = 3
    return mock


@pytest.fixture
def mock_wsfexv1():
    """WSFEXv1 mockeado con respuestas exitosas por defecto."""
    mock = Mock()
    mock.GetLastCMP.return_value = 5
    mock.GetLastID.return_value = 100
    mock.GetParamCtz.return_value = "1180.50"
    mock.Authorize.return_value = "86200000000001"
    mock.CAE = "86200000000001"
    mock.FchVencCAE = "20260516"
    mock.Vencimiento = "16/05/2026"
    mock.Resultado = "A"
    mock.ErrMsg = ""
    mock.Obs = ""
    mock.AppServerStatus = "OK"
    mock.DbServerStatus = "OK"
    mock.AuthServerStatus = "OK"
    return mock


@pytest.fixture
def mock_fepdf():
    """FEPDF mockeado."""
    mock = Mock()
    mock.CargarFormato.return_value = True
    mock.CrearFactura.return_value = True
    mock.AgregarDetalleItem.return_value = True
    mock.CrearPlantilla.return_value = True
    mock.ProcesarPlantilla.return_value = True
    mock.GenerarPDF.return_value = True
    mock.AgregarDato.return_value = True
    mock.AgregarCampo.return_value = True
    return mock


@pytest.fixture
def sample_comprobante():
    """Comprobante de ejemplo para tests."""
    return {
        "tipo_cbte": 11,
        "tipo_nombre": "Factura C",
        "cbte_nro": 8,
        "cae": "86151425715928",
        "fch_venc_cae": "20260423",
        "fecha_cbte": "20260413",
        "punto_vta": 3,
        "monto": 2060038.06,
        "cliente": "Consumidor Final",
        "descripcion": "Servicios de desarrollo de software - Abril 2026",
        "tipo_doc": 99,
        "nro_doc": 0,
        "desde": "20260401",
        "hasta": "20260430",
        "fecha_venc_pago": "20260510",
        "factura_asociada": None,
    }


# =============================================================================
# 1. Configuración y constantes
# =============================================================================

class TestConstantes:
    def test_cuit_cargado(self):
        assert isinstance(facturar.CUIT, int)
        assert facturar.CUIT > 0

    def test_tipos_comprobante(self):
        assert facturar.FACTURA_C == 11
        assert facturar.NOTA_CREDITO_C == 13
        assert facturar.FACTURA_E == 19
        assert facturar.NOTA_CREDITO_E == 21

    def test_urls_wsfexv1(self):
        assert "wsfexv1" in facturar.URLS["homo"]
        assert "wsfexv1" in facturar.URLS["prod"]
        assert "wsfexv1" in facturar.URLS["prod"]["wsfexv1"]
        assert "homo" in facturar.URLS["homo"]["wsfexv1"]

    def test_concepto_servicios(self):
        assert facturar.CONCEPTO == 2

    def test_urls_produccion(self):
        assert "wsaa" in facturar.URLS["prod"]
        assert "wsfev1" in facturar.URLS["prod"]
        assert "afip.gov.ar" in facturar.URLS["prod"]["wsaa"]
        assert "wsaahomo" not in facturar.URLS["prod"]["wsaa"]

    def test_urls_homologacion(self):
        assert "wsaa" in facturar.URLS["homo"]
        assert "wsfev1" in facturar.URLS["homo"]
        assert "homo" in facturar.URLS["homo"]["wsaa"]

    def test_conf_pdf_claves(self):
        claves_requeridas = {"EMPRESA", "MEMBRETE1", "MEMBRETE2", "CUIT", "IIBB", "IVA", "INICIO"}
        assert claves_requeridas.issubset(set(facturar.CONF_PDF.keys()))


# =============================================================================
# 2. Registro (cargar / guardar)
# =============================================================================

class TestRegistro:
    def test_cargar_registro_vacio(self, tmp_facturas):
        """Si no existe el archivo, retorna lista vacía."""
        result = facturar.cargar_registro()
        assert result == []

    def test_guardar_y_cargar_roundtrip(self, tmp_facturas, sample_comprobante):
        """Guardar y re-cargar mantiene los datos."""
        registro = [sample_comprobante]
        facturar.guardar_registro(registro)
        cargado = facturar.cargar_registro()
        assert len(cargado) == 1
        assert cargado[0]["cae"] == sample_comprobante["cae"]
        assert cargado[0]["monto"] == sample_comprobante["monto"]
        assert cargado[0]["cliente"] == sample_comprobante["cliente"]

    def test_guardar_crea_directorio(self, tmp_facturas):
        """guardar_registro crea el directorio si no existe."""
        facturar.guardar_registro([])
        assert os.path.exists(facturar.FACTURAS_DIR)
        assert os.path.exists(facturar.REGISTRO_PATH)

    def test_guardar_multiples(self, tmp_facturas, sample_comprobante):
        """Guardar múltiples comprobantes."""
        c1 = {**sample_comprobante, "cbte_nro": 8}
        c2 = {**sample_comprobante, "cbte_nro": 9, "monto": 4561512.81}
        facturar.guardar_registro([c1, c2])
        cargado = facturar.cargar_registro()
        assert len(cargado) == 2
        assert cargado[0]["cbte_nro"] == 8
        assert cargado[1]["cbte_nro"] == 9

    def test_registro_json_valido(self, tmp_facturas, sample_comprobante):
        """El archivo guardado es JSON válido."""
        facturar.guardar_registro([sample_comprobante])
        with open(facturar.REGISTRO_PATH) as f:
            data = json.load(f)
        assert isinstance(data, list)


# =============================================================================
# 3. Autenticación
# =============================================================================

class TestAutenticar:
    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_produccion_usa_urls_prod(self, MockWSAA, MockWSFEv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = "ticket_acceso_fake"
        wsfev1 = MockWSFEv1.return_value
        wsfev1.AppServerStatus = "OK"
        wsfev1.DbServerStatus = "OK"
        wsfev1.AuthServerStatus = "OK"

        facturar.autenticar(produccion=True)

        wsaa.Autenticar.assert_called_once_with(
            "wsfe", facturar.CERT, facturar.PRIVATEKEY,
            wsdl=facturar.URLS["prod"]["wsaa"], cache=facturar.CACHE
        )
        wsfev1.Conectar.assert_called_once_with(
            facturar.CACHE, facturar.URLS["prod"]["wsfev1"]
        )

    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_homologacion_usa_urls_homo(self, MockWSAA, MockWSFEv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = "ticket_acceso_fake"
        wsfev1 = MockWSFEv1.return_value
        wsfev1.AppServerStatus = "OK"
        wsfev1.DbServerStatus = "OK"
        wsfev1.AuthServerStatus = "OK"

        facturar.autenticar(produccion=False)

        wsaa.Autenticar.assert_called_once_with(
            "wsfe", facturar.CERT, facturar.PRIVATEKEY,
            wsdl=facturar.URLS["homo"]["wsaa"], cache=facturar.CACHE
        )
        wsfev1.Conectar.assert_called_once_with(
            facturar.CACHE, facturar.URLS["homo"]["wsfev1"]
        )

    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_fallo_autenticacion_exit(self, MockWSAA, MockWSFEv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = ""  # falla

        with pytest.raises(SystemExit) as exc_info:
            facturar.autenticar(produccion=False)
        assert exc_info.value.code == 1

    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_retorna_wsfev1(self, MockWSAA, MockWSFEv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = "ticket"
        wsfev1 = MockWSFEv1.return_value
        wsfev1.AppServerStatus = "OK"
        wsfev1.DbServerStatus = "OK"
        wsfev1.AuthServerStatus = "OK"

        result = facturar.autenticar(produccion=True)
        assert result is wsfev1

    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_configura_cuit_y_ticket(self, MockWSAA, MockWSFEv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = "mi_ticket"
        wsfev1 = MockWSFEv1.return_value
        wsfev1.AppServerStatus = "OK"
        wsfev1.DbServerStatus = "OK"
        wsfev1.AuthServerStatus = "OK"

        facturar.autenticar(produccion=True)

        assert wsfev1.Cuit == facturar.CUIT
        wsfev1.SetTicketAcceso.assert_called_once_with("mi_ticket")


# =============================================================================
# 4. Emitir comprobante
# =============================================================================

class TestEmitirComprobante:
    @patch("facturar.datetime")
    def test_factura_exitosa(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        result = facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 2060038.06,
            "Consumidor Final", "Servicios - Abril 2026",
            "20260401", "20260430"
        )

        assert result["tipo_cbte"] == 11
        assert result["cbte_nro"] == 8  # ultimo(7) + 1
        assert result["cae"] == "86151425715928"
        assert result["monto"] == 2060038.06
        assert result["cliente"] == "Consumidor Final"

    @patch("facturar.datetime")
    def test_cbte_nro_es_ultimo_mas_uno(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        mock_wsfev1.CompUltimoAutorizado.return_value = "42"

        result = facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 1000,
            "Test", "Test", "20260401", "20260430"
        )
        assert result["cbte_nro"] == 43

    @patch("facturar.datetime")
    def test_fecha_venc_pago_10_dias(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        result = facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 1000,
            "Test", "Test", "20260401", "20260430"
        )
        assert result["fecha_venc_pago"] == "20260510"

    @patch("facturar.datetime")
    def test_nota_credito_agrega_cmp_asoc(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        facturar.emitir_comprobante(
            mock_wsfev1, facturar.NOTA_CREDITO_C, 1000,
            "Test", "Anulación", "20260401", "20260430",
            factura_asociada=5
        )

        mock_wsfev1.AgregarCmpAsoc.assert_called_once()
        args = mock_wsfev1.AgregarCmpAsoc.call_args
        assert args[1]["tipo"] == facturar.FACTURA_C
        assert args[1]["nro"] == 5

    @patch("facturar.datetime")
    def test_factura_sin_cmp_asoc(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 1000,
            "Test", "Test", "20260401", "20260430"
        )

        mock_wsfev1.AgregarCmpAsoc.assert_not_called()

    @patch("facturar.datetime")
    def test_error_afip_exit(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta
        mock_wsfev1.ErrMsg = "Error grave de AFIP"

        with pytest.raises(SystemExit) as exc_info:
            facturar.emitir_comprobante(
                mock_wsfev1, facturar.FACTURA_C, 1000,
                "Test", "Test", "20260401", "20260430"
            )
        assert exc_info.value.code == 1

    @patch("facturar.datetime")
    def test_rechazo_exit(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta
        mock_wsfev1.ErrMsg = ""
        mock_wsfev1.Resultado = "R"

        with pytest.raises(SystemExit) as exc_info:
            facturar.emitir_comprobante(
                mock_wsfev1, facturar.FACTURA_C, 1000,
                "Test", "Test", "20260401", "20260430"
            )
        assert exc_info.value.code == 1

    @patch("facturar.datetime")
    def test_guarda_en_registro(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 2060038.06,
            "Consumidor Final", "Servicios", "20260401", "20260430"
        )

        registro = facturar.cargar_registro()
        assert len(registro) == 1
        assert registro[0]["cae"] == "86151425715928"

    @patch("facturar.datetime")
    def test_parametros_crear_factura(self, mock_dt, mock_wsfev1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta

        facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 5000.50,
            "Test", "Desc", "20260401", "20260430",
            tipo_doc=80, nro_doc=30717509117, punto_vta=3
        )

        mock_wsfev1.CrearFactura.assert_called_once()
        kwargs = mock_wsfev1.CrearFactura.call_args[1]
        assert kwargs["concepto"] == facturar.CONCEPTO
        assert kwargs["tipo_doc"] == 80
        assert kwargs["nro_doc"] == 30717509117
        assert kwargs["tipo_cbte"] == facturar.FACTURA_C
        assert kwargs["punto_vta"] == 3
        assert kwargs["imp_total"] == 5000.50
        assert kwargs["imp_neto"] == 5000.50
        assert kwargs["imp_iva"] == 0.00
        assert kwargs["moneda_id"] == "PES"

    @patch("facturar.datetime")
    def test_con_observaciones(self, mock_dt, mock_wsfev1, tmp_facturas):
        """Las observaciones se imprimen pero no impiden autorización."""
        mock_dt.date.today.return_value.strftime.return_value = "20260413"
        mock_dt.datetime.strptime.return_value = datetime.datetime(2026, 4, 30)
        mock_dt.timedelta = datetime.timedelta
        mock_wsfev1.Obs = "10245: El campo Condicion Frente al IVA..."

        result = facturar.emitir_comprobante(
            mock_wsfev1, facturar.FACTURA_C, 1000,
            "Test", "Test", "20260401", "20260430"
        )
        assert result["cae"] == "86151425715928"


# =============================================================================
# 5. Generar PDF
# =============================================================================

class TestGenerarPDF:
    @patch("facturar.FEPDF")
    def test_produccion_sin_marca_agua(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value

        facturar.generar_pdf(sample_comprobante, produccion=True)

        fepdf.AgregarCampo.assert_not_called()

    @patch("facturar.FEPDF")
    def test_homologacion_con_marca_agua(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value

        facturar.generar_pdf(sample_comprobante, produccion=False)

        fepdf.AgregarCampo.assert_called_once()
        args = fepdf.AgregarCampo.call_args
        assert args[0][0] == "DEMO"
        # Verifica que también agrega dato de homologación
        datos_agregados = [c[0] for c in fepdf.AgregarDato.call_args_list]
        assert ("motivos_obs", "SIN VALIDEZ FISCAL - HOMOLOGACION") in datos_agregados

    @patch("facturar.FEPDF")
    def test_tipo_doc_cuit(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value
        sample_comprobante["tipo_doc"] = 80

        facturar.generar_pdf(sample_comprobante, produccion=True)

        kwargs = fepdf.CrearFactura.call_args[1]
        assert kwargs["id_impositivo"] == "CUIT"

    @patch("facturar.FEPDF")
    def test_tipo_doc_dni(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value
        sample_comprobante["tipo_doc"] = 96

        facturar.generar_pdf(sample_comprobante, produccion=True)

        kwargs = fepdf.CrearFactura.call_args[1]
        assert kwargs["id_impositivo"] == "DNI"

    @patch("facturar.FEPDF")
    def test_tipo_doc_consumidor_final(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value
        sample_comprobante["tipo_doc"] = 99

        facturar.generar_pdf(sample_comprobante, produccion=True)

        kwargs = fepdf.CrearFactura.call_args[1]
        assert kwargs["id_impositivo"] == "Consumidor Final"

    @patch("facturar.FEPDF")
    def test_pdf_path_factura(self, MockFEPDF, sample_comprobante, tmp_facturas):
        sample_comprobante["tipo_cbte"] = 11
        sample_comprobante["punto_vta"] = 3
        sample_comprobante["cbte_nro"] = 8

        result = facturar.generar_pdf(sample_comprobante, produccion=True)

        assert "FC-0003-00000008.pdf" in result

    @patch("facturar.FEPDF")
    def test_pdf_path_nota_credito(self, MockFEPDF, sample_comprobante, tmp_facturas):
        sample_comprobante["tipo_cbte"] = 13
        sample_comprobante["punto_vta"] = 3
        sample_comprobante["cbte_nro"] = 1

        result = facturar.generar_pdf(sample_comprobante, produccion=True)

        assert "NC-0003-00000001.pdf" in result

    @patch("facturar.FEPDF")
    def test_carga_plantilla(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value

        facturar.generar_pdf(sample_comprobante, produccion=True)

        fepdf.CargarFormato.assert_called_once()
        plantilla_path = fepdf.CargarFormato.call_args[0][0]
        assert plantilla_path.endswith("factura.csv")

    @patch("facturar.FEPDF")
    def test_detalle_item(self, MockFEPDF, sample_comprobante, tmp_facturas):
        fepdf = MockFEPDF.return_value

        facturar.generar_pdf(sample_comprobante, produccion=True)

        fepdf.AgregarDetalleItem.assert_called_once()
        kwargs = fepdf.AgregarDetalleItem.call_args[1]
        assert kwargs["codigo"] == "SRV"
        assert kwargs["ds"] == sample_comprobante["descripcion"]
        assert kwargs["precio"] == sample_comprobante["monto"]
        assert kwargs["importe"] == sample_comprobante["monto"]
        assert kwargs["qty"] == 1


# =============================================================================
# 6. Comandos CLI (integración con mocks)
# =============================================================================

class TestCmdFactura:
    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_factura_basica(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 11}

        args = argparse.Namespace(
            monto=1000000, cliente="Consumidor Final",
            descripcion="Servicios", desde="20260401", hasta="20260430",
            cuit_cliente=0, tipo_doc=99, punto_vta=3, produccion=True
        )
        facturar.cmd_factura(args)

        mock_auth.assert_called_once_with(True)
        mock_emitir.assert_called_once()
        mock_pdf.assert_called_once()

    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_factura_con_cuit_setea_tipo_doc_80(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 11}

        args = argparse.Namespace(
            monto=2468797, cliente="Wais SRL",
            descripcion="Desarrollo", desde="20260301", hasta="20260331",
            cuit_cliente=30717509117, tipo_doc=99, punto_vta=3, produccion=True
        )
        facturar.cmd_factura(args)

        emitir_args = mock_emitir.call_args
        assert emitir_args[0][4] == "Desarrollo"  # descripcion
        # tipo_doc should have been changed to 80
        assert args.tipo_doc == 80

    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_factura_sin_cuit_tipo_doc_99(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 11}

        args = argparse.Namespace(
            monto=1000, cliente="Consumidor Final",
            descripcion="Test", desde="20260401", hasta="20260430",
            cuit_cliente=0, tipo_doc=99, punto_vta=3, produccion=False
        )
        facturar.cmd_factura(args)

        assert args.tipo_doc == 99


class TestCmdNotaCredito:
    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_nota_credito_basica(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 13}

        args = argparse.Namespace(
            monto=1000, cliente="Test SRL",
            descripcion="Anulación FC 0003-00000001",
            desde="20260301", hasta="20260331",
            factura_asociada=1,
            cuit_cliente=0, tipo_doc=99, punto_vta=3, produccion=True
        )
        facturar.cmd_nota_credito(args)

        mock_emitir.assert_called_once()
        kwargs = mock_emitir.call_args
        # Verifica que pasa NOTA_CREDITO_C
        assert kwargs[0][1] == facturar.NOTA_CREDITO_C
        # Verifica factura_asociada
        assert kwargs[1]["factura_asociada"] == 1

    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_nota_credito_con_cuit(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 13}

        args = argparse.Namespace(
            monto=1000, cliente="Wais SRL",
            descripcion="Anulación", desde="20260301", hasta="20260331",
            factura_asociada=5, cuit_cliente=30717509117,
            tipo_doc=99, punto_vta=3, produccion=True
        )
        facturar.cmd_nota_credito(args)

        assert args.tipo_doc == 80


# =============================================================================
# 7. Listar
# =============================================================================

class TestCmdListar:
    def test_listar_vacio(self, tmp_facturas, capsys):
        args = argparse.Namespace()
        facturar.cmd_listar(args)
        output = capsys.readouterr().out
        assert "No hay comprobantes registrados" in output

    def test_listar_con_comprobantes(self, tmp_facturas, sample_comprobante, capsys):
        facturar.guardar_registro([sample_comprobante])
        args = argparse.Namespace()
        facturar.cmd_listar(args)
        output = capsys.readouterr().out
        assert "Factura C" in output
        assert "86151425715928" in output
        assert "Consumidor Final" in output
        assert "0003-00000008" in output


# =============================================================================
# 8. Consultar
# =============================================================================

class TestCmdConsultar:
    @patch("facturar.autenticar")
    def test_consultar_factura(self, mock_auth, mock_wsfev1, capsys):
        mock_auth.return_value = mock_wsfev1

        args = argparse.Namespace(
            numero=8, nota_credito=False, punto_vta=3, produccion=True
        )
        facturar.cmd_consultar(args)

        mock_wsfev1.CompConsultar.assert_called_once_with(
            facturar.FACTURA_C, 3, 8
        )
        output = capsys.readouterr().out
        assert "Factura C" in output
        assert "0003-00000008" in output

    @patch("facturar.autenticar")
    def test_consultar_nota_credito(self, mock_auth, mock_wsfev1, capsys):
        mock_auth.return_value = mock_wsfev1

        args = argparse.Namespace(
            numero=1, nota_credito=True, punto_vta=3, produccion=False
        )
        facturar.cmd_consultar(args)

        mock_wsfev1.CompConsultar.assert_called_once_with(
            facturar.NOTA_CREDITO_C, 3, 1
        )
        output = capsys.readouterr().out
        assert "Nota de Crédito C" in output


# =============================================================================
# 9. Parsing de argumentos (main)
# =============================================================================

class TestArgParsing:
    def _parse(self, args_list):
        """Helper: parsea argumentos sin ejecutar el comando."""
        with patch("sys.argv", ["facturar.py"] + args_list):
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest="comando", required=True)

            p_fac = subparsers.add_parser("factura")
            p_fac.add_argument("--monto", type=float, required=True)
            p_fac.add_argument("--cliente", required=True)
            p_fac.add_argument("--descripcion", required=True)
            p_fac.add_argument("--desde", required=True)
            p_fac.add_argument("--hasta", required=True)
            p_fac.add_argument("--cuit-cliente", type=int, default=0)
            p_fac.add_argument("--tipo-doc", type=int, default=99)
            p_fac.add_argument("--punto-vta", type=int, default=3)
            p_fac.add_argument("--produccion", action="store_true")

            p_nc = subparsers.add_parser("nota-credito")
            p_nc.add_argument("--monto", type=float, required=True)
            p_nc.add_argument("--cliente", required=True)
            p_nc.add_argument("--descripcion", required=True)
            p_nc.add_argument("--desde", required=True)
            p_nc.add_argument("--hasta", required=True)
            p_nc.add_argument("--factura-asociada", type=int, required=True)
            p_nc.add_argument("--cuit-cliente", type=int, default=0)
            p_nc.add_argument("--tipo-doc", type=int, default=99)
            p_nc.add_argument("--punto-vta", type=int, default=3)
            p_nc.add_argument("--produccion", action="store_true")

            return parser.parse_args(args_list)

    def test_factura_defaults(self):
        args = self._parse([
            "factura", "--monto", "1000", "--cliente", "Test",
            "--descripcion", "Desc", "--desde", "20260401", "--hasta", "20260430"
        ])
        assert args.comando == "factura"
        assert args.monto == 1000.0
        assert args.punto_vta == 3
        assert args.tipo_doc == 99
        assert args.cuit_cliente == 0
        assert args.produccion is False

    def test_factura_produccion(self):
        args = self._parse([
            "factura", "--monto", "5000", "--cliente", "Wais",
            "--descripcion", "Dev", "--desde", "20260301", "--hasta", "20260331",
            "--produccion", "--cuit-cliente", "30717509117"
        ])
        assert args.produccion is True
        assert args.cuit_cliente == 30717509117

    def test_nota_credito_parsing(self):
        args = self._parse([
            "nota-credito", "--monto", "1000", "--cliente", "Test",
            "--descripcion", "Anulación", "--desde", "20260401", "--hasta", "20260430",
            "--factura-asociada", "5"
        ])
        assert args.comando == "nota-credito"
        assert args.factura_asociada == 5

    def test_comando_requerido(self):
        with pytest.raises(SystemExit):
            self._parse([])


# =============================================================================
# 10. main() end-to-end (CLI completo con sys.argv)
# =============================================================================

class TestMainEndToEnd:
    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_main_factura(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 11}

        with patch("sys.argv", [
            "facturar.py", "factura",
            "--monto", "1000000",
            "--cliente", "Consumidor Final",
            "--descripcion", "Servicios - Abril 2026",
            "--desde", "20260401", "--hasta", "20260430",
            "--produccion",
        ]):
            facturar.main()

        mock_auth.assert_called_once_with(True)
        mock_emitir.assert_called_once()
        mock_pdf.assert_called_once()

    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_main_nota_credito(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 13}

        with patch("sys.argv", [
            "facturar.py", "nota-credito",
            "--monto", "1000",
            "--cliente", "Test",
            "--descripcion", "Anulación",
            "--desde", "20260401", "--hasta", "20260430",
            "--factura-asociada", "5",
            "--produccion",
        ]):
            facturar.main()

        mock_auth.assert_called_once_with(True)
        emitir_args = mock_emitir.call_args
        assert emitir_args[0][1] == facturar.NOTA_CREDITO_C
        assert emitir_args[1]["factura_asociada"] == 5

    def test_main_listar(self, tmp_facturas, sample_comprobante, capsys):
        facturar.guardar_registro([sample_comprobante])

        with patch("sys.argv", ["facturar.py", "listar"]):
            facturar.main()

        output = capsys.readouterr().out
        assert "Factura C" in output
        assert "86151425715928" in output

    @patch("facturar.autenticar")
    def test_main_consultar(self, mock_auth, mock_wsfev1, capsys):
        mock_auth.return_value = mock_wsfev1

        with patch("sys.argv", [
            "facturar.py", "consultar",
            "--numero", "8", "--produccion",
        ]):
            facturar.main()

        mock_wsfev1.CompConsultar.assert_called_once_with(facturar.FACTURA_C, 3, 8)

    def test_main_sin_comando_exit(self):
        with patch("sys.argv", ["facturar.py"]):
            with pytest.raises(SystemExit):
                facturar.main()

    @patch("facturar.generar_pdf")
    @patch("facturar.emitir_comprobante")
    @patch("facturar.autenticar")
    def test_main_factura_con_cuit(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 11}

        with patch("sys.argv", [
            "facturar.py", "factura",
            "--monto", "2468797",
            "--cliente", "Wais SRL",
            "--cuit-cliente", "30717509117",
            "--descripcion", "Desarrollo",
            "--desde", "20260301", "--hasta", "20260331",
        ]):
            facturar.main()

        emitir_args = mock_emitir.call_args[0]
        assert emitir_args[3] == "Wais SRL"  # cliente
        assert emitir_args[4] == "Desarrollo"  # descripcion


# =============================================================================
# 11. _load_env()
# =============================================================================

class TestLoadEnv:
    def test_load_env_no_file(self, tmp_path, monkeypatch):
        """Si no existe .env, no explota."""
        monkeypatch.setattr(facturar, "_load_env", lambda: None)
        # Simplemente verificar que el módulo carga sin .env

    def test_load_env_sets_vars(self, tmp_path):
        """_load_env carga variables al environ."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_PYARCA_VAR=hola\n# comentario\nOTRA=chau\n")

        # Simular _load_env apuntando al archivo
        with patch("facturar.os.path.dirname", return_value=str(tmp_path)):
            with patch("facturar.os.path.abspath", return_value=str(tmp_path / "facturar.py")):
                os.environ.pop("TEST_PYARCA_VAR", None)
                os.environ.pop("OTRA", None)
                facturar._load_env()

        assert os.environ.get("TEST_PYARCA_VAR") == "hola"
        assert os.environ.get("OTRA") == "chau"

        # Cleanup
        os.environ.pop("TEST_PYARCA_VAR", None)
        os.environ.pop("OTRA", None)


# =============================================================================
# 12. Factura E / NC E (exportación)
# =============================================================================

class TestAutenticarErrores:
    @patch("facturar.WSFEXv1")
    @patch("facturar.WSAA")
    def test_servicio_no_autorizado_mensaje_amigable(self, MockWSAA, MockWSFEXv1, capsys):
        from pysimplesoap.client import SoapFault
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.side_effect = SoapFault(
            "ns1:coe.notAuthorized", "Computador no autorizado a acceder al servicio"
        )

        with pytest.raises(SystemExit) as exc:
            facturar.autenticar(produccion=True, servicio="wsfex")
        assert exc.value.code == 1

        out = capsys.readouterr().out
        assert "Factura electronica de exportacion" in out
        assert "Administrador de Relaciones" in out

    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_cert_untrusted_mensaje_amigable(self, MockWSAA, MockWSFEv1, capsys):
        from pysimplesoap.client import SoapFault
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.side_effect = SoapFault(
            "ns1:cms.cert.untrusted", "Certificado no emitido por AC de confianza"
        )

        with pytest.raises(SystemExit) as exc:
            facturar.autenticar(produccion=False)
        assert exc.value.code == 1

        out = capsys.readouterr().out
        assert "homologación" in out

    @patch("facturar.WSFEv1")
    @patch("facturar.WSAA")
    def test_soap_fault_desconocido_se_propaga(self, MockWSAA, MockWSFEv1):
        from pysimplesoap.client import SoapFault
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.side_effect = SoapFault("ns1:foo.bar", "algo raro")

        with pytest.raises(SoapFault):
            facturar.autenticar(produccion=False)


class TestAutenticarWsfex:
    @patch("facturar.WSFEXv1")
    @patch("facturar.WSAA")
    def test_servicio_wsfex_usa_wsfexv1(self, MockWSAA, MockWSFEXv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = "ticket"
        ws = MockWSFEXv1.return_value
        ws.AppServerStatus = "OK"
        ws.DbServerStatus = "OK"
        ws.AuthServerStatus = "OK"

        result = facturar.autenticar(produccion=True, servicio="wsfex")

        wsaa.Autenticar.assert_called_once_with(
            "wsfex", facturar.CERT, facturar.PRIVATEKEY,
            wsdl=facturar.URLS["prod"]["wsaa"], cache=facturar.CACHE,
        )
        ws.Conectar.assert_called_once_with(
            facturar.CACHE, facturar.URLS["prod"]["wsfexv1"]
        )
        assert result is ws

    @patch("facturar.WSFEXv1")
    @patch("facturar.WSAA")
    def test_homologacion_wsfex(self, MockWSAA, MockWSFEXv1):
        wsaa = MockWSAA.return_value
        wsaa.Autenticar.return_value = "ticket"
        ws = MockWSFEXv1.return_value
        ws.AppServerStatus = "OK"
        ws.DbServerStatus = "OK"
        ws.AuthServerStatus = "OK"

        facturar.autenticar(produccion=False, servicio="wsfex")

        ws.Conectar.assert_called_once_with(
            facturar.CACHE, facturar.URLS["homo"]["wsfexv1"]
        )


class TestEmitirComprobanteE:
    @patch("facturar.datetime")
    def test_factura_e_exitosa(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        result = facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 1000.0,
            "Acme Inc", "50000000059",
            "Software services - April 2026",
            pais_destino=212, moneda="DOL", tipo_cambio=1180.0,
        )

        assert result["tipo_cbte"] == 19
        assert result["cbte_nro"] == 6              # ultimo(5) + 1
        assert result["cae"] == "86200000000001"
        assert result["pais_destino"] == 212
        assert result["moneda"] == "DOL"
        assert result["tipo_cambio"] == 1180.0
        assert result["nro_doc"] == "50000000059"

    @patch("facturar.datetime")
    def test_authorize_recibe_id_incremental(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"
        mock_wsfexv1.GetLastID.return_value = 42

        facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
            pais_destino=212, tipo_cambio=1.0,
        )

        mock_wsfexv1.Authorize.assert_called_once_with(43)

    @patch("facturar.datetime")
    def test_auto_fetch_cotizacion(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"
        mock_wsfexv1.GetParamCtz.return_value = "1234.56"

        result = facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
            pais_destino=212, moneda="DOL", tipo_cambio=None,
        )

        mock_wsfexv1.GetParamCtz.assert_called_once_with("DOL")
        assert result["tipo_cambio"] == 1234.56

    @patch("facturar.datetime")
    def test_cotizacion_invalida_exit(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"
        mock_wsfexv1.GetParamCtz.return_value = "no-es-un-numero"

        with pytest.raises(SystemExit) as exc:
            facturar.emitir_comprobante_e(
                mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
                pais_destino=212, moneda="DOL", tipo_cambio=None,
            )
        assert exc.value.code == 1

    @patch("facturar.datetime")
    def test_sin_cuit_pais_cliente_tipo_doc_99(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        result = facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "", "Desc",
            pais_destino=212, tipo_cambio=1.0,
        )

        assert result["tipo_doc"] == 99
        assert result["nro_doc"] == ""

    @patch("facturar.datetime")
    def test_domicilio_vacio_usa_no_declarado(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
            pais_destino=212, tipo_cambio=1.0,
        )

        kwargs = mock_wsfexv1.CrearFactura.call_args[1]
        assert kwargs["domicilio_cliente"] == "NO DECLARADO"

    @patch("facturar.datetime")
    def test_domicilio_provisto_se_respeta(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
            pais_destino=212, tipo_cambio=1.0,
            domicilio_cliente="123 Main St, NYC",
        )

        kwargs = mock_wsfexv1.CrearFactura.call_args[1]
        assert kwargs["domicilio_cliente"] == "123 Main St, NYC"

    @patch("facturar.datetime")
    def test_moneda_pes_no_consulta_cotizacion(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        result = facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
            pais_destino=212, moneda="PES", tipo_cambio=None,
        )

        mock_wsfexv1.GetParamCtz.assert_not_called()
        assert result["tipo_cambio"] == 1.0

    @patch("facturar.datetime")
    def test_nc_e_agrega_cmp_asoc(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.NOTA_CREDITO_E, 100.0, "X", "1", "Anulación",
            pais_destino=212, tipo_cambio=1.0, factura_asociada=7,
        )

        mock_wsfexv1.AgregarCmpAsoc.assert_called_once()
        kwargs = mock_wsfexv1.AgregarCmpAsoc.call_args[1]
        assert kwargs["cbte_tipo"] == facturar.FACTURA_E
        assert kwargs["cbte_nro"] == 7

    @patch("facturar.datetime")
    def test_error_afip_exit(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"
        mock_wsfexv1.ErrMsg = "Error grave"

        with pytest.raises(SystemExit) as exc:
            facturar.emitir_comprobante_e(
                mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
                pais_destino=212, tipo_cambio=1.0,
            )
        assert exc.value.code == 1

    @patch("facturar.datetime")
    def test_rechazo_exit(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"
        mock_wsfexv1.ErrMsg = ""
        mock_wsfexv1.Resultado = "R"

        with pytest.raises(SystemExit) as exc:
            facturar.emitir_comprobante_e(
                mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
                pais_destino=212, tipo_cambio=1.0,
            )
        assert exc.value.code == 1

    @patch("facturar.datetime")
    def test_guarda_en_registro(self, mock_dt, mock_wsfexv1, tmp_facturas):
        mock_dt.date.today.return_value.strftime.return_value = "20260506"

        facturar.emitir_comprobante_e(
            mock_wsfexv1, facturar.FACTURA_E, 100.0, "X", "1", "Desc",
            pais_destino=212, tipo_cambio=1.0,
        )

        registro = facturar.cargar_registro()
        assert len(registro) == 1
        assert registro[0]["tipo_cbte"] == 19


class TestCmdFacturaE:
    @patch("facturar.generar_pdf_e")
    @patch("facturar.emitir_comprobante_e")
    @patch("facturar.autenticar")
    def test_cmd_factura_e_basico(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 19}

        args = argparse.Namespace(
            monto=1000, cliente="Acme Inc",
            cuit_pais_cliente="50000000059",
            descripcion="Services", pais_destino=212,
            moneda="DOL", tipo_cambio=1180.0,
            incoterms="N/A", idioma=7,
            punto_vta=3, produccion=True,
        )
        facturar.cmd_factura_e(args)

        mock_auth.assert_called_once_with(True, servicio="wsfex")
        mock_emitir.assert_called_once()
        mock_pdf.assert_called_once()


class TestCmdNcE:
    @patch("facturar.generar_pdf_e")
    @patch("facturar.emitir_comprobante_e")
    @patch("facturar.autenticar")
    def test_cmd_nc_e_pasa_factura_asociada(self, mock_auth, mock_emitir, mock_pdf):
        mock_auth.return_value = Mock()
        mock_emitir.return_value = {"tipo_cbte": 21}

        args = argparse.Namespace(
            monto=1000, cliente="Acme Inc",
            cuit_pais_cliente="50000000059",
            descripcion="Anulación", pais_destino=212,
            moneda="DOL", tipo_cambio=1180.0,
            incoterms="N/A", idioma=7,
            punto_vta=3, produccion=True,
            factura_asociada=7,
        )
        facturar.cmd_nc_e(args)

        emitir_args = mock_emitir.call_args
        assert emitir_args[0][1] == facturar.NOTA_CREDITO_E
        assert emitir_args[1]["factura_asociada"] == 7


class TestGenerarPDFE:
    @pytest.fixture
    def sample_e(self):
        return {
            "tipo_cbte": 19,
            "tipo_nombre": "Factura E",
            "cbte_nro": 1,
            "cae": "86200000000001",
            "fch_venc_cae": "20260516",
            "fecha_cbte": "20260506",
            "punto_vta": 3,
            "monto": 1000.0,
            "cliente": "Acme Inc",
            "descripcion": "Software services",
            "tipo_doc": 80,
            "nro_doc": "50000000059",
            "pais_destino": 200,
            "moneda": "DOL",
            "tipo_cambio": 1180.50,
            "incoterms": "N/A",
            "idioma": 7,
        }

    @patch("facturar.FEPDF")
    def test_carga_plantilla_factura_e(self, MockFEPDF, sample_e, tmp_facturas):
        fepdf = MockFEPDF.return_value
        facturar.generar_pdf_e(sample_e, produccion=True)

        fepdf.CargarFormato.assert_called_once()
        plantilla = fepdf.CargarFormato.call_args[0][0]
        assert plantilla.endswith("factura_e.csv")

    @patch("facturar.FEPDF")
    def test_inyecta_datos_exportacion(self, MockFEPDF, sample_e, tmp_facturas):
        fepdf = MockFEPDF.return_value
        facturar.generar_pdf_e(sample_e, produccion=True)

        datos = dict(c[0] for c in fepdf.AgregarDato.call_args_list)
        assert datos["PaisDestino"] == "200"
        assert datos["Moneda"] == "DOL"
        assert "1180" in datos["Cotizacion"]
        assert datos["Incoterms"] == "N/A"

    @patch("facturar.FEPDF")
    def test_pdf_path_factura_e(self, MockFEPDF, sample_e, tmp_facturas):
        result = facturar.generar_pdf_e(sample_e, produccion=True)
        assert "FE-0003-00000001.pdf" in result

    @patch("facturar.FEPDF")
    def test_pdf_path_nc_e(self, MockFEPDF, sample_e, tmp_facturas):
        sample_e["tipo_cbte"] = 21
        result = facturar.generar_pdf_e(sample_e, produccion=True)
        assert "NE-0003-00000001.pdf" in result

    @patch("facturar.FEPDF")
    def test_id_impositivo_vacio_usa_cero(self, MockFEPDF, sample_e, tmp_facturas):
        fepdf = MockFEPDF.return_value
        sample_e["nro_doc"] = ""

        facturar.generar_pdf_e(sample_e, produccion=True)

        kwargs = fepdf.CrearFactura.call_args[1]
        assert kwargs["id_impositivo"] == "0"

    @patch("facturar.FEPDF")
    def test_homologacion_marca_agua(self, MockFEPDF, sample_e, tmp_facturas):
        fepdf = MockFEPDF.return_value
        facturar.generar_pdf_e(sample_e, produccion=False)
        fepdf.AgregarCampo.assert_called_once()
        args = fepdf.AgregarCampo.call_args
        assert args[0][0] == "DEMO"


class TestListarFacturaE:
    def test_listar_incluye_factura_e(self, tmp_facturas, capsys):
        comprobante_e = {
            "tipo_cbte": 19,
            "tipo_nombre": "Factura E",
            "cbte_nro": 1,
            "cae": "86200000000001",
            "fch_venc_cae": "20260516",
            "fecha_cbte": "20260506",
            "punto_vta": 3,
            "monto": 1000.0,
            "cliente": "Acme Inc",
            "descripcion": "Services",
            "tipo_doc": 80,
            "nro_doc": "50000000059",
        }
        facturar.guardar_registro([comprobante_e])

        args = argparse.Namespace()
        facturar.cmd_listar(args)
        output = capsys.readouterr().out

        assert "Factura E" in output
        assert "86200000000001" in output
        assert "Acme Inc" in output
