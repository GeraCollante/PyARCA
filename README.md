<p align="center">
  <img src="docs/logo.png" alt="PyARCA" width="300">
</p>

<h1 align="center">PyARCA</h1>

<p align="center">
  <a href="https://github.com/GeraCollante/PyARCA/actions/workflows/ci.yml"><img src="https://github.com/GeraCollante/PyARCA/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/GeraCollante/PyARCA"><img src="https://codecov.io/gh/GeraCollante/PyARCA/branch/main/graph/badge.svg" alt="Coverage"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11-blue.svg" alt="Python 3.9+"></a>
  <a href="COPYING.LESSER"><img src="https://img.shields.io/badge/license-LGPL--3.0--or--later-green.svg" alt="License: LGPL v3"></a>
  <a href="https://docs.astral.sh/ruff/"><img src="https://img.shields.io/badge/linting-ruff-261230.svg" alt="Linting: ruff"></a>
  <a href="https://docs.astral.sh/uv/"><img src="https://img.shields.io/badge/uv-package%20manager-blueviolet.svg" alt="uv"></a>
  <a href="SKILL.md"><img src="https://img.shields.io/badge/Claude%20Code-optimized-ff6600.svg" alt="Claude Code"></a>
</p>

CLI para emitir **Facturas C** y **Notas de Crédito C** (Monotributo) contra ARCA (ex-AFIP) desde la terminal. Construido sobre [pyafipws](https://github.com/reingart/pyafipws), la librería de webservices de AFIP creada por **Mariano Reingart**.

Este repositorio está optimizado para [Claude Code](https://claude.ai/claude-code) — con una configuración mínima, Claude puede emitir facturas, consultar comprobantes y operar el CLI en lenguaje natural. Ver [SKILL.md](SKILL.md) para configurarlo.

> **Estado del proyecto:** El CLI de facturación (`facturar.py`) está **testeado y probado en producción** para emisión de Facturas C y Notas de Crédito C de Monotributo (concepto Servicios). Los demás módulos de la librería (facturación A/B, comercio exterior, agricultura, trazabilidad, remitos, etc.) fueron reorganizados y limpiados a nivel de código, pero **no fueron probados en la vida real** por el autor de este fork. El repositorio está abierto a PRs de quienes quieran probar, corregir o extender esos módulos.

---

## Inicio rápido

```bash
# 1. Instalar uv (si no lo tenés)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clonar e instalar
git clone <repo-url> && cd PyARCA
uv sync --extra dev

# 3. Emitir una factura (necesitás certificado digital, ver abajo)
uv run python facturar.py factura \
    --monto 1000000 \
    --cliente "Consumidor Final" \
    --descripcion "Servicios de desarrollo de software - Abril 2026" \
    --desde 20260401 --hasta 20260430 \
    --produccion
```

---

## 📋 Guía completa: configurar facturación electrónica desde cero

Para emitir facturas electrónicas necesitás 4 cosas:
1. 🔑 **Clave fiscal nivel 3+** en ARCA (ex-AFIP)
2. 📜 **Certificado digital** (clave privada + certificado firmado por ARCA)
3. 🔗 **Servicio de facturación electrónica** habilitado
4. 🏪 **Punto de venta** configurado para Web Services

Todo esto se hace una sola vez. El certificado dura 2 años.

### 🔐 Paso 1: Generar la clave privada y el pedido de certificado (CSR)

La clave privada es como la contraseña de tu facturación. **Se queda en tu máquina y nunca la compartís con nadie.**

Abrí una terminal y ejecutá:

```bash
# 1. Generar clave privada RSA de 2048 bits
openssl genrsa -out mi_clave.key 2048

# 2. Generar el pedido de certificado (CSR)
#    Reemplazá con tu nombre y CUIT (sin guiones)
openssl req -new -key mi_clave.key \
    -subj "/CN=facturacion/O=TU NOMBRE COMPLETO/serialNumber=CUIT 20XXXXXXXXX" \
    -out mi_pedido.csr
```

Ejemplo:
```bash
openssl req -new -key mi_clave.key \
    -subj "/CN=facturacion/O=JUAN PEREZ/serialNumber=CUIT 20123456789" \
    -out mi_pedido.csr
```

> **¿No tenés OpenSSL?** En Linux ya viene instalado. En Mac también (`brew install openssl` si no). En Windows podés usar Git Bash o WSL.

Ahora tenés dos archivos:
- `mi_clave.key` — tu clave privada (**SECRETA**, no la subas a ningún lado)
- `mi_pedido.csr` — el pedido que vas a subir a ARCA en el paso siguiente

### 🌐 Paso 2: Habilitar el servicio "Administración de Certificados Digitales"

1. Entrá a [https://auth.afip.gob.ar/contribuyente/](https://auth.afip.gob.ar/contribuyente/) con tu CUIT y clave fiscal
2. En el menú principal, buscá **"Administrador de Relaciones de Clave Fiscal"**
3. Hacé click en **"Adherir servicio"**
4. Navegá: **ARCA** → **Servicios Interactivos** → **Administración de Certificados Digitales**
5. Confirmá

<!-- TODO: screenshot del menú de servicios de ARCA -->
<!-- ![Adherir servicio](docs/screenshots/paso2-adherir-servicio.png) -->

### 📤 Paso 3: Crear el alias y subir el certificado

1. Volvé al menú principal de ARCA y entrá a **"Administración de Certificados Digitales"**
2. Vas a ver una pantalla con tus certificados (probablemente vacía)
3. Hacé click en **"Agregar alias"**
   - Nombre del alias: `facturacion` (o el que quieras, es solo un identificador)
   - Confirmá
4. En el alias que acabás de crear, hacé click en **"Agregar certificado"**
5. Seleccioná el archivo `mi_pedido.csr` que generaste en el Paso 1
6. Confirmá y **descargá el certificado** (archivo `.crt`)
7. Guardá el `.crt` como `mi_certificado.crt` en la carpeta del proyecto

<!-- TODO: screenshot de la pantalla de certificados -->
<!-- ![Agregar certificado](docs/screenshots/paso3-agregar-certificado.png) -->

> **Importante:** El archivo `.crt` que descargás es el certificado firmado por ARCA. Junto con tu `mi_clave.key`, forman el par necesario para autenticarte. Uno sin el otro no sirve.

### 🔗 Paso 4: Habilitar el servicio de Facturación Electrónica

1. Volvé al menú principal de ARCA
2. Entrá a **"Administrador de Relaciones de Clave Fiscal"**
3. Hacé click en **"Nueva Relación"**
4. Navegá por las opciones:
   - **Representante:** vos mismo (tu CUIT)
   - **Servicio:** **ARCA** → **WebServices** → **Facturación Electrónica**
5. Te va a pedir que selecciones un **Computador Fiscal** — elegí el alias que creaste (ej. `facturacion`)
6. Confirmá

<!-- TODO: screenshot de nueva relación -->
<!-- ![Nueva relación](docs/screenshots/paso4-nueva-relacion.png) -->

> **¿Por qué dice "Computador Fiscal"?** Es la forma que tiene ARCA de vincular tu certificado digital con un servicio específico. Tu "computador fiscal" es tu máquina/servidor que va a firmar las facturas.

### 🏪 Paso 5: Crear el punto de venta

El punto de venta es el número que aparece al inicio de tus facturas (ej. **0003**-00000001). Necesitás uno configurado para Web Services.

1. Desde el menú principal de ARCA, buscá **"ABM de Puntos de Venta"**
   - Si no lo encontrás, entrá por **"Facturación Electrónica"** → **"ABM de Puntos de Venta"**
2. Hacé click en **"Agregar"**
3. Completá:
   - **Sistema:** RCEL - Factura Electrónica - Web Services
   - **Número:** el que quieras (ej. `3`). Si ya tenés puntos de venta del portal web, usá uno nuevo
4. Confirmá

<!-- TODO: screenshot del ABM de puntos de venta -->
<!-- ![ABM Puntos de Venta](docs/screenshots/paso5-punto-de-venta.png) -->

> **Ojo:** El punto de venta del portal web (Factura en Línea) **no es el mismo** que el de Web Services. Si ya facturás por el portal con el punto de venta 1, creá el punto de venta 3 (o el que quieras) para Web Services.

### ⚙️ Paso 6: Configurar PyARCA

Copiá la plantilla de configuración y editala con tus datos:

```bash
cp .env.example .env
```

Editá `.env`:
```env
CUIT=20123456789
CERT=mi_certificado.crt
PRIVATEKEY=mi_clave.key
EMPRESA=JUAN PEREZ
MEMBRETE1=Av. Siempreviva 742, Springfield
MEMBRETE2=C.P. 1234 - Buenos Aires
CUIT_FMT=CUIT 20-12345678-9
IIBB=Exento
IVA=Responsable Monotributo
INICIO=Inicio de Actividad: 01/01/2020
```

### ✅ Paso 7: Verificar que todo funciona

```bash
# Consultar el último comprobante autorizado
uv run python facturar.py consultar --numero 1 --produccion
```

Si ves datos del comprobante, **está todo configurado**. Si da error:

| Error | Causa | Solución |
|-------|-------|----------|
| `No se pudo autenticar contra WSAA` | Certificado no válido o no asociado | Revisá los pasos 3 y 4 |
| `Conexión AFIP: Auth=NO` | El servicio no está habilitado | Revisá el paso 4 (Nueva Relación) |
| `Comprobante no encontrado` | No hay facturas emitidas aún | Normal si es un punto de venta nuevo |

### 📁 Resumen de archivos

```
mi_clave.key        # 🔒 Clave privada (SECRETA, generada en Paso 1)
mi_certificado.crt  # 📜 Certificado digital (descargado de ARCA en Paso 3)
mi_pedido.csr       # 📋 Pedido de certificado (ya no lo necesitás)
.env                # ⚙️  Configuración con tus datos (Paso 6)
```

Todos estos archivos están en `.gitignore` — **nunca van a quedar en el repositorio**.

---

## Uso del CLI

### Factura a consumidor final

```bash
uv run python facturar.py factura \
    --monto 1000000 \
    --cliente "Consumidor Final" \
    --descripcion "Servicios de desarrollo de software - Abril 2026" \
    --desde 20260401 --hasta 20260430 \
    --produccion
```

### Factura con CUIT del cliente

```bash
uv run python facturar.py factura \
    --monto 2468797 \
    --cliente "Empresa SRL" \
    --cuit-cliente 30712345678 \
    --descripcion "Desarrollo de software" \
    --desde 20260301 --hasta 20260331 \
    --produccion
```

### Nota de crédito (anulación)

```bash
uv run python facturar.py nota-credito \
    --monto 1000000 \
    --cliente "Consumidor Final" \
    --descripcion "Anulacion FC 0003-00000005" \
    --desde 20260301 --hasta 20260331 \
    --factura-asociada 5 \
    --produccion
```

### Listar comprobantes emitidos

```bash
uv run python facturar.py listar
```

### Consultar comprobante en ARCA

```bash
uv run python facturar.py consultar --numero 1 --produccion
uv run python facturar.py consultar --numero 1 --nota-credito --produccion
```

Sin `--produccion`, opera contra homologación (requiere certificado de testing).

### Opciones

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--monto` | Importe total en pesos | (requerido) |
| `--cliente` | Nombre del cliente | (requerido) |
| `--descripcion` | Detalle del servicio | (requerido) |
| `--desde` / `--hasta` | Período del servicio (YYYYMMDD) | (requerido) |
| `--cuit-cliente` | CUIT del cliente (si no es consumidor final) | 0 |
| `--tipo-doc` | Tipo de documento (80=CUIT, 96=DNI, 99=CF) | 99 |
| `--punto-vta` | Punto de venta | 3 |
| `--produccion` | Operar contra ARCA producción | homologación |
| `--factura-asociada` | Nro. de factura a anular (solo NC) | - |

---

## Tipos de comprobante

| Tipo | Código | Descripción |
|------|--------|-------------|
| Factura C | 11 | Monotributo, no discrimina IVA |
| Nota de Crédito C | 13 | Anulación/ajuste de facturas |

Concepto **2 (Servicios)** — requiere período desde/hasta.

Para facturas a consumidor final menores a $10M, no se requiere identificación del receptor (RG 5700/2025).

---

## Tests

```bash
uv run pytest tests/test_facturar.py -v    # 48 tests del CLI (100% mockeado, sin conexión a ARCA)
uv run pytest tests/ -v                     # suite completa (requiere cert de homologación)
```

## Linting

```bash
uv run ruff check .                         # verificar
uv run ruff check . --fix                   # auto-fix
```

Reglas activas: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `UP` (pyupgrade), `B006` (bugbear).

---

## Estructura del proyecto

```
PyARCA/
├── facturar.py                  # CLI de facturación (entrada principal)
├── pyproject.toml               # Configuración (deps, ruff, pytest)
├── uv.lock                      # Lockfile de dependencias
│
├── src/pyafipws/                # Librería (nombre interno del paquete)
│   ├── __init__.py              # Re-exports lazy para retrocompatibilidad
│   ├── wsaa.py                  # Autenticación WSAA (core)
│   ├── utils.py                 # Utilidades compartidas (core)
│   │
│   ├── facturacion/             # Factura electrónica
│   │   ├── wsfev1.py            #   Mercado interno (WSFEv1)
│   │   ├── wsfexv1.py           #   Comercio exterior (WSFEXv1)
│   │   ├── wsbfev1.py           #   Bono fiscal (WSBFEv1)
│   │   ├── wsmtx.py             #   Multi-artículo (WSMTXCA)
│   │   ├── wsct.py              #   Turismo (WSCT)
│   │   ├── wscdc.py             #   Constatación de comprobantes
│   │   └── wsfecred.py          #   Factura de crédito electrónica
│   │
│   ├── agricultura/             # Agricultura y ganadería
│   │   ├── wsctg.py             #   Trazabilidad de granos
│   │   ├── wslpg.py             #   Liquidación primaria de granos
│   │   ├── wslsp.py             #   Liquidación de hacienda
│   │   ├── wsltv.py             #   Tabaco verde
│   │   └── wslum.py             #   Leche
│   │
│   ├── trazabilidad/            # Trazabilidad (ANMAT/SENASA)
│   │   ├── trazamed.py          #   Medicamentos
│   │   ├── trazafito.py         #   Fitosanitarios
│   │   └── ...                  #   Productos médicos, precursores, veterinarios
│   │
│   ├── remitos/                 # Remitos electrónicos (carne, harina, azúcar, CPE)
│   ├── padron/                  # Padrón de contribuyentes (CUIT, SIRED)
│   ├── provincial/              # Servicios provinciales (COT, IIBB)
│   ├── pdf/                     # Generación de PDF, QR, código de barras
│   ├── cli/                     # Interfaces CLI legacy (rece1, receb1, etc.)
│   └── formatos/                # Parsers (CSV, TXT, XML, JSON, DBF, SQL)
│
├── tests/                       # Suite de tests (pytest + VCR cassettes)
├── docs/                        # Documentación y plantillas
├── conf/                        # Certificados CA y configs de servicios
├── plantillas/                  # Templates CSV para generación de PDF
├── ejemplos/                    # Ejemplos en Python, VB, C#, PHP, Java, etc.
└── datos/                       # Datos de referencia
```

---

## Webservices soportados

| Dominio | Servicios |
|---------|-----------|
| **Facturación** | WSFEv1, WSFEXv1, WSBFEv1, WSMTXCA, WSCT, WSCDC, WSFECred |
| **Agricultura** | WSCTG, WSLPG, WSLSP, WSLTV, WSLUM |
| **Trazabilidad** | TrazaMed, TrazaFito, TrazaProdMed, TrazaRenpre, TrazaVet |
| **Remitos** | WSRemCarne, WSRemHarina, WSRemAzucar, WSCPE |
| **Padrón** | WS_SR_Padron, Padron, SIRED |
| **Provincial** | COT (ARBA), IIBB, RG3685 |
| **Auth** | WSAA (firma digital, tickets de acceso) |

Documentación completa de la librería: [wiki de pyafipws](https://github.com/reingart/pyafipws/wiki)

---

## Contribuir

Este fork se enfoca en facturación Monotributo (Factura C / NC C). Los demás módulos de la librería están reorganizados y limpios, pero no fueron probados en producción.

Si usás alguno de los otros webservices (comercio exterior, agricultura, trazabilidad, etc.) y querés contribuir con tests o fixes, los PRs son bienvenidos.

### Flujo de trabajo

1. Crear un branch desde `main` (`feat/mi-cambio`, `fix/mi-fix`)
2. Hacer los cambios y verificar que pasen los checks:
   ```bash
   uv run ruff check .
   uv run pytest tests/test_facturar.py --cov -q
   ```
3. Abrir un PR contra `main` — CI corre automáticamente (ruff + tests + coverage)
4. No se pushea directo a `main`

## Créditos

La totalidad de la librería de webservices de ARCA/AFIP fue creada por **Mariano Reingart** (reingart@gmail.com) y es mantenida por la comunidad en [github.com/reingart/pyafipws](https://github.com/reingart/pyafipws).

Este fork agrega el CLI de facturación (`facturar.py`), reorganiza la estructura en subpaquetes, moderniza el tooling (uv, ruff, pyproject.toml) y corrige errores estáticos del código. Todo el trabajo sobre la librería base se apoya íntegramente en el código original de Reingart.

## Licencia

Este proyecto mantiene la licencia original: [LGPL-3.0-or-later](COPYING.LESSER).

Esto significa que podés usar, modificar y redistribuir el código, incluso en proyectos propietarios, siempre que:
- Mantengas la misma licencia para las modificaciones a la librería
- Incluyas el aviso de copyright original
- Distribuyas el código fuente de tus modificaciones

Ver [COPYING](COPYING) y [COPYING.LESSER](COPYING.LESSER) para el texto completo.
