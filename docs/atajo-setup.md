# iOS Shortcut — build from scratch

📖 **[Leer en español](atajo-setup.es.md)**

This document describes the "Sincronizar Entreno" Shortcut so anyone can rebuild it on their iPhone. **We do not commit the exported `.shortcut`** because it embeds your Bearer token.

Estimated time: 30-45 minutes the first time.

## Why rebuild it instead of importing

The `.shortcut` file exported from iOS contains every literal value of every action, including the Bearer token in the HTTP headers. Importing someone else's `.shortcut` would leak their token (and using your own would require manually replacing it, which is the same work as building from scratch).

## Mental model

The Shortcut runs from the **share sheet** on a Bevel image. It asks the user for name/shoes/tags, encodes the image to base64, and POSTs JSON to your `https://api.your-domain.com/sync-workout`.

## Step-by-step

### 1. Input

- `Receive Apps and Images from Share Sheet`
- `If there's no input: Continue`

### 2. Workout name menu

`Choose from menu "Workout name"`, with options matching what you usually run:

| Option | Case body |
|---|---|
| `60 S` (track intervals) | `Text: 60 S` + `Set variable nombre_entreno to Text` |
| `12 km` | `Text: 12 km` + `Set variable nombre_entreno to Text` |
| `Long run` | `Text: Long run` + `Set variable nombre_entreno to Text` |
| `Other (type)` | `Ask for Input: Text` with prompt "Workout name" + `Set variable nombre_entreno to Provided Input` |

End with `End menu`. **Do NOT** use "Menu Result" magic variable after the menu — with nested menus it gets confused. Define the variable explicitly inside each case.

### 3. Shoes menu

Same pattern. Each case sets `zapas` to the literal string:

| Option | Variable |
|---|---|
| Your Shoe A short name | `zapas = "Your Shoe A short name"` |
| Your Shoe B short name | `zapas = "Your Shoe B short name"` |
| Your Shoe C short name | `zapas = "Your Shoe C short name"` |

The names in the menu can be short — the `gear_map.py` ALIASES dict on the server maps them to the canonical full name.

### 4. Tags

- `List`: Aerobic, Base, Z2, Long, Tempo, Intervals (or whatever your tagging scheme is).
- `Choose from List` (toggle "Select Multiple" if you want multi-select).
- `Combine Selected Items with ","`.
- `Set variable tags_csv to Combined Text`.

### 5. Image

- `Get File from Shortcut Input of type public.image`.
- `Encode Image as base64` (action name in iOS Shortcuts is "Base64 Encode" — the input should be `File`).
- `Set variable image_b64 to Encoded Text`.

### 6. HTTP request

`Get Contents of https://api.your-domain.com/sync-workout`

| Setting | Value |
|---|---|
| Method | POST |
| Header | `Authorization` = `Bearer <RUNSYNC_TOKEN>` |
| Request Body | JSON |

JSON fields (all type Text):

| Key | Value |
|---|---|
| `name` | variable `nombre_entreno` |
| `shoes` | variable `zapas` |
| `tags` | variable `tags_csv` |
| `image_filename` | literal `Image.png` |
| `image_b64` | variable `image_b64` |
| `skip_telegram` | literal `false` (or `true` to skip Telegram on a given run) |

### 7. Notification (optional)

- `Get Dictionary Value for "ok" from Contents of URL`.
- `If Dictionary Value is Yes`  ← important: in English locale the literal is `Yes`, in Spanish locale it's `Sí`. iOS renders the JSON boolean `true` as the localized string and compares strings.
  - `Show Notification "runsync ✅"`.
- `Otherwise`
  - `Show Notification "runsync ❌ {Dictionary Value}"`.
- `End If`.

### 8. (Optional) Manual share at the end

- `Share imagen_archivo` → opens the system share sheet so you can pick WhatsApp / Telegram / wherever.
- `Share <caption text>` → for the text + #tags.

## Gotchas

- **`Set Variable` does not accept literal text** in the "to" field. That's why each case uses the pattern `Text + Set Variable`.
- **"Menu Result" gets confused with nested menus.** Define the variable explicitly in each case body.
- **The `image` field with type File in form requests** is not reliable in iOS Shortcuts. That's why we use JSON + base64.
- **Booleans in conditions**: compare against `Yes`/`No` (English) or `Sí`/`No` (Spanish), not against `true`/`false`.
- **Bearer token in the header**: never commit it. Put it in the Shortcut manually.
- **iOS Shortcuts has different ways to insert variables** (variable picker vs magic variable). For files, you sometimes need the magic-variable approach (long-press the field).

## Quick check that it works

After building, run the Shortcut on any image (a screenshot works). It should:

1. Show the workout name menu → pick one.
2. Show the shoes menu → pick one.
3. Show the tags list → pick one or several.
4. Run silently for ~2 seconds.
5. Show a notification `runsync ✅`.

If you see `runsync ❌`, look at the JSON shown in the previous screen (or temporarily add `Show Contents of URL` after the HTTP request) and check the per-connector errors.

If the JSON shows `ok=false` because one specific connector failed (e.g. `"unknown gear: My Shoe"`), make sure `gear_map.py` on the server has that shoe (with the canonical name or an alias) and redeploy.
