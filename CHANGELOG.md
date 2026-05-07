# Changelog

Todas las entradas notables del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado [SemVer](https://semver.org/lang/es/).

## [Unreleased]

## [0.2.0] - 2026-05-07

### Agregado
- Soporte para **Factura E** (tipo 19) y **Nota de Crédito E** (tipo 21) — exportación de servicios contra **WSFEXv1**.
- Subcomandos `factura-e` y `nota-credito-e` en el CLI con flags propios: `--pais-destino`, `--cuit-pais-cliente`, `--moneda`, `--tipo-cambio` (auto-fetch desde ARCA si falta), `--incoterms`, `--idioma`.
- Plantilla PDF nueva `plantillas/factura_e.csv` adaptada a exportación (sin IVA, con país, moneda, cotización e INCOTERMS).
- Refactor de `autenticar()` para aceptar `servicio="wsfe"` (default, mercado interno) o `servicio="wsfex"` (exportación). Backwards compatible.
- Mensajes de error amigables en `autenticar()` cuando el servicio no está habilitado en ARCA o el certificado no corresponde al ambiente.

### Corregido
- **Códigos de país en docs y ejemplos**: la tabla del README y los ejemplos del CLI tenían los códigos de país equivocados (eran provincias / códigos desplazados). Ahora coinciden con la tabla oficial AFIP — `212`=USA (no 200), `438`=Alemania (no 218), `225`=Uruguay (no 438), etc. La verdad se obtiene siempre con `wsfexv1.GetParamDstPais()` en runtime; las constantes hardcodeadas son solo referencia rápida.

## [0.1.0] - 2026-05-06

Primera release pública del fork. El CLI de facturación (`facturar.py`) está testeado y probado en producción para Facturas C y Notas de Crédito C de Monotributo (concepto Servicios). El resto de la librería está reorganizado y sin probar.

### Agregado
- CLI `facturar.py` para emitir Facturas C y Notas de Crédito C contra ARCA desde la terminal.
- Tutorial paso a paso para obtener el certificado digital, con capturas de pantalla del flujo en ARCA.
- Reorganización de `src/pyafipws/` en subpaquetes (`facturacion/`, `agricultura/`, `trazabilidad/`, `remitos/`, `padron/`, `provincial/`, `pdf/`, `cli/`, `formatos/`).
- Tooling moderno: `uv` (package manager), `ruff` (lint), `pytest` con coverage en Codecov.
- CI en GitHub Actions: Ruff + tests en Python 3.9 / 3.10 / 3.11 con cobertura.
- Review automatizado de PRs con [Qodo PR-Agent](https://github.com/The-PR-Agent/pr-agent) sobre DeepSeek V4-Flash.
- Optimización para [Claude Code](https://claude.ai/claude-code) (ver `SKILL.md`).
- Documentación de seguridad (`SECURITY.md`), contribución (`CONTRIBUTING.md`) y templates de issue/PR.

### Heredado
- Toda la librería de webservices de ARCA/AFIP de [pyafipws](https://github.com/reingart/pyafipws) creada por **Mariano Reingart**.

[Unreleased]: https://github.com/GeraCollante/PyARCA/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/GeraCollante/PyARCA/releases/tag/v0.2.0
[0.1.0]: https://github.com/GeraCollante/PyARCA/releases/tag/v0.1.0
