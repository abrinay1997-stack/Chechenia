from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    os.environ.setdefault("CHECHENIA_ADMIN_KEY", "cambia-esta-clave")
    uvicorn.run("app.server:app", host="127.0.0.1", port=8787, reload=False)
