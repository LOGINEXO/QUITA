from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_email", "email"),
        Index("ix_customers_phone", "phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    address_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    leads: Mapped[list["Lead"]] = relationship(back_populates="customer")


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_status_created_at", "status", "created_at"),
        CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'converted', 'closed')",
            name="ck_leads_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    source: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="new", server_default="new", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="leads")
    consultations: Mapped[list["VehicleConsultation"]] = relationship(back_populates="lead")


class VehicleConsultation(TimestampMixin, Base):
    __tablename__ = "vehicle_consultations"
    __table_args__ = (
        Index("ix_vehicle_consultations_plate_created_at", "plate", "created_at"),
        CheckConstraint(
            "status IN ('pending', 'success', 'unavailable', 'failed')",
            name="ck_vehicle_consultations_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    plate: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending", nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(80))
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped[Lead | None] = relationship(back_populates="consultations")


class ApiProvider(TimestampMixin, Base):
    __tablename__ = "api_providers"
    __table_args__ = (
        Index("ix_api_providers_enabled_priority", "enabled", "priority"),
        CheckConstraint("priority >= 1 AND priority <= 10000", name="ck_api_providers_priority"),
        CheckConstraint("timeout_seconds > 0 AND timeout_seconds <= 60", name="ck_api_providers_timeout"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=8, server_default="8", nullable=False)
    # Referência a secret manager/variável de ambiente; nunca armazenar a chave em texto puro aqui.
    secret_ref: Mapped[str | None] = mapped_column(String(180))
    health_path: Mapped[str | None] = mapped_column(String(200))
    last_status: Mapped[str | None] = mapped_column(String(40))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120))
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
