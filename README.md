# Chechenia

Checker de **primera parte**: comprueba si un email ya está registrado en **tu** aplicación.

No es un checker de Spotify ni de ningún servicio ajeno. El motor solo acepta un endpoint JSON propio, exige una admin key y bloquea hosts de plataformas de terceros.

## Qué incluye

1. **App demo** (`app/server.py`) con:
   - `POST /auth/register` — alta de usuarios
   - `GET /admin/users/exists?email=` — ¿este correo ya existe?
   - SQLite local en `data/users.db`
2. **Checker GUI** (`run_checker.py`) — carga una lista, muestra registrados / libres / inválidos / errores y exporta resultados.
3. **Checker CLI** (`python -m checker.cli`)

Contrato del endpoint que el checker espera:

```json
{
  "email": "ana@chechenia.local",
  "registered": true,
  "valid_format": true
}
```

Si la respuesta no es JSON con `registered`, se marca como error. Así no se puede reutilizar contra páginas HTML de signup de terceros.

## Arranque local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Terminal 1 — tu app:

```bash
python run_app.py
```

Queda en `http://127.0.0.1:8787`. La demo crea tres cuentas:

- `ana@chechenia.local`
- `carlos@chechenia.local`
- `soporte@chechenia.local`

Terminal 2 — checker:

```bash
python run_checker.py
```

O por consola:

```bash
python -m checker.cli --emails data/emails.example.txt --out results
```

## Conectar tu API real

En `config.json`:

```json
{
  "api_base_url": "https://tu-api.com",
  "exists_path": "/admin/users/exists",
  "admin_key": "tu-clave-de-admin",
  "timeout_sec": 12,
  "workers": 8,
  "delay_ms": 0
}
```

Tu backend debe:

- Exigir header `X-Admin-Key`
- Recibir `?email=`
- Responder JSON `{ "email", "registered", "valid_format" }`
- Tener rate limit (el checker no usa proxies; habla con tu servidor)

Las contraseñas de un archivo `email:pass` **se ignoran**. Solo se comprueba existencia del correo.

## Archivos de salida

Tras cada corrida, en `results/`:

- `registered.txt` — ya existen en tu app
- `available.txt` — no están registrados
- `invalid.txt` — formato inválido
- `errors.txt` — red, auth o schema
- `summary.json`

## Límites a propósito

- Sin rotación de proxies
- Sin login masivo / credential check
- Hosts de servicios de terceros bloqueados
- Máximo 32 workers
