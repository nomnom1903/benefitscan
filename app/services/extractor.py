"""
app/services/extractor.py — Stage 2: AI extraction (Anthropic or Gemini)

Supports two providers, switched via AI_PROVIDER in .env:
  "anthropic" — Claude API (paid, most accurate)
  "gemini"    — Google Gemini API (free tier, no credit card required)

Both providers receive the same prompt and return the same 30-field JSON structure.
The rest of the pipeline (validator, exporter, frontend) doesn't know or care which
provider was used — it just receives a dict of fields.
"""

import json
import re
import logging
from typing import Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import settings
from app.prompts.sbc_extraction import SYSTEM_PROMPT, EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def extract_sbc_fields(pdf_text: str) -> dict:
    """
    Extract all 30 SBC fields from PDF text using the configured AI provider.

    Reads AI_PROVIDER from .env and dispatches to the appropriate function.
    Returns a normalized dict with all 30 field keys (values are str or None).
    """
    provider = settings.ai_provider.lower()

    if provider == "gemini":
        logger.info(f"Using Gemini ({settings.gemini_model})")
        raw = _extract_with_gemini(pdf_text)
    elif provider == "anthropic":
        logger.info(f"Using Anthropic ({settings.claude_model})")
        raw = _extract_with_anthropic(pdf_text)
    else:
        raise ValueError(
            f"Unknown AI_PROVIDER: '{settings.ai_provider}'. "
            "Set AI_PROVIDER to 'anthropic' or 'gemini' in your .env file."
        )

    return _normalize_extraction(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic / Claude
# ─────────────────────────────────────────────────────────────────────────────

def _extract_with_anthropic(pdf_text: str) -> dict:
    """Call Claude API. Retries on transient network/rate-limit errors."""
    import anthropic

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type((
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _call():
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(sbc_text=pdf_text)}],
        )
        return _parse_json_response(message.content[0].text)

    return _call()


# ─────────────────────────────────────────────────────────────────────────────
# Google Gemini (free tier)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_with_gemini(pdf_text: str) -> dict:
    """
    Call Google Gemini API using the new google-genai SDK (free tier).
    Free tier: gemini-1.5-flash — 15 requests/min, 1,500 requests/day.
    Get a free key at aistudio.google.com (no credit card required).
    """
    from google import genai
    from google.genai import types

    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set in your .env file. "
            "Get a free key at aistudio.google.com"
        )

    client = genai.Client(api_key=settings.gemini_api_key)
    full_prompt = EXTRACTION_PROMPT.format(sbc_text=pdf_text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _call():
        # Strip "models/" prefix if present — the SDK adds it automatically
        model_name = settings.gemini_model.replace("models/", "")
        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,          # 0 = deterministic — we want exact extraction, not creativity
                max_output_tokens=4096,
            ),
        )
        return _parse_json_response(response.text)

    return _call()


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json_response(response_text: str) -> dict:
    """
    Parse an AI response as JSON.
    Handles: clean JSON, markdown-fenced JSON, JSON with a preamble sentence.
    """
    # Happy path: clean JSON
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences: ```json { ... } ```
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Extract any JSON object from within surrounding text
    brace_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"AI response could not be parsed as JSON. "
        f"Response was: {response_text[:300]}..."
    )


def _normalize_extraction(raw: dict) -> dict:
    """
    Ensure all 30 expected fields are present.
    Converts "null", "None", "N/A", empty strings → Python None.
    """
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

    normalized = {}
    for key in expected_keys:
        value = raw.get(key)
        if isinstance(value, str) and value.lower() in ("null", "none", "n/a", "not applicable"):
            value = None
        if isinstance(value, str) and value.strip() == "":
            value = None
        normalized[key] = value

    populated = sum(1 for v in normalized.values() if v is not None)
    logger.info(f"Extraction complete: {populated}/31 fields populated.")
    return normalized
