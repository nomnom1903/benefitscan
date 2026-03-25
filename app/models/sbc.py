"""
app/models/sbc.py — Data models for SBC (Summary of Benefits and Coverage) plans

Two types of models live here:
  1. SBCPlanDB  — SQLAlchemy ORM model (defines the database table structure)
  2. SBCPlanSchema / SBCPlanResponse — Pydantic models (defines API request/response shapes)

Why two separate model types:
  SQLAlchemy talks to the database. Pydantic validates API data.
  They have different jobs and different syntax, so keeping them separate
  avoids confusion even though it feels like duplication at first.
"""

import uuid
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# SQLAlchemy — Database Layer
# ─────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base class all SQLAlchemy models must inherit from."""
    pass


class SBCPlanDB(Base):
    """
    Database table: sbc_plans
    One row per uploaded SBC document. Stores both extraction results and metadata.
    All 30 SBC fields are stored as nullable strings — they come out of the PDF as text
    and the broker sees/edits them as text, so there's no benefit to parsing $1,500 into
    a number at storage time.
    """
    __tablename__ = "sbc_plans"

    # --- Row identity ---
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- File metadata ---
    upload_filename: Mapped[str] = mapped_column(String)   # original PDF filename
    upload_path: Mapped[str] = mapped_column(String)       # absolute path on disk
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # --- Pipeline status ---
    # pending → processing → complete | failed
    status: Mapped[str] = mapped_column(String, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Validation report (stored as JSON string) ---
    # Example: {"field_results": {"plan_name": {"status": "OK", "note": ""}}, ...}
    # Stored as text because SQLite doesn't have a native JSON column type
    validation_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─────────────────────────────────────────────────────────────────────────
    # The 30 Tier 1 SBC fields
    # All nullable — Claude returns null when a field is genuinely absent
    # ─────────────────────────────────────────────────────────────────────────

    # Plan identity
    plan_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    carrier_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    plan_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)      # HMO/PPO/EPO/POS/HDHP

    # Deductibles
    deductible_individual_in_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deductible_family_in_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deductible_individual_out_of_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deductible_family_out_of_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Out-of-pocket maximums
    oop_max_individual_in_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    oop_max_family_in_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Copays
    copay_pcp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    copay_specialist: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    copay_emergency_room: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    copay_urgent_care: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Coinsurance
    coinsurance_in_network: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Pharmacy / Rx tiers
    rx_tier1_generic: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rx_tier2_preferred_brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rx_tier3_nonpreferred_brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rx_tier4_specialty: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Plan features
    hsa_eligible: Mapped[Optional[str]] = mapped_column(String, nullable=True)          # Yes / No
    separate_drug_deductible: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Yes / No

    # Common services
    preventive_care: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inpatient_hospital: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outpatient_surgery: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mental_health_copay: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telehealth_copay: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Premiums (annual, all tiers)
    premium_employee_only: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    premium_employee_spouse: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    premium_employee_children: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    premium_family: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Administrative
    effective_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    network_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def to_dict(self) -> dict:
        """Convert this database row to a plain Python dict for API responses."""
        data = {
            "id": self.id,
            "upload_filename": self.upload_filename,
            "upload_path": self.upload_path,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
            "status": self.status,
            "error_message": self.error_message,
            "validation_report": json.loads(self.validation_report) if self.validation_report else None,
            # SBC fields
            "plan_name": self.plan_name,
            "carrier_name": self.carrier_name,
            "plan_type": self.plan_type,
            "deductible_individual_in_network": self.deductible_individual_in_network,
            "deductible_family_in_network": self.deductible_family_in_network,
            "deductible_individual_out_of_network": self.deductible_individual_out_of_network,
            "deductible_family_out_of_network": self.deductible_family_out_of_network,
            "oop_max_individual_in_network": self.oop_max_individual_in_network,
            "oop_max_family_in_network": self.oop_max_family_in_network,
            "copay_pcp": self.copay_pcp,
            "copay_specialist": self.copay_specialist,
            "copay_emergency_room": self.copay_emergency_room,
            "copay_urgent_care": self.copay_urgent_care,
            "coinsurance_in_network": self.coinsurance_in_network,
            "rx_tier1_generic": self.rx_tier1_generic,
            "rx_tier2_preferred_brand": self.rx_tier2_preferred_brand,
            "rx_tier3_nonpreferred_brand": self.rx_tier3_nonpreferred_brand,
            "rx_tier4_specialty": self.rx_tier4_specialty,
            "hsa_eligible": self.hsa_eligible,
            "separate_drug_deductible": self.separate_drug_deductible,
            "preventive_care": self.preventive_care,
            "inpatient_hospital": self.inpatient_hospital,
            "outpatient_surgery": self.outpatient_surgery,
            "mental_health_copay": self.mental_health_copay,
            "telehealth_copay": self.telehealth_copay,
            "premium_employee_only": self.premium_employee_only,
            "premium_employee_spouse": self.premium_employee_spouse,
            "premium_employee_children": self.premium_employee_children,
            "premium_family": self.premium_family,
            "effective_date": self.effective_date,
            "network_name": self.network_name,
        }
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic — API Layer (request/response validation)
# ─────────────────────────────────────────────────────────────────────────────

