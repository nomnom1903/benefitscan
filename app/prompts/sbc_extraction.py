"""
app/prompts/sbc_extraction.py — Claude API prompt templates for SBC extraction

Why a dedicated prompts file:
Prompts are code. They need version control, review, and iteration just like
any other logic. Keeping them here (instead of buried in the service file)
makes it easy to A/B test prompt changes, track what changed, and hand off to
a non-engineer to tune the wording.

Prompt engineering notes:
- The system prompt establishes expert persona — this anchors Claude's behavior
  toward precision over creativity
- We explicitly say "return null, not an error" — without this, models sometimes
  hallucinate plausible-sounding values for missing fields
- "JSON only, no markdown" prevents the ```json ... ``` wrapper that some models
  add by default, which breaks JSON parsing
- We use double-braces {{ }} for literal JSON braces in the f-string template
  (single braces are interpreted as Python format placeholders)
"""

SYSTEM_PROMPT = """You are an expert insurance benefits analyst specializing in \
reading Summary of Benefits and Coverage (SBC) documents. Your job is to extract \
specific plan data fields from SBC text with perfect accuracy.

SBCs are standardized 4-page documents mandated by the ACA. They always contain \
the same fields in roughly the same locations. You must extract values EXACTLY as \
stated — do not interpret, round, or paraphrase. If a field is genuinely not present \
in the document, return null for that field.

Return your response as a JSON object only. No explanation, no markdown, no preamble. \
Just the JSON object."""

EXTRACTION_PROMPT = """Extract all fields from this SBC document text. Return a \
JSON object with exactly these keys:

{{
  "plan_name": "string or null",
  "carrier_name": "string or null",
  "plan_type": "HMO|PPO|EPO|POS|HDHP|null",
  "deductible_individual_in_network": "string or null",
  "deductible_family_in_network": "string or null",
  "deductible_individual_out_of_network": "string or null",
  "deductible_family_out_of_network": "string or null",
  "oop_max_individual_in_network": "string or null",
  "oop_max_family_in_network": "string or null",
  "copay_pcp": "string or null",
  "copay_specialist": "string or null",
  "copay_emergency_room": "string or null",
  "copay_urgent_care": "string or null",
  "coinsurance_in_network": "string or null",
  "rx_tier1_generic": "string or null",
  "rx_tier2_preferred_brand": "string or null",
  "rx_tier3_nonpreferred_brand": "string or null",
  "rx_tier4_specialty": "string or null",
  "hsa_eligible": "Yes|No|null",
  "preventive_care": "string or null",
  "inpatient_hospital": "string or null",
  "outpatient_surgery": "string or null",
  "mental_health_copay": "string or null",
  "telehealth_copay": "string or null",
  "premium_employee_only": "string or null",
  "premium_employee_spouse": "string or null",
  "premium_employee_children": "string or null",
  "premium_family": "string or null",
  "effective_date": "string or null",
  "network_name": "string or null",
  "separate_drug_deductible": "Yes|No|null"
}}

Important extraction rules:
1. Copy values verbatim from the document (e.g. "$1,500" not "1500")
2. For copays, include the full text (e.g. "$30 copay/visit" not just "$30")
3. For coinsurance, include the percentage and context (e.g. "20% after deductible")
4. If a field says "Not Applicable" or "N/A", return null — not the string "N/A"
5. For plan_type, infer from the document if not explicitly stated
6. If premium information is not in the SBC, return null (premiums are sometimes
   in a separate rate sheet, not the SBC itself)

SBC Document Text:
{sbc_text}"""
