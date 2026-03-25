# BenefitScan — SBC Data Fields Reference

All 30 Tier 1 fields extracted from each SBC. Use this as the reference
for what each field means, where it appears in an SBC, and common edge cases.

---

## Plan Identity

| Field Key | Display Label | Where in SBC | Notes |
|-----------|--------------|-------------|-------|
| `plan_name` | Plan Name | Cover page, header | May include year (e.g. "PPO 2000 2025") |
| `carrier_name` | Carrier | Cover page, header | The insurance company name |
| `plan_type` | Plan Type | Cover page or Section 1 | HMO / PPO / EPO / POS / HDHP |
| `network_name` | Network Name | Cover page, footer | May differ from carrier name |
| `effective_date` | Effective Date | Cover page | Format varies by carrier |

---

## Deductibles

The deductible is what the member pays out-of-pocket before insurance starts sharing costs.

| Field Key | Display Label | 2025 Typical Range |
|-----------|--------------|-------------------|
| `deductible_individual_in_network` | Deductible — Ind. (In-Net) | $500 – $5,000 |
| `deductible_family_in_network` | Deductible — Fam. (In-Net) | $1,000 – $10,000 |
| `deductible_individual_out_of_network` | Deductible — Ind. (OON) | $1,000 – $10,000 |
| `deductible_family_out_of_network` | Deductible — Fam. (OON) | $2,000 – $20,000 |

**Edge cases:**
- HMO plans often have `Not Applicable` for OON (they don't cover out-of-network) → returns null
- HDHP plans have higher deductibles by design ($1,600+ individual for HSA eligibility)
- Some plans have embedded deductibles (individual limit counts toward family) vs. aggregate only

---

## Out-of-Pocket Maximums

The most a member will pay in a year. After this, insurance pays 100%.

| Field Key | Display Label | 2025 ACA Limit |
|-----------|--------------|----------------|
| `oop_max_individual_in_network` | OOP Max — Ind. (In-Net) | $9,200 max |
| `oop_max_family_in_network` | OOP Max — Fam. (In-Net) | $18,400 max |

**Validation:** Values exceeding the ACA 2025 annual limits are flagged Non-Compliant.

---

## Office Visit Copays

Fixed dollar amounts paid per visit, regardless of deductible status (usually).

| Field Key | Display Label | Typical Range |
|-----------|--------------|--------------|
| `copay_pcp` | PCP Copay | $15 – $50 |
| `copay_specialist` | Specialist Copay | $30 – $75 |
| `copay_emergency_room` | ER Copay | $100 – $500 |
| `copay_urgent_care` | Urgent Care Copay | $35 – $100 |
| `mental_health_copay` | Mental Health Copay | Same as PCP (parity law) |
| `telehealth_copay` | Telehealth Copay | $0 – $30 (increasingly $0) |

**Edge cases:**
- HDHP plans often have "deductible then $0" or "no copay before deductible" → include verbatim
- Some plans say "20% after deductible" for ER instead of a flat copay

---

## Coinsurance

The percentage the member pays after meeting the deductible.

| Field Key | Display Label | Typical Value |
|-----------|--------------|--------------|
| `coinsurance_in_network` | Coinsurance (In-Net) | 10% – 30% |

**Note:** "20% coinsurance" means the member pays 20%, insurance pays 80%.

---

## Pharmacy (Rx) Tiers

| Field Key | Display Label | Tier Definition |
|-----------|--------------|----------------|
| `rx_tier1_generic` | Rx Tier 1 — Generic | FDA-approved equivalents |
| `rx_tier2_preferred_brand` | Rx Tier 2 — Pref. Brand | Brand-name on formulary |
| `rx_tier3_nonpreferred_brand` | Rx Tier 3 — Non-Pref. Brand | Brand not preferred by carrier |
| `rx_tier4_specialty` | Rx Tier 4 — Specialty | Biologics, high-cost specialty drugs |
| `separate_drug_deductible` | Separate Drug Deductible | Yes/No |

**Edge cases:**
- Some carriers use 5 tiers (Tier 5 = specialty select). Tier 5 goes in `rx_tier4_specialty` with a note.
- Mail-order pricing is usually separate — note if included in extracted value

---

## Plan Features

| Field Key | Display Label | Values |
|-----------|--------------|--------|
| `hsa_eligible` | HSA Eligible | Yes / No |
| `separate_drug_deductible` | Separate Drug Deductible | Yes / No |

**HSA eligibility rules:**
- Must be enrolled in a Qualified High-Deductible Health Plan (QHDHP)
- 2025 minimum deductible: $1,650 individual / $3,300 family

---

## Common Services

| Field Key | Display Label | Notes |
|-----------|--------------|-------|
| `preventive_care` | Preventive Care | ACA-mandated, almost always "No charge" |
| `inpatient_hospital` | Inpatient Hospital | Usually coinsurance after deductible |
| `outpatient_surgery` | Outpatient Surgery | Usually coinsurance after deductible |

---

## Premiums

**Important:** Premiums are sometimes NOT in the SBC itself — they appear in a separate
rate sheet provided by the carrier. If null, ask the carrier for the rate sheet.

| Field Key | Display Label | Coverage Tier |
|-----------|--------------|--------------|
| `premium_employee_only` | Premium — Ee Only | Employee only |
| `premium_employee_spouse` | Premium — Ee + Spouse | Employee + 1 adult |
| `premium_employee_children` | Premium — Ee + Children | Employee + dependents |
| `premium_family` | Premium — Family | All covered |

**Note:** These are usually annual totals in our extraction. Monthly = annual ÷ 12.
