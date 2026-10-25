from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import require_admin_session
from app.db.models import AuditEvent, Customer
from app.db.session import get_db

router = APIRouter(prefix="/admin/customers", tags=["admin-customers"], dependencies=[Depends(require_admin_session)])


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Informe o nome completo")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        digits = re.sub(r"\D", "", value)
        if not 10 <= len(digits) <= 15:
            raise ValueError("Telefone inválido")
        return digits

    @model_validator(mode="after")
    def require_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Informe e-mail ou telefone")
        return self


class CustomerView(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[CustomerView])
def list_customers(active: bool | None = Query(default=True), limit: int = Query(default=200, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    query = select(Customer)
    if active is not None:
        query = query.where(Customer.active == active)
    rows = db.scalars(query.order_by(Customer.created_at.desc(), Customer.id.desc()).limit(limit).offset(offset)).all()
    return [CustomerView(id=c.id, full_name=c.full_name, email=c.email, phone=c.phone, active=c.active, created_at=c.created_at, updated_at=c.updated_at) for c in rows]


@router.post("", response_model=CustomerView, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = Customer(full_name=payload.full_name, email=payload.email, phone=payload.phone)
    db.add(customer)
    db.flush()
    db.add(AuditEvent(actor_id="admin", action="customer.created", resource_type="customer", resource_id=str(customer.id), details_json={"email": customer.email, "phone": customer.phone}))
    db.commit()
    db.refresh(customer)
    return CustomerView(id=customer.id, full_name=customer.full_name, email=customer.email, phone=customer.phone, active=customer.active, created_at=customer.created_at, updated_at=customer.updated_at)


@router.delete("/{customer_id}", response_model=CustomerView)
def deactivate_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if customer.active:
        customer.active = False
        db.add(AuditEvent(actor_id="admin", action="customer.deactivated", resource_type="customer", resource_id=str(customer.id), details_json={"soft_delete": True}))
        db.commit()
        db.refresh(customer)
    return CustomerView(id=customer.id, full_name=customer.full_name, email=customer.email, phone=customer.phone, active=customer.active, created_at=customer.created_at, updated_at=customer.updated_at)
