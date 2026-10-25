from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
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
    postal_code: str | None = Field(default=None, max_length=12)
    privacy_consent: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

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

    @field_validator("postal_code")
    @classmethod
    def clean_postal_code(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        digits = re.sub(r"\D", "", value)
        if not 5 <= len(digits) <= 10:
            raise ValueError("CEP inválido")
        return digits

    @model_validator(mode="after")
    def require_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Informe e-mail ou telefone")
        return self

class CustomerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str | None
    phone: str | None
    postal_code: str | None
    address_json: dict[str, Any] | None
    privacy_consent_at: datetime | None
    active: bool
    created_at: datetime
    updated_at: datetime

def customer_view(c: Customer) -> CustomerView:
    return CustomerView(
        id=c.id, full_name=c.full_name, email=c.email, phone=c.phone,
        postal_code=c.postal_code, address_json=c.address_json,
        privacy_consent_at=c.privacy_consent_at, active=c.active,
        created_at=c.created_at, updated_at=c.updated_at,
    )

@router.get("", response_model=list[CustomerView])
def list_customers(
    active: bool | None = Query(default=True),
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Customer)
    if active is not None:
        query = query.where(Customer.active == active)
    rows = db.scalars(query.order_by(Customer.created_at.desc(), Customer.id.desc()).limit(limit).offset(offset)).all()
    return [customer_view(c) for c in rows]

@router.post("", response_model=CustomerView, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    details = dict(payload.details or {})
    details.pop("documents", None)  # Arquivos não devem ser guardados como texto no banco.
    address = {k: details.pop(k) for k in ("birth_date", "company_opening_date", "cpf_cnpj", "address", "city", "state", "vehicle", "contract", "arrears", "documents", "notes", "assigned_to") if k in details}
    if details:
        address["additional"] = details
    customer = Customer(
        full_name=payload.full_name, email=payload.email, phone=payload.phone,
        postal_code=payload.postal_code, address_json=address or None,
        privacy_consent_at=datetime.now().astimezone() if payload.privacy_consent else None,
    )
    db.add(customer)
    db.flush()
    db.add(AuditEvent(
        actor_id="admin", action="customer.created", resource_type="customer",
        resource_id=str(customer.id),
        details_json={"email": customer.email, "phone": customer.phone, "fields_saved": sorted(address.keys())},
    ))
    db.commit()
    db.refresh(customer)
    return customer_view(customer)

@router.patch("/{customer_id}", response_model=CustomerView)
def update_customer(customer_id: int, payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    details = dict(payload.details or {})
    details.pop("documents", None)
    address = {k: details.pop(k) for k in ("birth_date", "company_opening_date", "cpf_cnpj", "address", "city", "state", "vehicle", "contract", "arrears", "documents", "notes", "assigned_to") if k in details}
    if details:
        address["additional"] = details
    customer.full_name = payload.full_name
    customer.email = payload.email
    customer.phone = payload.phone
    customer.postal_code = payload.postal_code
    customer.address_json = address or None
    if payload.privacy_consent and customer.privacy_consent_at is None:
        customer.privacy_consent_at = datetime.now().astimezone()
    db.add(AuditEvent(actor_id="admin", action="customer.updated", resource_type="customer", resource_id=str(customer.id), details_json={"fields_saved": sorted(address.keys())}))
    db.commit()
    db.refresh(customer)
    return customer_view(customer)

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
    return customer_view(customer)
