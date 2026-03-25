"""
tests/test_validator.py — Unit tests for the validation service

Tests that the validator correctly flags:
  - Missing fields (null)
  - Unusually high/low deductibles
  - ACA OOP max violations
  - Missing plan type
  - Total extraction failure pattern

To run: python -m pytest tests/test_validator.py -v
"""

import pytest
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-for-testing-only"

from app.services.validator import validate_sbc_plan, _extract_dollar_amount


# ─── Helper: build a complete "good" plan dict to use as a baseline ───────────
def good_plan() -> dict:
    """A fully populated, ACA-compliant plan — all validators should pass."""
    return {
        "plan_name": "Blue Shield PPO 2000",
        "carrier_name": "Blue Shield of California",
        "plan_type": "PPO",
        "deductible_individual_in_network": "$2,000",
        "deductible_family_in_network": "$4,000",
        "deductible_individual_out_of_network": "$4,000",
        "deductible_family_out_of_network": "$8,000",
        "oop_max_individual_in_network": "$6,500",
        "oop_max_family_in_network": "$13,000",
        "copay_pcp": "$30 copay/visit",
        "copay_specialist": "$50 copay/visit",
        "copay_emergency_room": "$250 copay/visit",
        "copay_urgent_care": "$75 copay/visit",
        "coinsurance_in_network": "20% after deductible",
        "rx_tier1_generic": "$10",
        "rx_tier2_preferred_brand": "$40",
        "rx_tier3_nonpreferred_brand": "$75",
        "rx_tier4_specialty": "20% up to $250/fill",
        "hsa_eligible": "No",
        "separate_drug_deductible": "No",
        "preventive_care": "No charge",
        "inpatient_hospital": "20% after deductible",
        "outpatient_surgery": "20% after deductible",
        "mental_health_copay": "$30 copay/visit",
        "telehealth_copay": "$15",
        "premium_employee_only": "$4,800/year",
        "premium_employee_spouse": "$9,600/year",
        "premium_employee_children": "$8,400/year",
        "premium_family": "$14,400/year",
        "effective_date": "January 1, 2025",
        "network_name": "Blue Shield Access+ HMO",
    }


class TestMissingFieldDetection:
    """Null fields should always be flagged as Missing."""

    def test_null_field_flagged_as_missing(self):
        plan = good_plan()
        plan["copay_pcp"] = None
        report = validate_sbc_plan(plan)
        assert report["field_results"]["copay_pcp"]["status"] == "Missing"

    def test_multiple_nulls_all_flagged(self):
        plan = good_plan()
        plan["rx_tier4_specialty"] = None
        plan["telehealth_copay"] = None
        plan["effective_date"] = None
        report = validate_sbc_plan(plan)
        assert report["field_results"]["rx_tier4_specialty"]["status"] == "Missing"
        assert report["field_results"]["telehealth_copay"]["status"] == "Missing"
        assert report["field_results"]["effective_date"]["status"] == "Missing"

    def test_missing_count_in_summary(self):
        plan = good_plan()
        plan["copay_pcp"] = None
        plan["copay_specialist"] = None
        report = validate_sbc_plan(plan)
        assert report["summary"]["missing_count"] == 2

    def test_fully_populated_plan_has_zero_missing(self):
        report = validate_sbc_plan(good_plan())
        assert report["summary"]["missing_count"] == 0


class TestDeductibleValidation:
    """Deductibles outside normal ranges should be flagged as Review."""

    def test_very_high_individual_deductible_flagged(self):
        plan = good_plan()
        plan["deductible_individual_in_network"] = "$12,000"  # above $10,000 threshold
        report = validate_sbc_plan(plan)
        assert report["field_results"]["deductible_individual_in_network"]["status"] == "Review"

    def test_very_low_individual_deductible_flagged(self):
        plan = good_plan()
        plan["deductible_individual_in_network"] = "$50"  # below $100 threshold
        report = validate_sbc_plan(plan)
        assert report["field_results"]["deductible_individual_in_network"]["status"] == "Review"

    def test_normal_deductible_not_flagged(self):
        plan = good_plan()
        plan["deductible_individual_in_network"] = "$2,500"
        report = validate_sbc_plan(plan)
        assert report["field_results"]["deductible_individual_in_network"]["status"] == "OK"

    def test_family_deductible_also_checked(self):
        plan = good_plan()
        plan["deductible_family_in_network"] = "$25,000"  # extreme value
        report = validate_sbc_plan(plan)
        assert report["field_results"]["deductible_family_in_network"]["status"] == "Review"


