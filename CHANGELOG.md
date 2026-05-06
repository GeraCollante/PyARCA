# Changelog

Todas las entradas notables del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado [SemVer](https://semver.org/lang/es/).

## [Unreleased]

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

[Unreleased]: https://github.com/GeraCollante/PyARCA/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/GeraCollante/PyARCA/releases/tag/v0.1.0
