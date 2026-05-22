# Atajo iOS — recrear desde cero

Esta guía describe el Atajo "Sincronizar Entreno" para que cualquiera pueda reconstruirlo en su iPhone. **No commiteamos el `.shortcut` exportado** porque lleva el Bearer token embebido.

## Resumen

El Atajo se ejecuta desde la **hoja de compartir** sobre una imagen exportada de Bevel. Pregunta nombre/zapatillas/tags al usuario, codifica la imagen en base64 y hace POST JSON a `https://api.sahuquillo.org/sync-workout`.

## Estructura completa

### 1. Entrada
- `Recibir Apps e Imágenes de Hoja para compartir`
- `Si no hay datos de entrada: Continuar`

### 2. Menú "Nombre del entreno"

`Seleccionar en el menú con "Nombre del entreno"`, opciones:

| Opción | Contenido del caso |
|---|---|
| 60 S | `Texto: 60 S` + `Definir variable nombre_entreno a Texto` |
| 12 km | `Texto: 12 km` + `Definir variable nombre_entreno a Texto` |
| Tirada Larga | `Texto: Tirada Larga` + `Definir variable nombre_entreno a Texto` |
| Otro (escribir) | `Pedir Texto con "Nombre del entreno"` + `Definir variable nombre_entreno a Solicitud` |

Termina con `Terminar menú`. **No** uses "Resultado del menú" después — al haber menús anidados se contamina.

### 3. Menú "Zapatillas"

Mismo patrón. Cada caso define `zapas` con el literal correspondiente:

| Opción | Variable |
|---|---|
| Under Armour Elite 2 | `zapas = "Under Armour Elite 2"` (alias en backend → Under Armour Infinite Elite 2) |
| NB More v5 | `zapas = "NB More v5"` (alias → New Balance More 5) |
| Adidas Boston 13 | `zapas = "Adidas Boston 13"` |

Los nombres pueden ser cortos: el `gear_map.py` del servidor tiene aliases.

### 4. Tags

- `Crear lista`: Aeróbico, Base, Z2, Tirada Larga, Tempo, Series
- `Seleccionar en Lista` (con "Permitir varios" si quieres multi-select)
- `Combinar Ítem seleccionado con ","`
- `Definir variable tags_csv a Texto combinado`

### 5. Imagen

- `Obtener archivo de tipo public.image de Entrada de atajo`
- `Codificar imagen_archivo con base64` (donde `imagen_archivo` apunta a la salida anterior, o directamente la magic variable `Archivo del tipo`)
- `Definir variable image_b64 a Texto codificado`

### 6. Petición HTTP

`Obtener contenido de https://api.sahuquillo.org/sync-workout`

| Opción | Valor |
|---|---|
| Método | POST |
| Cabecera | `Authorization` = `Bearer <RUNSYNC_TOKEN>` |
| Cuerpo | JSON |

**Campos del cuerpo JSON** (todos tipo Texto):

| Clave | Valor |
|---|---|
| name | variable `nombre_entreno` |
| shoes | variable `zapas` |
| tags | variable `tags_csv` |
| image_filename | literal `Imagen.png` |
| image_b64 | variable `image_b64` |
| skip_telegram | literal `false` (o `true` para no enviar a Telegram) |

### 7. Notificación de resultado (opcional)

- `Obtener Valor para "ok" en Contenido de URL`
- `Si Valor del diccionario es/está Sí` (¡con acento! es el booleano `true` localizado al castellano)
  - `Mostrar notificación "runsync ✅"`
- `Si no`
  - `Mostrar notificación "runsync ❌ {Valor del diccionario}"`
- `Terminar si`

**Importante:** la comparación tiene que ser contra `Sí`, no contra `verdadero`. iOS Atajos en español renderiza los booleanos JSON como `Sí`/`No` y compara strings.

### 8. (Opcional) Compartir manual al final
- `Compartir imagen_archivo` → usuario elige WhatsApp / Telegram / lo que sea.
- `Compartir <caption>` → para mandar texto + #tags a otro destino.

## Gotchas

- **`Definir variable` no acepta texto literal** en el campo "a". Por eso cada opción del menú usa el patrón `Texto + Definir variable`.
- **`Resultado del menú` se confunde con menús anidados.** Define la variable explícitamente en cada caso.
- **El campo `image` con tipo Archivo en el formulario no funciona** fiable en iOS Atajos. Por eso JSON + base64.
- **Booleanos en condiciones**: compara contra `Sí`/`No`, no contra `verdadero`/`falso`.
- **Bearer token en cabecera**: no se guarda en el repo. Ponlo en el Atajo manualmente.

## Recursos

- [docs/atajo-pasos.md](atajo-pasos.md): guía interactiva paso a paso de los arreglos típicos cuando algo va mal.
