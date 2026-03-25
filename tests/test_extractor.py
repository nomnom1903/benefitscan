"""
tests/test_extractor.py — Unit tests for the AI extraction service

These tests verify that the JSON parsing and normalization logic works correctly.
They do NOT call the real Claude API (that would cost money and require a network
connection for every test run). Instead, we mock the API response.

To run: python -m pytest tests/test_extractor.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# We need to mock settings before importing extractor (it reads the API key at import time)
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-for-testing-only"

from app.services.extractor import _parse_json_response, _normalize_extraction


class TestParseJsonResponse:
    """Tests for the JSON parsing logic that handles Claude's various response formats."""

    def test_clean_json_object(self):
        """Happy path: Claude returns clean JSON with no wrapper."""
        raw = '{"plan_name": "Blue PPO 2000", "copay_pcp": "$30"}'
        result = _parse_json_response(raw)
        assert result["plan_name"] == "Blue PPO 2000"
        assert result["copay_pcp"] == "$30"

    def test_json_with_markdown_fence(self):
        """Claude sometimes wraps JSON in ```json ... ``` — we strip the fences."""
        raw = '```json\n{"plan_name": "Aetna HMO", "copay_pcp": "$25"}\n```'
        result = _parse_json_response(raw)
        assert result["plan_name"] == "Aetna HMO"

    def test_json_with_plain_fence(self):
        """Triple backtick without 'json' label."""
        raw = '```\n{"plan_name": "Cigna EPO"}\n```'
        result = _parse_json_response(raw)
        assert result["plan_name"] == "Cigna EPO"

    def test_json_with_preamble(self):
        """Claude sometimes adds a sentence before the JSON object."""
        raw = 'Here is the extracted data:\n{"plan_name": "Kaiser HMO", "hsa_eligible": "No"}'
        result = _parse_json_response(raw)
        assert result["plan_name"] == "Kaiser HMO"

    def test_invalid_json_raises(self):
        """Completely unparseable response should raise ValueError."""
        raw = "I could not extract the data from this document."
        with pytest.raises(ValueError, match="could not be parsed as JSON"):
            _parse_json_response(raw)


class TestNormalizeExtraction:
    """Tests for field normalization: null strings, missing keys, empty strings."""

    def test_string_null_converted_to_none(self):
        """Claude sometimes returns the string "null" instead of JSON null."""
        raw = {"plan_name": "Test Plan", "copay_pcp": "null"}
        result = _normalize_extraction(raw)
        assert result["copay_pcp"] is None

    def test_string_none_converted_to_none(self):
        """Normalize "None" (Python-style) to actual None."""
        raw = {"plan_name": "Test Plan", "copay_pcp": "None"}
        result = _normalize_extraction(raw)
        assert result["copay_pcp"] is None

    def test_na_converted_to_none(self):
        """N/A and 'Not Applicable' should normalize to None."""
        raw = {"plan_name": "Test Plan", "telehealth_copay": "N/A"}
        result = _normalize_extraction(raw)
        assert result["telehealth_copay"] is None

    def test_empty_string_converted_to_none(self):
        """Empty strings are treated as missing, not as an empty value."""
        raw = {"plan_name": "Test Plan", "network_name": "   "}
        result = _normalize_extraction(raw)
        assert result["network_name"] is None

    def test_missing_keys_filled_with_none(self):
        """If Claude omits a key entirely, it's added as None."""
        raw = {"plan_name": "Partial Plan"}  # Only one of 30 fields
        result = _normalize_extraction(raw)
        # All 31 expected keys should be present (30 SBC fields + we check a few)
        assert "copay_pcp" in result
        assert result["copay_pcp"] is None
        assert "deductible_individual_in_network" in result
        assert result["deductible_individual_in_network"] is None

    def test_valid_values_preserved(self):
        """Values that look correct should pass through unchanged."""
        raw = {
            "plan_name": "Blue Shield PPO 2000",
            "copay_pcp": "$30 copay/visit",
            "deductible_individual_in_network": "$2,000",
            "hsa_eligible": "No",
            "plan_type": "PPO",
        }
        result = _normalize_extraction(raw)
        assert result["plan_name"] == "Blue Shield PPO 2000"
        assert result["copay_pcp"] == "$30 copay/visit"
        assert result["deductible_individual_in_network"] == "$2,000"
        assert result["hsa_eligible"] == "No"
        assert result["plan_type"] == "PPO"

    def test_all_thirty_fields_present(self):
        """The normalized output must contain all 30 expected SBC fields."""
        result = _normalize_extraction({})  # Empty input
        expected_keys = [
            "plan_name", "carrier_name", "plan_type",
            "deductible_individual_in_network", "deductible_family_in_network",
            "deductible_individual_out_of_network", "deductible_family_out_of_network",
            "oop_max_individual_in_network", "oop_max_family_in_network",
            "copay_pcp", "copay_specialist", "copay_emergency_room", "copay_urgent_care",
            "coinsurance_in_network",
            "rx_tier1_generic", "rx_tier2_preferred_brand",
            "rx_tier3_nonpreferred_brand", "rx_tier4_specialty",
            "hsa_eligible", "preventive_care", "inpatient_hospital",
            "outpatient_surgery", "mental_health_copay", "telehealth_copay",
            "premium_employee_only", "premium_employee_spouse",
            "premium_employee_children", "premium_family",
            "effective_date", "network_name", "separate_drug_deductible",
        ]
        for key in expected_keys:
            assert key in result, f"Missing expected field: {key}"
