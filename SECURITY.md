# Política de seguridad

PyARCA opera con material criptográfico sensible (claves privadas RSA, certificados digitales emitidos por ARCA) y emite comprobantes fiscales con consecuencias legales. Si encontrás una vulnerabilidad, te pedimos que la reportes de forma responsable.

## Cómo reportar

**No abras un issue público.** Mandá un mail a **geracollante95@gmail.com** con:

- Descripción del problema y su impacto.
- Pasos para reproducirlo.
- Versión afectada (commit SHA o tag).
- Cualquier mitigación temporal que se te ocurra.

Vas a recibir confirmación de recepción dentro de las 72 horas.

## Alcance

Reportes especialmente bienvenidos sobre:

- Manejo inseguro de claves privadas (`*.key`) o certificados (`*.crt`) — exposición en logs, paths predecibles, permisos laxos.
- Inyección de parámetros que termine en llamadas WSAA/WSFEv1 con datos de un tercero.
- Validación insuficiente de CUIT/montos que permita emitir comprobantes contra contribuyentes que no sean el operador.
- Dependencias con vulnerabilidades conocidas que afecten a PyARCA en su flujo principal.

Quedan **fuera de alcance**:

- Vulnerabilidades en `pyafipws` upstream — reportarlas en [github.com/reingart/pyafipws](https://github.com/reingart/pyafipws).
- Vulnerabilidades en los webservices de ARCA — son responsabilidad del organismo.
- Dependencias en módulos de la librería marcados como "no probados en producción" (ver Estado del proyecto en el README).

## Buenas prácticas para usuarios

- Nunca commitees `*.key`, `*.csr`, `mi_*.crt` ni `.env` — el `.gitignore` ya los excluye, pero verificá antes de pushear.
- Permisos mínimos en archivos sensibles: `chmod 600 mi_clave.key`.
- Rotá tu certificado antes del vencimiento (cada 2 años).
- Probá cambios contra **homologación** antes de tocar `--produccion`.
