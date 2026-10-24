"""Initial core QUITA schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(32)),
        sa.Column("postal_code", sa.String(12)),
        sa.Column("address_json", sa.JSON()),
        sa.Column("privacy_consent_at", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(80)),
        sa.Column("status", sa.String(24), server_default="new", nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('new', 'contacted', 'qualified', 'converted', 'closed')", name="ck_leads_status"),
    )
    op.create_index("ix_leads_status_created_at", "leads", ["status", "created_at"])

    op.create_table(
        "vehicle_consultations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("plate", sa.String(10), nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("provider_id", sa.String(80)),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'success', 'unavailable', 'failed')", name="ck_vehicle_consultations_status"),
    )
    op.create_index("ix_vehicle_consultations_plate_created_at", "vehicle_consultations", ["plate", "created_at"])

    op.create_table(
        "api_providers",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="8", nullable=False),
        sa.Column("secret_ref", sa.String(180)),
        sa.Column("health_path", sa.String(200)),
        sa.Column("last_status", sa.String(40)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("priority >= 1 AND priority <= 10000", name="ck_api_providers_priority"),
        sa.CheckConstraint("timeout_seconds > 0 AND timeout_seconds <= 60", name="ck_api_providers_timeout"),
    )
    op.create_index("ix_api_providers_enabled_priority", "api_providers", ["enabled", "priority"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.String(120)),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(120)),
        sa.Column("details_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_api_providers_enabled_priority", table_name="api_providers")
    op.drop_table("api_providers")
    op.drop_index("ix_vehicle_consultations_plate_created_at", table_name="vehicle_consultations")
    op.drop_table("vehicle_consultations")
    op.drop_index("ix_leads_status_created_at", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_table("customers")