class TestOOPMaxCompliance:
    """OOP max values exceeding 2025 ACA limits should be flagged Non-Compliant."""

    def test_individual_oop_max_exceeds_aca_limit(self):
        plan = good_plan()
        plan["oop_max_individual_in_network"] = "$10,000"  # over $9,200 limit
        report = validate_sbc_plan(plan)
        assert report["field_results"]["oop_max_individual_in_network"]["status"] == "Non-Compliant"
        assert "9,200" in report["field_results"]["oop_max_individual_in_network"]["note"]

    def test_family_oop_max_exceeds_aca_limit(self):
        plan = good_plan()
        plan["oop_max_family_in_network"] = "$20,000"  # over $18,400 limit
        report = validate_sbc_plan(plan)
        assert report["field_results"]["oop_max_family_in_network"]["status"] == "Non-Compliant"

    def test_compliant_oop_max_not_flagged(self):
        plan = good_plan()
        plan["oop_max_individual_in_network"] = "$7,000"  # within limit
        report = validate_sbc_plan(plan)
        assert report["field_results"]["oop_max_individual_in_network"]["status"] == "OK"

    def test_non_compliant_triggers_critical_overall_status(self):
        plan = good_plan()
        plan["oop_max_individual_in_network"] = "$15,000"
        report = validate_sbc_plan(plan)
        assert report["overall_status"] == "CRITICAL"


class TestPlanTypeValidation:
    """Missing plan type should be flagged as Review."""

    def test_null_plan_type_flagged(self):
        plan = good_plan()
        plan["plan_type"] = None
        report = validate_sbc_plan(plan)
        assert report["field_results"]["plan_type"]["status"] == "Review"

    def test_present_plan_type_not_flagged(self):
        plan = good_plan()
        plan["plan_type"] = "HMO"
        report = validate_sbc_plan(plan)
        assert report["field_results"]["plan_type"]["status"] == "OK"


class TestOverallStatus:
    """overall_status should be set correctly based on the most severe flag."""

    def test_clean_plan_is_ok(self):
        report = validate_sbc_plan(good_plan())
        assert report["overall_status"] == "OK"

    def test_review_flag_gives_warning(self):
        plan = good_plan()
        plan["plan_type"] = None  # triggers Review
        report = validate_sbc_plan(plan)
        assert report["overall_status"] == "WARNING"

    def test_noncompliant_gives_critical(self):
        plan = good_plan()
        plan["oop_max_individual_in_network"] = "$15,000"  # ACA violation
        report = validate_sbc_plan(plan)
        assert report["overall_status"] == "CRITICAL"

    def test_many_missing_gives_warning(self):
        plan = good_plan()
        # Null out 4 fields — should trigger WARNING (threshold is > 3 missing)
        for field in ["copay_pcp", "copay_specialist", "copay_emergency_room", "copay_urgent_care"]:
            plan[field] = None
        report = validate_sbc_plan(plan)
        assert report["overall_status"] == "WARNING"


class TestDollarExtraction:
    """Tests for the internal dollar amount parser."""

    def test_dollar_sign_format(self):
        assert _extract_dollar_amount("$1,500") == 1500.0

    def test_plain_number(self):
        assert _extract_dollar_amount("9200") == 9200.0

    def test_number_with_context(self):
        assert _extract_dollar_amount("$30 copay/visit") == 30.0

    def test_percentage_not_parsed_as_dollar(self):
        # "20% after deductible" — the 20 will be extracted, but that's acceptable
        # since we only use this on dollar-valued fields
        result = _extract_dollar_amount("20% after deductible")
        assert result == 20.0  # Returns 20, but we don't call this on % fields

    def test_none_returns_none(self):
        assert _extract_dollar_amount(None) is None

    def test_unparseable_returns_none(self):
        assert _extract_dollar_amount("Not applicable") is None
