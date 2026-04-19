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
    # Reticulocyte absolute count: some labs report in 10^3/uL (e.g. 50) vs /cumm (50000)
    "Reticulocyte Count": {"threshold": 1000, "multiplier": 1000},
}

# Parameters where OCR drops decimal point, inflating value 10x
# e.g. RBC 4.0 mill/cumm printed as "40", ref "4.5-6.5" printed as "45-65"
SCALE_DOWN_RULES = {
    "Total RBC count": {"threshold": 10.0, "divisor": 10.0},
}

# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive unit conversion table — covers conventional ↔ SI differences
# seen in labs across India, US, UK, Europe, Australia, Middle East, SE Asia.
#
# Key format: (canonical_param, normalised_unit_string) → (multiply_by, db_unit)
# Unit strings are pre-normalised (lowercase, no spaces, µ→u, ×→x, ³→3, ²→2).
# DB units match reference_ranges.json.  Add new rows freely; existing rows
# are never removed — they are safe no-ops when the unit already matches.
# ─────────────────────────────────────────────────────────────────────────────
UNIT_CONVERSIONS: dict = {

    # ══ GLUCOSE / DIABETES ════════════════════════════════════════════════════
    # DB: mg/dL   SI: mmol/L   factor: × 18.018
    ("Fasting Blood Glucose",      "mmol/l"):  (18.018, "mg/dL"),
    ("Postprandial Blood Glucose", "mmol/l"):  (18.018, "mg/dL"),
    ("Random Blood Glucose",       "mmol/l"):  (18.018, "mg/dL"),
    # HbA1c: IFCC (mmol/mol) → NGSP (%)   IFCC formula: % = (mmol/mol × 0.09148) + 2.15
    # Stored as (factor, unit, offset) — see apply_unit_conversion for handling.
    ("HbA1c", "mmol/mol"):  (0.09148, "%", 2.15),

    # ══ LIPID PANEL ════════════════════════════════════════════════════════════
    # DB: mg/dL   SI: mmol/L   cholesterol factor: × 38.665, TG: × 88.573
    ("Total Cholesterol",   "mmol/l"):  (38.665, "mg/dL"),
    ("Triglycerides",       "mmol/l"):  (88.573, "mg/dL"),
    ("HDL Cholesterol",     "mmol/l"):  (38.665, "mg/dL"),
    ("LDL Cholesterol",     "mmol/l"):  (38.665, "mg/dL"),
    ("VLDL Cholesterol",    "mmol/l"):  (38.665, "mg/dL"),
    ("Non-HDL Cholesterol", "mmol/l"):  (38.665, "mg/dL"),
    ("Apolipoprotein A1",   "g/l"):     (100.0,  "mg/dL"),
    ("Apolipoprotein B",    "g/l"):     (100.0,  "mg/dL"),
    # Homocysteine: DB umol/L = same as umol/l (no-op normalisation)
    ("Homocysteine", "umol/l"): (1.0, "umol/L"),

    # ══ RENAL / KFT ═══════════════════════════════════════════════════════════
    # Creatinine: DB mg/dL   SI: umol/L   factor: ÷ 88.402
    ("Creatinine",       "umol/l"):   (0.011312, "mg/dL"),
    ("Urine Creatinine", "umol/l"):   (0.011312, "mg/dL"),
    # Urea: DB mg/dL   SI: mmol/L   factor: × 6.006
    ("Blood Urea",  "mmol/l"):  (6.006, "mg/dL"),
    # BUN: DB mg/dL   SI: mmol/L   factor: × 2.8
    ("BUN",         "mmol/l"):  (2.8,   "mg/dL"),
    # Uric Acid: DB mg/dL   SI: umol/L   factor: ÷ 59.485
    ("Uric Acid",   "umol/l"):  (0.016807, "mg/dL"),
    # eGFR: mL/min/1.73m2 = mL/min/1.73m² — no numeric conversion needed
    # Cystatin C: mg/L — already DB unit, no conversion
    # Urine Protein: DB mg/dL; if reported mg/L → ÷ 10
    ("Urine Protein",    "mg/l"):  (0.1, "mg/dL"),
    # Microalbumin: DB mg/L; if reported mg/dL → × 10
    ("Microalbumin",     "mg/dl"): (10.0, "mg/L"),
    # ACR: DB mg/g (mg albumin/g creatinine); if reported mg/mmol → × 8.84
    ("ACR", "mg/mmol"): (8.84, "mg/g"),

    # ══ ELECTROLYTES ════════════════════════════════════════════════════════════
    # Na/K/Cl/HCO3: mmol/L = mEq/L for monovalent ions — no conversion needed
    # Calcium: DB mg/dL   SI: mmol/L   factor: × 4.008
    ("Calcium",    "mmol/l"):  (4.008, "mg/dL"),
    # Phosphorus: DB mg/dL   SI: mmol/L   factor: × 3.097
    ("Phosphorus", "mmol/l"):  (3.097, "mg/dL"),
    # Magnesium: DB mg/dL   SI: mmol/L   factor: × 2.431
    ("Magnesium",  "mmol/l"):  (2.431, "mg/dL"),
    # Magnesium: DB mg/dL   SI: mEq/L   factor: × 1.215 (Mg²⁺ eq)
    ("Magnesium",  "meq/l"):   (1.215, "mg/dL"),

    # ══ HAEMATOLOGY ════════════════════════════════════════════════════════════
    # Hemoglobin: DB g/dL   UK/AU/CA report g/L → ÷ 10
    ("Hemoglobin", "g/l"):  (0.1, "g/dL"),
    # ESR: mm/hr — already DB unit everywhere, no conversion needed

    # ══ LIVER FUNCTION (LFT) ═══════════════════════════════════════════════════
    # Bilirubin: DB mg/dL   SI: umol/L   factor: ÷ 17.104
    ("Total Bilirubin",    "umol/l"):  (0.058479, "mg/dL"),
    ("Direct Bilirubin",   "umol/l"):  (0.058479, "mg/dL"),
    ("Indirect Bilirubin", "umol/l"):  (0.058479, "mg/dL"),
    # Albumin / Total Protein / Globulin: DB g/dL   SI: g/L → ÷ 10
    ("Total Protein",  "g/l"):  (0.1, "g/dL"),
    ("Albumin",        "g/l"):  (0.1, "g/dL"),
    ("Globulin",       "g/l"):  (0.1, "g/dL"),
    # Ammonia: DB ug/dL   SI: umol/L   factor: × 1.703
    ("Ammonia",  "umol/l"):  (1.703, "ug/dL"),
    # LDH/ALT/AST/ALP/GGT — U/L = IU/L, no conversion needed
    # Ceruloplasmin: DB mg/dL  SI: mg/L → ÷ 10
    ("Ceruloplasmin", "mg/l"):  (0.1, "mg/dL"),

    # ══ IRON STUDIES ═══════════════════════════════════════════════════════════
    # Serum Iron / TIBC: DB ug/dL   SI: umol/L   factor: × 5.585
    ("Serum Iron",            "umol/l"):  (5.585, "ug/dL"),
    ("TIBC",                  "umol/l"):  (5.585, "ug/dL"),
    ("Transferrin Saturation","umol/l"):  (5.585, "ug/dL"),
    # Ferritin: DB ng/mL = ug/L — same numeric; if pmol/L → × 0.45
    ("Serum Ferritin", "pmol/l"): (0.45, "ng/mL"),

    # ══ THYROID ════════════════════════════════════════════════════════════════
    # TSH: mIU/L = uIU/mL — same numeric; pmol/L → × 1.31 (rare)
    ("TSH", "pmol/l"):  (1.31, "mIU/L"),
    # Free T4: DB ng/dL   SI: pmol/L   factor: ÷ 12.871
    ("Free T4",  "pmol/l"):  (0.07769, "ng/dL"),
    # Total T4: DB ug/dL  SI: nmol/L  factor: ÷ 12.871
    ("Total T4", "nmol/l"):  (0.07769, "ug/dL"),
    # Free T3: DB pg/mL   SI: pmol/L  factor: × 0.6503
    ("Free T3",  "pmol/l"):  (0.6503, "pg/mL"),
    # Total T3: DB ng/dL  SI: nmol/L  factor: × 65.1
    ("Total T3", "nmol/l"):  (65.1,   "ng/dL"),
    ("Total T3", "ng/ml"):   (100.0,  "ng/dL"),
    ("Free T3",  "pg/ml"):   (100.0,  "pg/dL"),   # kept for backward compat
    ("Total T4", "ng/ml"):   (0.1,    "ug/dL"),   # kept for backward compat

    # ══ VITAMINS / NUTRITION ═══════════════════════════════════════════════════
    # Vitamin D: DB ng/mL  SI: nmol/L  factor: × 0.4006
    ("Vitamin D",   "nmol/l"):  (0.4006, "ng/mL"),
    # Vitamin B12: DB pg/mL  SI: pmol/L  factor: × 1.3554
    ("Vitamin B12", "pmol/l"):  (1.3554, "pg/mL"),
    # Folate: DB ng/mL  SI: nmol/L  factor: × 0.4413
    ("Folate",      "nmol/l"):  (0.4413, "ng/mL"),
    # Zinc: DB ug/dL  SI: umol/L  factor: × 6.535
    ("Zinc",        "umol/l"):  (6.535, "ug/dL"),
    # Copper: DB ug/dL  SI: umol/L  factor: × 6.353
    ("Copper",      "umol/l"):  (6.353, "ug/dL"),
    # Selenium: DB ng/mL  SI: umol/L  factor: × 79.0
    ("Selenium",    "umol/l"):  (79.0, "ng/mL"),

    # ══ HORMONES ═══════════════════════════════════════════════════════════════
    # Cortisol: DB ug/dL  SI: nmol/L  factor: ÷ 27.586
    ("Cortisol",  "nmol/l"):  (0.036246, "ug/dL"),
    # Testosterone: DB ng/dL  SI: nmol/L  factor: × 28.818
    ("Total Testosterone", "nmol/l"):  (28.818, "ng/dL"),
    ("Free Testosterone",  "pmol/l"):  (0.2884, "pg/mL"),
    # Estradiol: DB pg/mL  SI: pmol/L  factor: × 0.2724
    ("Estradiol",   "pmol/l"):  (0.2724, "pg/mL"),
    # Progesterone: DB ng/mL  SI: nmol/L  factor: × 0.3145
    ("Progesterone","nmol/l"):  (0.3145, "ng/mL"),
    # Prolactin: DB ng/mL  SI: mIU/L  factor: × 0.04717
    ("Prolactin",   "miu/l"):   (0.04717, "ng/mL"),
    # PTH: DB pg/mL  SI: pmol/L  factor: × 9.43
    ("PTH", "pmol/l"):  (9.43, "pg/mL"),
    # IGF-1: DB ng/mL  SI: nmol/L  factor: × 130.5
    ("IGF-1", "nmol/l"):  (130.5, "ng/mL"),
    # DHEA-S: DB ug/dL  SI: umol/L  factor: × 36.81
    ("DHEA-S", "umol/l"): (36.81, "ug/dL"),
    # SHBG: nmol/L — already DB unit, no conversion
    # Insulin: DB uIU/mL = mIU/L — same numeric; pmol/L → × 0.1438
    ("Insulin",   "pmol/l"):  (0.1438, "uIU/mL"),
    # C-Peptide: DB ng/mL  SI: pmol/L  factor: × 0.003017
    ("C-Peptide", "pmol/l"):  (0.003017, "ng/mL"),

    # ══ CARDIAC MARKERS ════════════════════════════════════════════════════════
    # Troponin I: DB ng/mL  SI: ug/L = ng/mL — same numeric
    ("Troponin I",               "ug/l"):  (1.0, "ng/mL"),
    ("Troponin T",               "ug/l"):  (1.0, "ng/mL"),
    ("High-sensitivity Troponin I", "pg/ml"): (1.0, "ng/L"),  # hsTnI DB is ng/L
    # BNP / NT-proBNP: DB pg/mL  SI: ng/L = pg/mL — same numeric
    ("BNP",       "ng/l"):  (1.0, "pg/mL"),
    ("NT-proBNP", "ng/l"):  (1.0, "pg/mL"),
    # CK / Myoglobin — U/L or ug/L, already compatible with DB

    # ══ INFLAMMATORY / CRP ══════════════════════════════════════════════════════
    # CRP: DB mg/L  some labs report mg/dL → × 10
    ("CRP",   "mg/dl"): (10.0, "mg/L"),
    ("hsCRP", "mg/dl"): (10.0, "mg/L"),

    # ══ COAGULATION ════════════════════════════════════════════════════════════
    # D-Dimer: DB ug/mL FEU; some report ng/mL → ÷ 1000
    ("D-Dimer", "ng/ml"):   (0.001, "ug/mL FEU"),
    ("D-Dimer", "mg/l"):    (1.0,   "ug/mL FEU"),   # mg/L FEU = ug/mL FEU

    # ══ TUMOUR MARKERS ════════════════════════════════════════════════════════
    # All in ng/mL or U/mL — already compatible; no conversions needed currently

    # ══ BONE METABOLISM ════════════════════════════════════════════════════════
    # Calcium already handled above
    # PTH already handled above
    # Osteocalcin: DB ng/mL  SI: nmol/L  factor: × 17.75 (Mw=5800)
    ("Osteocalcin", "nmol/l"): (17.75, "ng/mL"),

    # ══ METABOLIC ═════════════════════════════════════════════════════════════
    # Lactic Acid: DB mmol/L  if mg/dL → ÷ 9.01
    ("Lactic Acid", "mg/dl"): (0.111, "mmol/L"),
    # Ammonia: DB ug/dL  SI: umol/L  (already above)

    # ══ HAEMATOLOGY EXTENDED ══════════════════════════════════════════════════
    # PCV/Hematocrit: DB %  SI: L/L  factor: × 100
    ("Packed Cell Volume",  "l/l"):   (100.0, "%"),
    ("Hematocrit",          "l/l"):   (100.0, "%"),
    # MCHC: DB g/dL  UK/AU report g/L → ÷ 10
    ("MCHC", "g/l"):  (0.1, "g/dL"),
    # Hemoglobin: DB g/dL  SI: mmol/L  factor: × 1.6113
    ("Hemoglobin", "mmol/l"):  (1.6113, "g/dL"),
    # Reticulocyte Count: DB /cumm (absolute cells)  if reported as /mm3 same numeric
    # Retics in 10^9/L → × 1 (same as /cumm ÷ 1)

    # ══ ENZYME ACTIVITIES (ukat/L and nkat/L) ═════════════════════════════════
    # SI: ukat/L → U/L (= IU/L) factor: × 60  (1 ukat = 60 U)
    ("ALT",      "ukat/l"): (60.0, "U/L"),
    ("AST",      "ukat/l"): (60.0, "U/L"),
    ("ALP",      "ukat/l"): (60.0, "U/L"),
    ("GGT",      "ukat/l"): (60.0, "U/L"),
    ("LDH",      "ukat/l"): (60.0, "U/L"),
    ("Amylase",  "ukat/l"): (60.0, "U/L"),
    ("Lipase",   "ukat/l"): (60.0, "U/L"),
    ("CK",       "ukat/l"): (60.0, "U/L"),
    ("CK-MB",    "ukat/l"): (60.0, "U/L"),
    ("Bone ALP", "ukat/l"): (60.0, "U/L"),
    # nkat/L → U/L factor: × 0.06
    ("ALT",      "nkat/l"): (0.06, "U/L"),
    ("AST",      "nkat/l"): (0.06, "U/L"),
    ("ALP",      "nkat/l"): (0.06, "U/L"),
    ("GGT",      "nkat/l"): (0.06, "U/L"),
    ("LDH",      "nkat/l"): (0.06, "U/L"),
    ("Amylase",  "nkat/l"): (0.06, "U/L"),
    ("Lipase",   "nkat/l"): (0.06, "U/L"),
    ("CK",       "nkat/l"): (0.06, "U/L"),
    ("CK-MB",    "nkat/l"): (0.06, "U/L"),

    # ══ PROTEINS / IMMUNOGLOBULINS ════════════════════════════════════════════
    # Fibrinogen: DB mg/dL  SI: umol/L  factor: × 34.0 (Mw~340 kDa)
    ("Fibrinogen",  "umol/l"):  (34.0,  "mg/dL"),
    # Fibrinogen: DB mg/dL  if reported g/L → × 100
    ("Fibrinogen",  "g/l"):     (100.0, "mg/dL"),
    # Transferrin: DB mg/dL  SI: g/L → × 100
    ("Transferrin", "g/l"):     (100.0, "mg/dL"),
    # Prealbumin: DB mg/dL  SI: g/L → × 100
    ("Prealbumin",  "g/l"):     (100.0, "mg/dL"),
    # Complement C3 / C4: DB mg/dL  SI: g/L → × 100
    ("C3 Complement", "g/l"):   (100.0, "mg/dL"),
    ("C4 Complement", "g/l"):   (100.0, "mg/dL"),
    # Immunoglobulins: DB mg/dL  SI: g/L → × 100
    ("IgG", "g/l"):  (100.0, "mg/dL"),
    ("IgA", "g/l"):  (100.0, "mg/dL"),
    ("IgM", "g/l"):  (100.0, "mg/dL"),
    # IgE: DB IU/mL  kU/L = IU/mL — same numeric (no-op)
    ("IgE", "ku/l"): (1.0, "IU/mL"),

    # ══ HORMONES EXTENDED ═════════════════════════════════════════════════════
    # FSH / LH: DB mIU/mL = IU/L — same numeric; no conversion needed
    # AMH: DB ng/mL  SI: pmol/L  factor: × 0.14003
    ("AMH", "pmol/l"):  (0.14003, "ng/mL"),
    # Beta-hCG: DB mIU/mL = IU/L — same numeric
    # ACTH: DB pg/mL  SI: pmol/L  factor: × 4.511
    ("ACTH", "pmol/l"):  (4.511, "pg/mL"),
    # Aldosterone: DB ng/dL  SI: pmol/L  factor: × 0.036095
    ("Aldosterone", "pmol/l"):  (0.036095, "ng/dL"),
    # Aldosterone: DB ng/dL  SI: nmol/L  factor: × 36.095
    ("Aldosterone", "nmol/l"):  (36.095, "ng/dL"),
    # Renin: DB ng/mL/hr  SI: pmol/L/hr  factor: × 1.267
    ("Renin", "pmol/l/hr"): (1.267, "ng/mL/hr"),
    # Growth Hormone: DB ng/mL  SI: mIU/L  factor: × 0.333
    ("Growth Hormone", "miu/l"): (0.333, "ng/mL"),

    # ══ VITAMINS EXTENDED ═════════════════════════════════════════════════════
    # Vitamin A (Retinol): DB ug/dL  SI: umol/L  factor: × 28.645
    ("Vitamin A", "umol/l"):  (28.645, "ug/dL"),
    # Vitamin E (Tocopherol): DB mg/L  SI: umol/L  factor: × 0.43073
    ("Vitamin E", "umol/l"):  (0.43073, "mg/L"),
    # Vitamin C (Ascorbic Acid): DB mg/dL  SI: umol/L  factor: × 0.017607
    ("Vitamin C", "umol/l"):  (0.017607, "mg/dL"),

    # ══ LIPIDS EXTENDED ═══════════════════════════════════════════════════════
    # Lipoprotein(a): DB mg/dL  SI: nmol/L  factor: × 0.4 (approximate, Lp(a) Mw variable)
    ("Lipoprotein(a)", "nmol/l"): (0.4, "mg/dL"),
    # ApoA1 / ApoB: DB mg/dL  if reported mg/L → ÷ 10
    ("Apolipoprotein A1", "mg/l"): (0.1, "mg/dL"),
    ("Apolipoprotein B",  "mg/l"): (0.1, "mg/dL"),

    # ══ CARDIAC EXTENDED ══════════════════════════════════════════════════════
    # Myoglobin: DB ng/mL  SI: nmol/L  factor: × 17.8 (Mw~17800)
    ("Myoglobin", "nmol/l"): (17.8, "ng/mL"),

    # ══ BONE METABOLISM EXTENDED ══════════════════════════════════════════════
    # C-Telopeptide (CTX): DB ng/mL  SI: pmol/L  factor: × 0.286 (Mw~3500)
    ("C-Telopeptide", "pmol/l"): (0.286, "ng/mL"),

    # ══ AUTOIMMUNE / SPECIAL PROTEINS ════════════════════════════════════════
    # Beta-2 Microglobulin: DB mg/L  SI: umol/L  factor: × 11.8 (Mw~11800)
    ("Beta-2 Microglobulin", "umol/l"):  (11.8, "mg/L"),
    # Beta-2 Microglobulin: ug/mL = mg/L — same numeric
    ("Beta-2 Microglobulin", "ug/ml"):   (1.0, "mg/L"),
    # Ceruloplasmin: DB mg/dL  SI: g/L → × 100
    ("Ceruloplasmin", "g/l"):  (100.0, "mg/dL"),
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


def _normalise_unit(raw_unit: str) -> str:
    """
    Normalise a raw unit string to a canonical lowercase token for lookup.
    Handles the many typographic variants found in global lab reports:
      - Greek/micro prefix: µ (U+00B5), μ (U+03BC), u  → all become 'u'
      - Superscripts: ³→3, ²→2, ⁹→9, ¹→1
      - Multiplication signs: ×, ·  → 'x'
      - Whitespace, parentheses, dots stripped
      - Per-unit slashes normalised
    """
    if not raw_unit:
        return ""
    u = raw_unit.strip()
    # Greek mu / micro sign → 'u'
    u = u.replace("\u03bc", "u").replace("\u00b5", "u")
    # Superscript digits
    for sup, dig in [("³", "3"), ("²", "2"), ("⁹", "9"), ("¹", "1"), ("⁰", "0")]:
        u = u.replace(sup, dig)
    # Multiplication / middle dot
    u = u.replace("×", "x").replace("·", "")
    # Remove spaces, parentheses, trailing dots
    u = u.replace(" ", "").replace("(", "").replace(")", "").replace(".", "")
    return u.lower()


def apply_unit_conversion(param, raw_unit, value):
    """
    Convert value to DB unit when extracted unit differs from DB unit.
    Handles conventional ↔ SI differences across global labs.

    Conversion tuple formats:
      (factor, unit)          → result = value × factor
      (factor, unit, offset)  → result = (value × factor) + offset
    The offset form is used for affine conversions (e.g. HbA1c IFCC→NGSP).
    """
    if not raw_unit:
        return value
    normalised = _normalise_unit(raw_unit)
    key = (param, normalised)
    conversion = UNIT_CONVERSIONS.get(key)
    if conversion:
        factor = conversion[0]
        offset = conversion[2] if len(conversion) > 2 else 0.0
        target_unit = conversion[1]
        result = (value * factor) + offset
        logger.debug(
            "unit_conversion: %s %s '%s' x%s +%s -> %s %s",
            param, value, raw_unit, factor, offset, result, target_unit,
        )
        return result
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

        # ── Priority 1: reference range embedded in the report ──────────────
        # Report-printed ranges are most authoritative — they already account
        # for patient age/gender/lab-specific methodology.
        # IMPORTANT: do NOT apply scale normalization here. Both the patient
        # value and the ref range were printed by the lab in the same unit
        # (e.g. both in thou/mm3). Scaling the value but not the range would
        # produce false HIGH/LOW flags (e.g. WBC 6.10→6100 vs ref 4.0-10.0).
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

        # Scale correction and unit conversion only apply when using DB ranges.
        # Labs that print their own ref ranges use consistent units throughout,
        # so no scaling is needed for the report-range path above.
        value = normalize_scale(param, value)
        value = apply_unit_conversion(param, raw_unit, value)

        # ── Priority 2: curated reference database ───────────────────────────
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

        # ── Priority 3: no range at all — pass through with UNKNOWN flag ─────
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
