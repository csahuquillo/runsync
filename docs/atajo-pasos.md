# Cómo arreglar el Atajo en iOS

> Editar el Atajo en la app **Atajos** del iPhone. Estos cambios son manuales en pantalla.

## 1) Arreglar `zapas` (zapatillas)

**Problema:** una acción "Definir variable zapas a Resultado del menú" está fuera del menú de zapatillas y captura el resultado del menú anterior (el del nombre del entreno).

**Pasos:**

1. Abrir el Atajo.
2. Buscar **cualquier** acción del tipo `Definir variable zapas a Resultado del menú` que esté **fuera** del menú "Zapatillas" → **borrarla**.
3. Dentro del menú `Seleccionar en el menú con "Zapatillas"`, en **cada caso** añadir una acción `Definir variable zapas a <texto>`:

```
Seleccionar en el menú con Zapatillas
  Adidas Boston 13
    Definir variable zapas a "Adidas Boston 13"
  New Balance More 5
    Definir variable zapas a "New Balance More 5"
  Under Armour Infinite Elite 2
    Definir variable zapas a "Under Armour Infinite Elite 2"
Terminar menú
```

4. Comprobar que en el formulario HTTP el campo `shoes` sigue apuntando a la **Variable** `zapas` (no a "Resultado del menú").

## 2) Arreglar `image` (forzar multipart/form-data)

**Problema:** si `image` se rellena con "Entrada de atajo" como texto, iOS no envía multipart.

**Pasos (antes de la acción `Obtener contenido de URL`):**

1. Añadir acción: **Obtener archivo de** → `Entrada de atajo`.
   - Tipo de archivo: imagen (o "Cualquiera" si no aparece).
2. Añadir acción: **Definir variable** → nombre `imagen_archivo`, valor = `Archivo` (la salida de la acción anterior).
3. En el formulario HTTP cambiar:
   - `image` → tipo **Archivo** (toca el campo y elige "Archivo", no "Texto") → seleccionar la variable `imagen_archivo`.

> Si el campo `image` aparece como Texto y no deja cambiarlo, borrarlo y volver a añadirlo eligiendo "Archivo".

## 3) Formulario HTTP final

```
URL:   https://api.sahuquillo.org/debug-form   (pruebas)
Método: POST
Solicitar: Formulario
Campos del formulario:
  name   (Texto)   = Variable nombre_entreno
  shoes  (Texto)   = Variable zapas
  tags   (Texto)   = Variable tags_csv
  image  (Archivo) = Variable imagen_archivo
```

## 4) Validar contra /debug-form

Ejecutar el Atajo desde la hoja de compartir de una imagen de Bevel. El resultado debe cumplir el JSON descrito en [AGENTS.md](../AGENTS.md). Si es OK, pasar al paso 5.

## 5) Cambiar a /sync-workout

1. Cambiar la URL del Atajo a `https://api.sahuquillo.org/sync-workout`.
2. Añadir cabecera `Authorization: Bearer <token>` (Carlos proporciona el token; no se guarda en este repo).

## 6) WhatsApp al final

Tras `Obtener contenido de URL` añadir:

1. `Compartir` → seleccionar `imagen_archivo` → destino WhatsApp.
2. `Compartir` → seleccionar el caption (texto) → destino WhatsApp.

(Se hace manualmente desde la hoja de Compartir; el Atajo solo abre el sheet.)
