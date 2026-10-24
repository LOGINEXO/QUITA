from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import require_admin_session
from app.db.models import AuditEvent, Lead, VehicleConsultation
from app.db.session import get_db
from app.integrations.buscafipe import BuscaFipeClient, BuscaFipeError
from app.config import settings

router = APIRouter(tags=["vehicle-consultations"])
buscafipe_client = BuscaFipeClient(timeout_seconds=settings.request_timeout_seconds)


class VehicleConsultationRequest(BaseModel):
    plate: str = Field(min_length=7, max_length=10)
    lead_id: int | None = Field(default=None, ge=1)

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]", "", value).upper()
        if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", normalized):
            raise ValueError("Placa inválida. Informe uma placa brasileira no formato ABC1234 ou ABC1D23.")
        return normalized


class VehicleConsultationResponse(BaseModel):
    id: int
    lead_id: int | None
    plate: str
    status: str
    provider_id: str | None
    result: dict[str, Any] | None
    error_code: str | None
    completed_at: datetime | None
    created_at: datetime


class VehicleConsultationAdminView(VehicleConsultationResponse):
    updated_at: datetime


@router.post(
    "/consultations/vehicle",
    response_model=VehicleConsultationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle_consultation(
    payload: VehicleConsultationRequest,
    db: Session = Depends(get_db),
) -> VehicleConsultationResponse:
    if payload.lead_id is not None and db.get(Lead, payload.lead_id) is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    consultation = VehicleConsultation(
        lead_id=payload.lead_id,
        plate=payload.plate,
        status="pending",
        provider_id="buscafipe",
    )
    db.add(consultation)
    db.flush()
    db.add(
        AuditEvent(
            actor_id="public",
            action="vehicle_consultation.requested",
            resource_type="vehicle_consultation",
            resource_id=str(consultation.id),
            details_json={"provider_id": "buscafipe", "lead_id": payload.lead_id},
        )
    )
    db.commit()
    db.refresh(consultation)

    try:
        result = await buscafipe_client.plate(payload.plate)
    except ValueError as exc:
        consultation.status = "failed"
        consultation.error_code = "invalid_plate"
        consultation.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BuscaFipeError:
        consultation.status = "unavailable"
        consultation.error_code = "provider_unavailable"
        consultation.completed_at = datetime.now(timezone.utc)
        db.add(
            AuditEvent(
                actor_id="system",
                action="vehicle_consultation.completed",
                resource_type="vehicle_consultation",
                resource_id=str(consultation.id),
                details_json={"status": "unavailable", "error_code": consultation.error_code},
            )
        )
        db.commit()
        db.refresh(consultation)
        return VehicleConsultationResponse(
            id=consultation.id,
            lead_id=consultation.lead_id,
            plate=consultation.plate,
            status=consultation.status,
            provider_id=consultation.provider_id,
            result=None,
            error_code=consultation.error_code,
            completed_at=consultation.completed_at,
            created_at=consultation.created_at,
        )
    except Exception as exc:
        consultation.status = "failed"
        consultation.error_code = "provider_error"
        consultation.completed_at = datetime.now(timezone.utc)
        db.add(
            AuditEvent(
                actor_id="system",
                action="vehicle_consultation.completed",
                resource_type="vehicle_consultation",
                resource_id=str(consultation.id),
                details_json={"status": "failed", "error_code": consultation.error_code},
            )
        )
        db.commit()
        raise HTTPException(status_code=502, detail="Falha inesperada na consulta veicular") from exc

    consultation.status = "success"
    consultation.result_json = result
    consultation.completed_at = datetime.now(timezone.utc)
    db.add(
        AuditEvent(
            actor_id="system",
            action="vehicle_consultation.completed",
            resource_type="vehicle_consultation",
            resource_id=str(consultation.id),
            details_json={"status": "success"},
        )
    )
    db.commit()
    db.refresh(consultation)
    return VehicleConsultationResponse(
        id=consultation.id,
        lead_id=consultation.lead_id,
        plate=consultation.plate,
        status=consultation.status,
        provider_id=consultation.provider_id,
        result=consultation.result_json,
        error_code=consultation.error_code,
        completed_at=consultation.completed_at,
        created_at=consultation.created_at,
    )


@router.get(
    "/admin/consultations/vehicle",
    response_model=list[VehicleConsultationAdminView],
    dependencies=[Depends(require_admin_session)],
)
def list_vehicle_consultations(
    consultation_status: str | None = Query(
        default=None,
        alias="status",
        pattern=r"^(pending|success|unavailable|failed)$",
    ),
    lead_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[VehicleConsultationAdminView]:
    query = select(VehicleConsultation)
    if consultation_status:
        query = query.where(VehicleConsultation.status == consultation_status)
    if lead_id is not None:
        query = query.where(VehicleConsultation.lead_id == lead_id)
    rows = db.scalars(
        query.order_by(VehicleConsultation.created_at.desc(), VehicleConsultation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        VehicleConsultationAdminView(
            id=row.id,
            lead_id=row.lead_id,
            plate=row.plate,
            status=row.status,
            provider_id=row.provider_id,
            result=row.result_json,
            error_code=row.error_code,
            completed_at=row.completed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
