"""
app/services/validator.py — Stage 3: Extracted data validation

The validator acts as a quality control layer between AI extraction and
human review. It doesn't reject data — it flags it, so the broker can
decide whether Claude got it right or needs correction.

Status levels:
  OK           — field present, value looks plausible
  Missing      — field is null/empty (might be absent from doc, might be extraction failure)
  Review       — field present but value is suspicious (unusually high/low, unexpected format)
  Non-Compliant — value violates a known regulatory rule (ACA OOP max limits, etc.)

Why human-in-the-loop matters:
AI extraction is ~95% accurate on standard SBCs. That's great, but 5% wrong
on a broker's client presentation is unacceptable. The validator surfaces the
5% so the broker reviews exactly those cells, rather than reviewing all 30 fields
on every plan manually.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ACA 2025 out-of-pocket maximum limits (updated annually by HHS)
# Brokers need to flag plans that exceed these — they're non-compliant
ACA_OOP_MAX_INDIVIDUAL_2025 = 9_200   # $9,200
ACA_OOP_MAX_FAMILY_2025 = 18_400       # $18,400

# Sanity bounds for deductibles — values outside this range get a Review flag
# (not necessarily wrong, but unusual enough to warrant a human look)
DEDUCTIBLE_LOW_THRESHOLD = 100        # Below $100 is suspicious for a group plan
DEDUCTIBLE_HIGH_THRESHOLD = 10_000    # Above $10,000 individual is unusual


def validate_sbc_plan(extracted_data: dict) -> dict:
    """
    Run all validation rules on an extracted SBC plan.

    Args:
        extracted_data: dict with 30 SBC field keys, values are strings or None

    Returns:
        validation_report dict:
        {
            "overall_status": "OK" | "WARNING" | "CRITICAL",
            "field_results": {
                "plan_name": {"status": "OK", "note": ""},
                "copay_pcp": {"status": "Missing", "note": "Field not found in document"},
                ...
            },
            "summary": {
                "total_fields": 30,
                "ok_count": 24,
                "missing_count": 4,
                "review_count": 2,
                "non_compliant_count": 0
            }
        }
    """
    field_results: dict[str, dict] = {}

    # --- Rule 1: Flag all null/missing fields ---
    for key, value in extracted_data.items():
        if value is None:
            field_results[key] = {
                "status": "Missing",
                "note": "Field not found in document — verify manually or leave blank if not applicable",
            }
        else:
            # Default to OK; specific rules below may upgrade this to Review/Non-Compliant
            field_results[key] = {"status": "OK", "note": ""}

    # --- Rule 2: Deductible sanity check ---
    deductible_fields = [
        "deductible_individual_in_network",
        "deductible_family_in_network",
        "deductible_individual_out_of_network",
        "deductible_family_out_of_network",
    ]
    for field in deductible_fields:
        value = extracted_data.get(field)
        if value is None:
            continue  # already flagged as Missing above
        amount = _extract_dollar_amount(value)
        if amount is not None:
            if amount < DEDUCTIBLE_LOW_THRESHOLD:
                field_results[field] = {
                    "status": "Review",
                    "note": f"Unusually low deductible (${amount:,.0f}) — verify this is correct",
                }
            elif amount > DEDUCTIBLE_HIGH_THRESHOLD:
                field_results[field] = {
                    "status": "Review",
                    "note": f"Unusually high deductible (${amount:,.0f}) — verify this is correct",
                }

    # --- Rule 3: ACA OOP max compliance check ---
    oop_individual = extracted_data.get("oop_max_individual_in_network")
    if oop_individual:
        amount = _extract_dollar_amount(oop_individual)
        if amount is not None and amount > ACA_OOP_MAX_INDIVIDUAL_2025:
            field_results["oop_max_individual_in_network"] = {
                "status": "Non-Compliant",
                "note": (
                    f"Exceeds 2025 ACA individual OOP max limit of "
                    f"${ACA_OOP_MAX_INDIVIDUAL_2025:,} — verify with carrier"
                ),
            }

    oop_family = extracted_data.get("oop_max_family_in_network")
    if oop_family:
        amount = _extract_dollar_amount(oop_family)
        if amount is not None and amount > ACA_OOP_MAX_FAMILY_2025:
            field_results["oop_max_family_in_network"] = {
                "status": "Non-Compliant",
                "note": (
                    f"Exceeds 2025 ACA family OOP max limit of "
                    f"${ACA_OOP_MAX_FAMILY_2025:,} — verify with carrier"
                ),
            }

    # --- Rule 4: Plan type must be identified ---
    if extracted_data.get("plan_type") is None:
        field_results["plan_type"] = {
            "status": "Review",
            "note": "Plan type (HMO/PPO/EPO/HDHP) could not be determined — required for comparison",
        }

    # --- Rule 5: Likely extraction failure if both premiums AND deductibles are null ---
    premium_fields = [
        "premium_employee_only", "premium_employee_spouse",
        "premium_employee_children", "premium_family",
    ]
    key_cost_fields = [
        "deductible_individual_in_network",
        "oop_max_individual_in_network",
        "copay_pcp",
    ]
    premiums_all_null = all(extracted_data.get(f) is None for f in premium_fields)
    core_costs_all_null = all(extracted_data.get(f) is None for f in key_cost_fields)

    if premiums_all_null and core_costs_all_null:
        # Flag plan_name as a proxy for "this whole extraction may have failed"
        field_results["plan_name"] = {
            "status": "Review",
            "note": (
                "Both premium and core cost fields are missing — "
                "possible extraction failure. Review the raw PDF."
            ),
        }

    # --- Build summary counts ---
    counts = {"OK": 0, "Missing": 0, "Review": 0, "Non-Compliant": 0}
    for result in field_results.values():
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1

    # Determine overall status
    if counts["Non-Compliant"] > 0:
        overall_status = "CRITICAL"
    elif counts["Review"] > 0 or counts["Missing"] > 3:
        # More than 3 missing fields suggests a problem worth flagging at the plan level
        overall_status = "WARNING"
    else:
        overall_status = "OK"

    validation_report = {
        "overall_status": overall_status,
        "field_results": field_results,
        "summary": {
            "total_fields": len(field_results),
            "ok_count": counts["OK"],
            "missing_count": counts["Missing"],
            "review_count": counts["Review"],
            "non_compliant_count": counts["Non-Compliant"],
        },
    }

    logger.info(
        f"Validation complete. Overall: {overall_status}. "
        f"OK: {counts['OK']}, Missing: {counts['Missing']}, "
        f"Review: {counts['Review']}, Non-Compliant: {counts['Non-Compliant']}"
    )

    return validation_report


def _extract_dollar_amount(value: str) -> Optional[float]:
    """
    Parse a dollar amount from a string like "$1,500", "$9,200/year", "1500".
    Returns the numeric value, or None if we can't parse it.

    We use this to run numeric comparisons on fields that are stored as strings.
    """
    if not value:
        return None
    # Remove $, commas, spaces; match the first number (integer or decimal)
    cleaned = value.replace("$", "").replace(",", "").replace(" ", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if match:
        return float(match.group())
    return None
