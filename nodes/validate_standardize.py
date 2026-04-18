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
import re
from utils.reference_ranges import load_reference_ranges

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Age parsing
# ─────────────────────────────────────────────────────────────────────────────

_AGE_UNIT_MULT_YEARS = {
    "day": 1 / 365.0, "days": 1 / 365.0, "d": 1 / 365.0,
    "week": 7 / 365.0, "weeks": 7 / 365.0, "wk": 7 / 365.0, "wks": 7 / 365.0,
    "month": 1 / 12.0, "months": 1 / 12.0, "mo": 1 / 12.0, "mos": 1 / 12.0, "m": 1 / 12.0,
    "year": 1.0, "years": 1.0, "yr": 1.0, "yrs": 1.0, "y": 1.0,
}


def parse_age_to_years(age_str):
    """
    Parse a printed age string like '8 Month(s)', '45 Years', '2y 3m', '30'
    into a float number of years. Returns None if unparseable.
    """
    if age_str is None:
        return None
    s = str(age_str).strip().lower()
    if not s:
        return None
    # Strip parentheses noise: "8 Month(s)" → "8 month s"
    s = s.replace("(", " ").replace(")", " ")
    # Find all <number><unit?> pairs
    tokens = re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]+)?", s)
    if not tokens:
        return None
    total_years = 0.0
    matched_any_unit = False
    for num_s, unit in tokens:
        try:
            num = float(num_s)
        except ValueError:
            continue
        if unit:
            # Strip trailing 's' etc. by trying both exact and singular forms
            mult = _AGE_UNIT_MULT_YEARS.get(unit)
            if mult is None and unit.endswith("s"):
                mult = _AGE_UNIT_MULT_YEARS.get(unit[:-1])
            if mult is not None:
                total_years += num * mult
                matched_any_unit = True
                continue
        # No unit — assume years only if it's the lone token
        if not matched_any_unit and len(tokens) == 1:
            total_years = num
            matched_any_unit = True
    return total_years if matched_any_unit else None


def age_bucket(age_years):
    """Map a numeric age (years) to a pediatric/adult bucket key."""
    if age_years is None:
        return None
    if age_years < 0.08:       # < ~28 days
        return "newborn"
    if age_years < 1.0:
        return "infant"
    if age_years < 6.0:
        return "toddler"
    if age_years < 13.0:
        return "child"
    if age_years < 18.0:
        return "adolescent"
    return "adult"

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

# Parameters where OCR drops decimal point, inflating value 10x
# e.g. RBC 4.0 mill/cumm printed as "40", ref "4.5-6.5" printed as "45-65"
SCALE_DOWN_RULES = {
    "Total RBC count": {"threshold": 10.0, "divisor": 10.0},
}

# Unit conversions when extracted unit differs from DB unit
# key: (canonical_param, extracted_unit_lower) → (multiply_by, db_unit)
UNIT_CONVERSIONS = {
    ("Total T3", "ng/ml"):  (100.0,  "ng/dL"),   # 1 ng/mL = 100 ng/dL
    ("Total T3", "nmol/l"): (65.1,   "ng/dL"),   # 1 nmol/L = 65.1 ng/dL
    ("Free T3",  "pg/ml"):  (100.0,  "pg/dL"),
    ("Total T4", "ng/ml"):  (0.1,    "ug/dL"),   # 1 ng/mL = 0.1 µg/dL (rare but seen)
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
    if rule and value < rule["threshold"]:
        return value * rule["multiplier"]
    down = SCALE_DOWN_RULES.get(param)
    if down and value > down["threshold"]:
        # Only divide if result lands in plausible range (avoid dividing genuinely high values)
        candidate = value / down["divisor"]
        if candidate <= down["threshold"] * 2:
            return candidate
    return value


def apply_unit_conversion(param, raw_unit, value):
    """Convert value to DB unit when extracted unit differs from curated DB unit."""
    if not raw_unit:
        return value
    key = (param, raw_unit.lower().replace(" ", ""))
    conversion = UNIT_CONVERSIONS.get(key)
    if conversion:
        factor, _ = conversion
        logger.debug(f"unit_conversion: {param} {value} {raw_unit} × {factor}")
        return value * factor
    return value


def resolve_reference(ref, gender: str = None, age_bucket_key: str = None):
    """
    Resolve a reference range from our database.
    Priority:
      1. Pediatric age bucket (newborn/infant/toddler/child/adolescent) when
         patient is non-adult — this MUST beat adult-gender ranges to avoid
         flagging infants against adult thresholds.
      2. Gender-adjusted adult range (adult_male / adult_female).
      3. Generic adult / neutral range.
    """
    if not isinstance(ref, dict):
        return None, None
    if "low" in ref and "high" in ref:
        return ref["low"], ref["high"]

    # Pediatric first — for anyone under 18
    pediatric = age_bucket_key and age_bucket_key != "adult"
    if pediatric:
        if age_bucket_key in ref and isinstance(ref[age_bucket_key], dict):
            return ref[age_bucket_key].get("low"), ref[age_bucket_key].get("high")
        # No pediatric bucket for this param → do NOT apply adult range.
        # Returning (None, None) lets caller fall back to the report-embedded range
        # (priority 2) instead of misflagging the child against adult thresholds.
        return None, None

    if gender:
        gender_key = _GENDER_KEY_MAP.get(gender.lower().strip())
        if gender_key and gender_key in ref and isinstance(ref[gender_key], dict):
            return ref[gender_key].get("low"), ref[gender_key].get("high")
    for key in ("adult", "adult_male", "adult_female"):
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
    age_raw = patient_info.get("Age")
    age_years = parse_age_to_years(age_raw)
    age_key = age_bucket(age_years)

    if gender:
        logger.info(f"validate: using gender-adjusted ranges for gender='{gender}'")
    if age_key:
        logger.info(
            f"validate: age='{age_raw}' → {age_years:.2f}y → bucket='{age_key}' "
            f"(pediatric ranges applied when available)"
        )

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

        # Unit conversion (e.g. T3 in ng/mL when DB uses ng/dL)
        value = apply_unit_conversion(param, raw_unit, value)

        # ── Priority 1: curated reference database ───────────────────────────
        if param in ranges:
            ref_entry = ranges[param].get("reference")
            low, high = resolve_reference(ref_entry, gender=gender, age_bucket_key=age_key)

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
