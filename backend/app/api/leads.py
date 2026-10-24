from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.providers import require_admin
from app.db.models import Customer, Lead
from app.db.session import get_db

router = APIRouter(tags=["leads"])


class LeadCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)
    postal_code: str | None = Field(default=None, max_length=12)
    source: str | None = Field(default="site", max_length=80)
    privacy_consent: bool

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Informe o nome completo")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        digits = re.sub(r"\D", "", value)
        if not 10 <= len(digits) <= 15:
            raise ValueError("Telefone inválido")
        return digits

    @field_validator("postal_code")
    @classmethod
    def normalize_postal_code(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        digits = re.sub(r"\D", "", value)
        if not 5 <= len(digits) <= 10:
            raise ValueError("CEP/código postal inválido")
        return digits

    @model_validator(mode="after")
    def require_contact_and_consent(self):
        if not self.email and not self.phone:
            raise ValueError("Informe um e-mail ou telefone para contato")
        if not self.privacy_consent:
            raise ValueError("É necessário aceitar o aviso de privacidade")
        return self


class LeadCreatedResponse(BaseModel):
    id: int
    status: str
    created_at: datetime


class LeadAdminView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    source: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    customer_name: str
    customer_email: str | None
    customer_phone: str | None


class LeadStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(new|contacted|qualified|converted|closed)$")
    notes: str | None = Field(default=None, max_length=5000)


@router.post("/leads", response_model=LeadCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreateRequest, db: Session = Depends(get_db)) -> LeadCreatedResponse:
    customer = Customer(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        postal_code=payload.postal_code,
        privacy_consent_at=datetime.now().astimezone(),
    )
    db.add(customer)
    db.flush()
    lead = Lead(customer_id=customer.id, source=payload.source, status="new")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return LeadCreatedResponse(id=lead.id, status=lead.status, created_at=lead.created_at)


@router.get(
    "/admin/leads",
    response_model=list[LeadAdminView],
    dependencies=[Depends(require_admin)],
)
def list_leads(
    lead_status: str | None = Query(default=None, alias="status", pattern=r"^(new|contacted|qualified|converted|closed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[LeadAdminView]:
    query = select(Lead, Customer).join(Customer, Lead.customer_id == Customer.id)
    if lead_status:
        query = query.where(Lead.status == lead_status)
    rows = db.execute(query.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit).offset(offset)).all()
    return [
        LeadAdminView(
            id=lead.id,
            customer_id=lead.customer_id,
            source=lead.source,
            status=lead.status,
            notes=lead.notes,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            customer_name=customer.full_name,
            customer_email=customer.email,
            customer_phone=customer.phone,
        )
        for lead, customer in rows
    ]


@router.patch(
    "/admin/leads/{lead_id}",
    response_model=LeadAdminView,
    dependencies=[Depends(require_admin)],
)
def update_lead(
    lead_id: int,
    payload: LeadStatusUpdate,
    db: Session = Depends(get_db),
) -> LeadAdminView:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    lead.status = payload.status
    if payload.notes is not None:
        lead.notes = payload.notes
    db.commit()
    db.refresh(lead)
    customer = db.get(Customer, lead.customer_id)
    return LeadAdminView(
        id=lead.id,
        customer_id=lead.customer_id,
        source=lead.source,
        status=lead.status,
        notes=lead.notes,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        customer_name=customer.full_name,
        customer_email=customer.email,
        customer_phone=customer.phone,
    )
