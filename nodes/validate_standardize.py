"""
Validation and standardization node.

Validates extracted parameters against reference ranges.
Priority for reference ranges:
  1. Our curated reference_ranges.json (gender-adjusted where available)
  2. Reference range embedded in the report itself (extracted by LLM)
  3. No range available → pass through with flag UNKNOWN (still included)

This makes validation universal — any lab panel is passed downstream,
even if we don't have a curated range for it.
"""

import logging
from utils.reference_ranges import load_reference_ranges

logger = logging.getLogger(__name__)

# Parameters needing scale correction (some labs report in different units)
SCALE_RULES = {
    "Total WBC count": {"threshold": 100, "multiplier": 1000},
    "Platelet Count": {"threshold": 1000, "multiplier": 1000},
    "Absolute Neutrophils": {"threshold": 100, "multiplier": 1000},
    "Absolute Lymphocytes": {"threshold": 100, "multiplier": 1000},
    "Absolute Monocytes": {"threshold": 100, "multiplier": 1000},
    "Absolute Eosinophils": {"threshold": 100, "multiplier": 1000},
    "Absolute Basophils": {"threshold": 100, "multiplier": 1000},
}

_GENDER_KEY_MAP = {
    "male": "adult_male", "m": "adult_male",
    "female": "adult_female", "f": "adult_female",
    "woman": "adult_female", "man": "adult_male",
}


def normalize_numeric(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except Exception:
        return None


def normalize_scale(param, value):
    rule = SCALE_RULES.get(param)
    if not rule:
        return value
    if value < rule["threshold"]:
        return value * rule["multiplier"]
    return value


def resolve_reference(ref, gender: str = None):
    """Resolve gender-adjusted or neutral reference range from our database."""
    if not isinstance(ref, dict):
        return None, None
    if "low" in ref and "high" in ref:
        return ref["low"], ref["high"]
    if gender:
        gender_key = _GENDER_KEY_MAP.get(gender.lower().strip())
        if gender_key and gender_key in ref and isinstance(ref[gender_key], dict):
            return ref[gender_key].get("low"), ref[gender_key].get("high")
    for key in ("adult_male", "adult_female", "adult"):
        if key in ref and isinstance(ref[key], dict):
            return ref[key].get("low"), ref[key].get("high")
    return None, None


def determine_flag(value, low, high):
    if value is None or low is None or high is None:
        return "UNKNOWN"
    if value < low:
        return "LOW"
    if value > high:
        return "HIGH"
    return "NORMAL"


def validate_and_standardize(state):
    ranges = load_reference_ranges()
    cleaned = {}
    errors = list(getattr(state, "errors", []) or [])

    extracted = getattr(state, "extracted_params", {}) or {}
    patient_info = getattr(state, "patient_info", {}) or {}
    gender = patient_info.get("Gender")

    if gender:
        logger.info(f"validate: using gender-adjusted ranges for gender='{gender}'")

    validated_count = 0
    report_range_count = 0
    passthrough_count = 0

    for param, info in extracted.items():
        raw_val = info.get("value")
        raw_unit = info.get("unit")

        if raw_val is None:
            errors.append(f"{param}: missing value")
            continue

        value = normalize_numeric(raw_val)
        if value is None:
            errors.append(f"{param}: invalid numeric value '{raw_val}'")
            continue

        # Scale correction (e.g. WBC reported as 7.5 instead of 7500)
        value = normalize_scale(param, value)

        # ── Priority 1: curated reference database ───────────────────────────
        if param in ranges:
            ref_entry = ranges[param].get("reference")
            low, high = resolve_reference(ref_entry, gender=gender)

            if low is not None and high is not None:
                flag = determine_flag(value, low, high)
                units = ranges[param].get("units")
                unit = raw_unit or (units[0] if isinstance(units, list) and units else None)
                cleaned[param] = {
                    "value": value,
                    "unit": unit,
                    "reference": {"low": low, "high": high},
                    "flag": flag,
                    "ref_source": "database",
                }
                validated_count += 1
                continue

        # ── Priority 2: reference range embedded in the report ───────────────
        report_low = info.get("report_ref_low")
        report_high = info.get("report_ref_high")

        if report_low is not None and report_high is not None:
            # Use the flag already printed in the report if available,
            # otherwise compute from the embedded range
            report_flag_raw = info.get("report_flag")
            if report_flag_raw:
                # Normalize printed flag to LOW/HIGH/NORMAL
                rfu = report_flag_raw.strip().upper()
                if rfu in ("H", "HH", "HIGH", "↑", "A") or rfu.startswith("H"):
                    flag = "HIGH"
                elif rfu in ("L", "LL", "LOW", "↓") or rfu.startswith("L"):
                    flag = "LOW"
                elif rfu in ("N", "NORMAL", "WNL", "NL"):
                    flag = "NORMAL"
                else:
                    flag = determine_flag(value, report_low, report_high)
            else:
                flag = determine_flag(value, report_low, report_high)

            cleaned[param] = {
                "value": value,
                "unit": raw_unit,
                "reference": {"low": report_low, "high": report_high},
                "flag": flag,
                "ref_source": "report",   # indicates range came from the report itself
            }
            report_range_count += 1
            continue

        # ── Priority 3: no range at all — pass through with UNKNOWN flag ─────
        # Still include the parameter so downstream nodes can see it
        report_flag_raw = info.get("report_flag")
        if report_flag_raw:
            rfu = report_flag_raw.strip().upper()
            if rfu in ("H", "HH", "HIGH", "↑", "A") or rfu.startswith("H"):
                flag = "HIGH"
            elif rfu in ("L", "LL", "LOW", "↓") or rfu.startswith("L"):
                flag = "LOW"
            else:
                flag = "NORMAL"
        else:
            flag = "UNKNOWN"

        cleaned[param] = {
            "value": value,
            "unit": raw_unit,
            "reference": {"low": None, "high": None},
            "flag": flag,
            "ref_source": "none",
        }
        passthrough_count += 1
        logger.debug(f"validate: '{param}' — no reference range, passing through with flag={flag}")

    logger.info(
        f"validate: {validated_count} from DB, {report_range_count} from report ranges, "
        f"{passthrough_count} pass-through, {len(errors)} errors"
    )
    return {"validated_params": cleaned, "errors": errors}


def validate_standardize_node(state):
    return validate_and_standardize(state)