# The ordered list of all 30 SBC field keys.
# Used by the exporter to ensure consistent column ordering in Excel.
SBC_FIELD_KEYS: list[str] = [
    "plan_name", "carrier_name", "plan_type",
    "deductible_individual_in_network", "deductible_family_in_network",
    "deductible_individual_out_of_network", "deductible_family_out_of_network",
    "oop_max_individual_in_network", "oop_max_family_in_network",
    "copay_pcp", "copay_specialist", "copay_emergency_room", "copay_urgent_care",
    "coinsurance_in_network",
    "rx_tier1_generic", "rx_tier2_preferred_brand",
    "rx_tier3_nonpreferred_brand", "rx_tier4_specialty",
    "hsa_eligible", "separate_drug_deductible",
    "preventive_care", "inpatient_hospital", "outpatient_surgery",
    "mental_health_copay", "telehealth_copay",
    "premium_employee_only", "premium_employee_spouse",
    "premium_employee_children", "premium_family",
    "effective_date", "network_name",
]

# Human-readable display labels for each field key (used in Excel headers and UI)
SBC_FIELD_LABELS: dict[str, str] = {
    "plan_name": "Plan Name",
    "carrier_name": "Carrier",
    "plan_type": "Plan Type",
    "deductible_individual_in_network": "Deductible — Ind. (In-Net)",
    "deductible_family_in_network": "Deductible — Fam. (In-Net)",
    "deductible_individual_out_of_network": "Deductible — Ind. (OON)",
    "deductible_family_out_of_network": "Deductible — Fam. (OON)",
    "oop_max_individual_in_network": "OOP Max — Ind. (In-Net)",
    "oop_max_family_in_network": "OOP Max — Fam. (In-Net)",
    "copay_pcp": "PCP Copay",
    "copay_specialist": "Specialist Copay",
    "copay_emergency_room": "ER Copay",
    "copay_urgent_care": "Urgent Care Copay",
    "coinsurance_in_network": "Coinsurance (In-Net)",
    "rx_tier1_generic": "Rx Tier 1 — Generic",
    "rx_tier2_preferred_brand": "Rx Tier 2 — Pref. Brand",
    "rx_tier3_nonpreferred_brand": "Rx Tier 3 — Non-Pref. Brand",
    "rx_tier4_specialty": "Rx Tier 4 — Specialty",
    "hsa_eligible": "HSA Eligible",
    "separate_drug_deductible": "Separate Drug Deductible",
    "preventive_care": "Preventive Care",
    "inpatient_hospital": "Inpatient Hospital",
    "outpatient_surgery": "Outpatient Surgery",
    "mental_health_copay": "Mental Health Copay",
    "telehealth_copay": "Telehealth Copay",
    "premium_employee_only": "Premium — Ee Only",
    "premium_employee_spouse": "Premium — Ee + Spouse",
    "premium_employee_children": "Premium — Ee + Children",
    "premium_family": "Premium — Family",
    "effective_date": "Effective Date",
    "network_name": "Network Name",
}


class PlanFieldUpdate(BaseModel):
    """Request body for PATCH /plans/{plan_id} — updates a single field."""
    field: str    # e.g. "copay_pcp"
    value: Optional[str]  # e.g. "$25" or None to clear it
