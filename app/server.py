from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from . import db

ADMIN_KEY = os.environ.get("CHECHENIA_ADMIN_KEY", "cambia-esta-clave")

app = FastAPI(
    title="Chechenia",
    description="App de ejemplo con registro y endpoint admin para comprobar si un email ya existe.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterOut(BaseModel):
    ok: bool
    email: str
    status: str


class ExistsOut(BaseModel):
    email: str
    registered: bool
    valid_format: bool = True


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    db.seed_if_empty()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "chechenia", "users": db.count_users()}


@app.post("/auth/register", response_model=RegisterOut)
def register(payload: RegisterIn) -> RegisterOut:
    ok, status = db.create_user(str(payload.email), payload.password)
    if status == "already_registered":
        raise HTTPException(status_code=409, detail="already_registered")
    if status == "invalid_email":
        raise HTTPException(status_code=400, detail="invalid_email")
    if status == "weak_password":
        raise HTTPException(status_code=400, detail="weak_password")
    return RegisterOut(ok=ok, email=db.normalize_email(str(payload.email)), status=status)


def _require_admin(x_admin_key: Optional[str]) -> None:
    if not x_admin_key or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="invalid_admin_key")


@app.get("/admin/users/exists", response_model=ExistsOut)
def user_exists(email: str, x_admin_key: Optional[str] = Header(default=None)) -> ExistsOut:
    """Endpoint de primera parte: ¿este email ya está registrado en Chechenia?"""
    _require_admin(x_admin_key)
    normalized = db.normalize_email(email)
    if not normalized or "@" not in normalized:
        return ExistsOut(email=normalized, registered=False, valid_format=False)
    return ExistsOut(
        email=normalized,
        registered=db.user_exists(normalized),
        valid_format=True,
    )
