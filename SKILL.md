# Usar PyARCA con Claude Code

[Claude Code](https://claude.ai/claude-code) es el CLI de Anthropic para programar con Claude. Este repositorio está preparado para que Claude entienda el proyecto, emita facturas y te ayude a operar sin que tengas que explicarle todo cada vez.

## Qué es Claude Code

Claude Code es una herramienta que te permite hablar con Claude directamente desde la terminal. Claude puede leer archivos, ejecutar comandos, editar código y hacer commits. Es como tener un programador que entiende tu proyecto sentado al lado tuyo.

### Instalar Claude Code

```bash
# Con npm
npm install -g @anthropic-ai/claude-code

# Ejecutar en el directorio del proyecto
cd PyARCA
claude
```

Necesitás una cuenta de Anthropic con acceso a la API, o una suscripción Max/Pro.

Más info: [docs.anthropic.com/claude-code](https://docs.anthropic.com/en/docs/claude-code/overview)

## Cómo configurar Claude Code para este proyecto

### Paso 1: Crear tu CLAUDE.md

`CLAUDE.md` es un archivo en la raíz del proyecto que Claude lee automáticamente al iniciar cada sesión. Es **privado** (está en `.gitignore`) y contiene tus datos de facturación.

Copiá la plantilla y completala con tus datos:

```bash
cp docs/CLAUDE.md.example CLAUDE.md
# Editá CLAUDE.md con tus datos: CUIT, nombre, punto de venta, etc.
```

El archivo le dice a Claude:
- Quién sos (nombre, CUIT, domicilio, categoría de monotributo)
- Cómo usar el CLI con tus datos
- Reglas fiscales que aplican a tu caso
- Convenciones del proyecto (nombres de PDFs, estructura de carpetas)

Con esto, Claude puede emitir facturas con un simple "haceme una factura a consumidor final por $1M de abril" — sin que tengas que pasarle todos los parámetros cada vez.

### Paso 2: Configurar tu `.env`

Copiá la plantilla y completala con tus datos:

```bash
cp .env.example .env
# Editá .env con tus datos
```

El `.env` tiene tu CUIT, nombre, domicilio y datos del PDF. Está en `.gitignore`, nunca se sube al repo.

### Paso 3: Verificar

```bash
claude
> Consultame la última factura en producción
```

Si Claude puede conectarse a ARCA y traer datos, está todo OK.

## Memoria persistente

Claude Code mantiene memoria entre sesiones en `.claude/` (también en `.gitignore`). Esto le permite recordar:

- Apodos de clientes (ej. "Nacho" = Wais SRL)
- Preferencias de trabajo (ej. siempre usar `uv run`)
- Decisiones tomadas en sesiones anteriores

No necesitás hacer nada para que esto funcione — Claude guarda y recupera la memoria automáticamente.

## Ejemplos de lo que podés pedirle a Claude

### Facturación

```
> Haceme una factura a consumidor final por $2M de abril
> Facturale a [nombre del cliente] $2.5M por desarrollo de marzo
> Haceme una nota de crédito para anular la factura 11
> Cuánto facturé este mes?
> Listame todas las facturas
```

### Consultas

```
> Consultá la factura 8 en ARCA
> En qué categoría de monotributo estoy?
> Cuánto margen me queda antes de la próxima recategorización?
```

### Desarrollo

```
> Correme los tests
> Pasale ruff al código
> Agregá un test para el caso de factura con CUIT
```

## Limitaciones

- Claude **no puede** iniciar sesión en ARCA por vos (no maneja un browser)
- Claude **no puede** descargar PDFs del portal web de ARCA (solo genera PDFs localmente al emitir)
- El certificado digital tiene que estar configurado previamente
- Las operaciones contra ARCA son **irreversibles** — las facturas emitidas no se pueden borrar, solo anular con nota de crédito
