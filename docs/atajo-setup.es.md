# Atajo iOS — recrear desde cero

📖 **[Read in English](atajo-setup.md)**

Esta guía describe el Atajo "Sincronizar Entreno" para que cualquiera pueda reconstruirlo en su iPhone. **No commiteamos el `.shortcut` exportado** porque lleva el Bearer token embebido.

Tiempo estimado: 30-45 minutos la primera vez.

## Por qué reconstruirlo en vez de importarlo

El fichero `.shortcut` exportado desde iOS contiene cada valor literal de cada acción, incluyendo el Bearer token en las cabeceras HTTP. Importar el `.shortcut` de otro filtraría su token (y usar el tuyo requeriría reemplazarlo a mano, que es el mismo trabajo que construirlo desde cero).

## Modelo mental

El Atajo se ejecuta desde la **hoja de compartir** sobre una imagen de Bevel. Pregunta al usuario nombre/zapatillas/tags, codifica la imagen en base64 y hace POST JSON a tu `https://api.tudominio.com/sync-workout`.

## Paso a paso

### 1. Entrada

- `Recibir Apps e Imágenes de Hoja para compartir`
- `Si no hay datos de entrada: Continuar`

### 2. Menú "Nombre del entreno"

`Seleccionar en el menú con "Nombre del entreno"`, opciones según tus entrenos típicos:

| Opción | Contenido del caso |
|---|---|
| `60 S` (series en pista) | `Texto: 60 S` + `Definir variable nombre_entreno a Texto` |
| `12 km` | `Texto: 12 km` + `Definir variable nombre_entreno a Texto` |
| `Tirada Larga` | `Texto: Tirada Larga` + `Definir variable nombre_entreno a Texto` |
| `Otro (escribir)` | `Pedir Texto con "Nombre del entreno"` + `Definir variable nombre_entreno a Solicitud` |

Termina con `Terminar menú`. **NO** uses "Resultado del menú" después — con menús anidados se contamina. Define la variable explícitamente en cada caso.

### 3. Menú "Zapatillas"

Mismo patrón. Cada caso define `zapas` con el literal:

| Opción | Variable |
|---|---|
| Nombre corto Zapatilla A | `zapas = "Nombre corto Zapatilla A"` |
| Nombre corto Zapatilla B | `zapas = "Nombre corto Zapatilla B"` |
| Nombre corto Zapatilla C | `zapas = "Nombre corto Zapatilla C"` |

Los nombres pueden ser cortos: el dict `ALIASES` de `gear_map.py` en el servidor los traduce al canonical completo.

### 4. Tags

- `Crear lista`: Aeróbico, Base, Z2, Tirada Larga, Tempo, Series (o lo que uses).
- `Seleccionar en Lista` (activa "Permitir varios" si quieres multi-select).
- `Combinar Ítem seleccionado con ","`.
- `Definir variable tags_csv a Texto combinado`.

### 5. Imagen

- `Obtener archivo de tipo public.image de Entrada de atajo`.
- `Codificar imagen con base64` (en iOS Atajos la acción se llama "Codificar Base64" — la entrada debe ser `Archivo`).
- `Definir variable image_b64 a Texto codificado`.

### 6. Petición HTTP

`Obtener contenido de https://api.tudominio.com/sync-workout`

| Ajuste | Valor |
|---|---|
| Método | POST |
| Cabecera | `Authorization` = `Bearer <RUNSYNC_TOKEN>` |
| Cuerpo | JSON |

Campos JSON (todos tipo Texto):

| Clave | Valor |
|---|---|
| `name` | variable `nombre_entreno` |
| `shoes` | variable `zapas` |
| `tags` | variable `tags_csv` |
| `image_filename` | literal `Imagen.png` |
| `image_b64` | variable `image_b64` |
| `skip_telegram` | literal `false` (o `true` para no enviar a Telegram en una ejecución) |

### 7. Notificación de resultado (opcional)

- `Obtener Valor para "ok" en Contenido de URL`.
- `Si Valor del diccionario es/está Sí`  ← **¡importante!** en locale español el literal es `Sí` (con acento), no `verdadero`. iOS renderiza el booleano JSON `true` como el string localizado y compara strings.
  - `Mostrar notificación "runsync ✅"`.
- `Si no`
  - `Mostrar notificación "runsync ❌ {Valor del diccionario}"`.
- `Terminar si`.

### 8. (Opcional) Compartir manual al final

- `Compartir imagen_archivo` → abre la hoja de compartir de iOS, eliges WhatsApp / Telegram / etc.
- `Compartir <texto del caption>` → para el texto + #tags.

## Gotchas

- **`Definir variable` NO acepta texto literal** en el campo "a". Por eso cada caso usa el patrón `Texto + Definir variable`.
- **"Resultado del menú" se confunde con menús anidados.** Define la variable explícitamente en cada case body.
- **El campo `image` con tipo Archivo en peticiones form no funciona** fiable en iOS Atajos. Por eso usamos JSON + base64.
- **Booleanos en condiciones**: compara contra `Sí`/`No` (español) o `Yes`/`No` (inglés), no contra `verdadero`/`falso`.
- **Bearer token en cabecera**: no se commitea. Lo metes en el Atajo a mano.
- **iOS Atajos tiene varias formas de insertar variables** (selector de variable vs magic variable). Para archivos a veces hace falta el magic-variable (mantener pulsado el campo).

## Comprobación rápida de que funciona

Tras construirlo, ejecuta el Atajo sobre cualquier imagen (sirve un screenshot). Debería:

1. Mostrar el menú de nombre de entreno → eliges uno.
2. Mostrar el menú de zapatillas → eliges una.
3. Mostrar la lista de tags → eliges uno o varios.
4. Trabajar en silencio ~2 segundos.
5. Mostrar notificación `runsync ✅`.

Si ves `runsync ❌`, mira el JSON que sale en la pantalla previa (o añade temporalmente `Mostrar Contenido de URL` tras el HTTP) y revisa los errores por conector.

Si el JSON dice `ok=false` porque falló un conector concreto (ej. `"unknown gear: Mi Zapa"`), comprueba que `gear_map.py` en el servidor tiene esa zapatilla (con el canonical o un alias) y redespliega.
