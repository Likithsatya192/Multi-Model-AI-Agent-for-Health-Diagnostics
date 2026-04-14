"""
Universal blood report parameter extraction.

Handles ANY blood test panel from ANY country's lab format:
  CBC/FBC, LFT/LFTs, KFT/RFT, Lipid Panel, Thyroid, Coagulation,
  Iron Studies, HbA1c/Diabetes, Electrolytes, and mixed/comprehensive panels.

Strategy:
  1. Dynamic JSON extraction — no Pydantic format instructions (saves ~700 tokens)
  2. Comprehensive alias map (483 aliases) — maps raw lab names to canonical names
  3. Report-embedded reference ranges — captured per value, used as fallback in validation
  4. Fast 8b model (20k TPM) for extraction; quality 70b as fallback
"""

import re
import json
import logging
from typing import List, Optional, Union
from utils.llm_utils import get_fast_llm, get_llm

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Universal alias map  (lowercase key → canonical name)
# Covers: Indian, US, European, WHO, ISO lab report naming conventions
# ─────────────────────────────────────────────────────────────────────────────
PARAM_ALIASES: dict[str, str] = {

    # ══════════════════ HAEMATOLOGY / CBC ══════════════════

    # Hemoglobin
    "hemoglobin": "Hemoglobin", "haemoglobin": "Hemoglobin",
    "hb": "Hemoglobin", "hgb": "Hemoglobin", "hb concentration": "Hemoglobin",
    "hb conc": "Hemoglobin", "hb level": "Hemoglobin",
    "blood hemoglobin": "Hemoglobin", "haemoglobin (hb)": "Hemoglobin",
    "hemoglobin (hb)": "Hemoglobin",

    # RBC
    "rbc": "Total RBC count", "rbc count": "Total RBC count",
    "total rbc": "Total RBC count", "total rbc count": "Total RBC count",
    "red blood cell count": "Total RBC count", "red blood cells": "Total RBC count",
    "red cell count": "Total RBC count", "erythrocyte count": "Total RBC count",
    "erythrocytes": "Total RBC count", "red blood corpuscles": "Total RBC count",
    "rbc (total)": "Total RBC count",

    # PCV / HCT
    "pcv": "Packed Cell Volume", "hct": "Packed Cell Volume",
    "hematocrit": "Packed Cell Volume", "haematocrit": "Packed Cell Volume",
    "packed cell volume": "Packed Cell Volume", "packed cell vol": "Packed Cell Volume",
    "packed cell volume (pcv)": "Packed Cell Volume",

    # MCV
    "mcv": "MCV", "mean corpuscular volume": "MCV", "mean cell volume": "MCV",
    "mean corpuscular vol": "MCV", "mean cell vol": "MCV",

    # MCH
    "mch": "MCH", "mean corpuscular hemoglobin": "MCH",
    "mean cell hemoglobin": "MCH", "mean corpuscular haemoglobin": "MCH",

    # MCHC
    "mchc": "MCHC", "mean corpuscular hemoglobin concentration": "MCHC",
    "mean cell hemoglobin concentration": "MCHC",
    "mean corpuscular haemoglobin concentration": "MCHC",

    # RDW
    "rdw": "RDW", "rdw-cv": "RDW", "rdw cv": "RDW", "rdw-sd": "RDW",
    "red cell distribution width": "RDW", "red blood cell distribution width": "RDW",
    "rbc distribution width": "RDW", "red cell dist width": "RDW",

    # WBC / TLC
    "wbc": "Total WBC count", "tlc": "Total WBC count", "twbc": "Total WBC count",
    "total wbc": "Total WBC count", "total wbc count": "Total WBC count",
    "total leucocyte count": "Total WBC count", "total leukocyte count": "Total WBC count",
    "leukocyte count": "Total WBC count", "leucocyte count": "Total WBC count",
    "white blood cell count": "Total WBC count", "white blood cells": "Total WBC count",
    "white cell count": "Total WBC count", "wbc count": "Total WBC count",
    "total wbc (tlc)": "Total WBC count",

    # Platelets
    "platelets": "Platelet Count", "platelet count": "Platelet Count",
    "plt": "Platelet Count", "platelet": "Platelet Count",
    "thrombocyte count": "Platelet Count", "thrombocytes": "Platelet Count",
    "blood platelets": "Platelet Count", "plt count": "Platelet Count",

    # Differential — percent
    "neutrophils": "Neutrophils", "neutrophil": "Neutrophils",
    "neutrophils %": "Neutrophils", "neutrophils%": "Neutrophils",
    "polymorphs": "Neutrophils", "polymorphonuclear": "Neutrophils",
    "pmn": "Neutrophils", "segs": "Neutrophils",
    "segmented neutrophils": "Neutrophils", "gran%": "Neutrophils",
    "granulocytes%": "Neutrophils", "neu%": "Neutrophils",
    "poly": "Neutrophils",

    "lymphocytes": "Lymphocytes", "lymphocyte": "Lymphocytes",
    "lymphs": "Lymphocytes", "lymphs%": "Lymphocytes",
    "lymphocytes%": "Lymphocytes", "lym%": "Lymphocytes",

    "monocytes": "Monocytes", "monocyte": "Monocytes",
    "mono": "Monocytes", "mono%": "Monocytes",
    "monocytes%": "Monocytes", "mon%": "Monocytes",

    "eosinophils": "Eosinophils", "eosinophil": "Eosinophils",
    "eos": "Eosinophils", "eos%": "Eosinophils",
    "eosinophils%": "Eosinophils", "eosino": "Eosinophils",

    "basophils": "Basophils", "basophil": "Basophils",
    "baso": "Basophils", "baso%": "Basophils",
    "basophils%": "Basophils", "bas%": "Basophils",

    "band cells": "Band Neutrophils", "bands": "Band Neutrophils",
    "band neutrophils": "Band Neutrophils", "stab cells": "Band Neutrophils",

    # Absolute differential counts
    "absolute neutrophils": "Absolute Neutrophils",
    "absolute neutrophil count": "Absolute Neutrophils",
    "anc": "Absolute Neutrophils", "neutrophils absolute": "Absolute Neutrophils",
    "abs neutrophils": "Absolute Neutrophils", "abs. neutrophils": "Absolute Neutrophils",
    "neu#": "Absolute Neutrophils", "gran#": "Absolute Neutrophils",

    "absolute lymphocytes": "Absolute Lymphocytes",
    "absolute lymphocyte count": "Absolute Lymphocytes",
    "alc": "Absolute Lymphocytes", "lymphocytes absolute": "Absolute Lymphocytes",
    "abs lymphocytes": "Absolute Lymphocytes", "abs. lymphocytes": "Absolute Lymphocytes",
    "lym#": "Absolute Lymphocytes",

    "absolute monocytes": "Absolute Monocytes",
    "absolute monocyte count": "Absolute Monocytes",
    "monocytes absolute": "Absolute Monocytes",
    "abs monocytes": "Absolute Monocytes", "abs. monocytes": "Absolute Monocytes",
    "mon#": "Absolute Monocytes",

    "absolute eosinophils": "Absolute Eosinophils",
    "absolute eosinophil count": "Absolute Eosinophils",
    "eosinophils absolute": "Absolute Eosinophils",
    "abs eosinophils": "Absolute Eosinophils", "abs. eosinophils": "Absolute Eosinophils",
    "eos#": "Absolute Eosinophils",

    "absolute basophils": "Absolute Basophils",
    "absolute basophil count": "Absolute Basophils",
    "basophils absolute": "Absolute Basophils",
    "abs basophils": "Absolute Basophils", "abs. basophils": "Absolute Basophils",
    "bas#": "Absolute Basophils",

    # ESR
    "esr": "ESR", "erythrocyte sedimentation rate": "ESR",
    "sedimentation rate": "ESR", "sed rate": "ESR",
    "westergren": "ESR", "wintrobe esr": "ESR",
    "erythrocyte sed. rate": "ESR",

    # MPV / PDW / PCT
    "mpv": "MPV", "mean platelet volume": "MPV", "mean thrombocyte volume": "MPV",
    "pdw": "PDW", "platelet distribution width": "PDW", "plt distribution width": "PDW",
    "pct": "PCT", "plateletcrit": "PCT", "plt crit": "PCT",

    # ══════════════════ LIVER FUNCTION TESTS ══════════════════

    "alt": "ALT", "sgpt": "ALT", "alanine aminotransferase": "ALT",
    "alanine transaminase": "ALT", "s. alt": "ALT", "serum alt": "ALT",
    "serum sgpt": "ALT", "s.g.p.t": "ALT",

    "ast": "AST", "sgot": "AST", "aspartate aminotransferase": "AST",
    "aspartate transaminase": "AST", "s. ast": "AST", "serum ast": "AST",
    "serum sgot": "AST", "s.g.o.t": "AST",

    "alp": "ALP", "alkaline phosphatase": "ALP", "alk phos": "ALP",
    "alkaline phosphomonoesterase": "ALP", "s. alp": "ALP", "serum alp": "ALP",
    "alk phosphatase": "ALP",

    "ggt": "GGT", "gamma-glutamyl transferase": "GGT",
    "gamma glutamyl transferase": "GGT", "gamma gt": "GGT", "ggtp": "GGT",
    "gamma glutamyl transpeptidase": "GGT", "γ-gt": "GGT", "serum ggt": "GGT",

    "total bilirubin": "Total Bilirubin", "bilirubin total": "Total Bilirubin",
    "t. bilirubin": "Total Bilirubin", "t bilirubin": "Total Bilirubin",
    "tbil": "Total Bilirubin", "tbili": "Total Bilirubin", "bil total": "Total Bilirubin",
    "serum bilirubin (total)": "Total Bilirubin", "bilirubin (total)": "Total Bilirubin",
    "s. bilirubin (t)": "Total Bilirubin",

    "direct bilirubin": "Direct Bilirubin", "bilirubin direct": "Direct Bilirubin",
    "d. bilirubin": "Direct Bilirubin", "d bilirubin": "Direct Bilirubin",
    "dbil": "Direct Bilirubin", "conjugated bilirubin": "Direct Bilirubin",
    "bilirubin (direct)": "Direct Bilirubin", "s. bilirubin (d)": "Direct Bilirubin",

    "indirect bilirubin": "Indirect Bilirubin", "bilirubin indirect": "Indirect Bilirubin",
    "i. bilirubin": "Indirect Bilirubin", "i bilirubin": "Indirect Bilirubin",
    "ibil": "Indirect Bilirubin", "unconjugated bilirubin": "Indirect Bilirubin",
    "bilirubin (indirect)": "Indirect Bilirubin", "s. bilirubin (i)": "Indirect Bilirubin",

    "total protein": "Total Protein", "protein total": "Total Protein",
    "t. protein": "Total Protein", "tp": "Total Protein",
    "serum protein": "Total Protein", "serum total protein": "Total Protein",
    "s. protein (total)": "Total Protein",

    "albumin": "Albumin", "serum albumin": "Albumin",
    "alb": "Albumin", "s. albumin": "Albumin",

    "globulin": "Globulin", "serum globulin": "Globulin", "glob": "Globulin",

    "a/g ratio": "A/G Ratio", "ag ratio": "A/G Ratio",
    "albumin/globulin ratio": "A/G Ratio", "albumin globulin ratio": "A/G Ratio",
    "albumin : globulin": "A/G Ratio",

    "ldh": "LDH", "lactate dehydrogenase": "LDH", "lactic dehydrogenase": "LDH",
    "serum ldh": "LDH",

    # ══════════════════ KIDNEY / RENAL FUNCTION ══════════════════

    "creatinine": "Creatinine", "serum creatinine": "Creatinine",
    "s. creatinine": "Creatinine", "s creatinine": "Creatinine",
    "cre": "Creatinine", "cr": "Creatinine",

    "blood urea nitrogen": "BUN", "bun": "BUN",
    "urea nitrogen": "BUN", "serum urea nitrogen": "BUN",

    "blood urea": "Blood Urea", "urea": "Blood Urea",
    "serum urea": "Blood Urea", "s. urea": "Blood Urea", "bu": "Blood Urea",

    "uric acid": "Uric Acid", "serum uric acid": "Uric Acid",
    "s. uric acid": "Uric Acid", "sua": "Uric Acid", "ua": "Uric Acid",

    "egfr": "eGFR", "estimated gfr": "eGFR",
    "glomerular filtration rate": "eGFR", "creatinine clearance": "eGFR",
    "estimated glomerular filtration rate": "eGFR",

    # ══════════════════ ELECTROLYTES ══════════════════

    "sodium": "Sodium", "serum sodium": "Sodium", "na": "Sodium",
    "na+": "Sodium", "s. sodium": "Sodium",

    "potassium": "Potassium", "serum potassium": "Potassium",
    "k": "Potassium", "k+": "Potassium", "s. potassium": "Potassium",

    "chloride": "Chloride", "serum chloride": "Chloride",
    "cl": "Chloride", "cl-": "Chloride",

    "bicarbonate": "Bicarbonate", "serum bicarbonate": "Bicarbonate",
    "hco3": "Bicarbonate", "hco3-": "Bicarbonate", "total co2": "Bicarbonate",

    "calcium": "Calcium", "serum calcium": "Calcium",
    "ca": "Calcium", "ca2+": "Calcium", "s. calcium": "Calcium",

    "phosphorus": "Phosphorus", "serum phosphorus": "Phosphorus",
    "phosphate": "Phosphorus", "serum phosphate": "Phosphorus",
    "inorganic phosphorus": "Phosphorus",

    "magnesium": "Magnesium", "serum magnesium": "Magnesium",
    "mg": "Magnesium", "mg2+": "Magnesium",

    # ══════════════════ LIPID PANEL ══════════════════

    "total cholesterol": "Total Cholesterol", "cholesterol": "Total Cholesterol",
    "cholesterol total": "Total Cholesterol", "serum cholesterol": "Total Cholesterol",
    "tc": "Total Cholesterol", "chol": "Total Cholesterol",
    "cholesterol, total": "Total Cholesterol",

    "triglycerides": "Triglycerides", "triglyceride": "Triglycerides",
    "tg": "Triglycerides", "triacylglycerol": "Triglycerides",
    "trig": "Triglycerides", "serum triglycerides": "Triglycerides",
    "triglycerides (tg)": "Triglycerides",

    "hdl cholesterol": "HDL Cholesterol", "hdl": "HDL Cholesterol",
    "hdl-c": "HDL Cholesterol", "high density lipoprotein": "HDL Cholesterol",
    "hdl-cholesterol": "HDL Cholesterol", "hdl chol": "HDL Cholesterol",
    "hdl (good cholesterol)": "HDL Cholesterol",

    "ldl cholesterol": "LDL Cholesterol", "ldl": "LDL Cholesterol",
    "ldl-c": "LDL Cholesterol", "low density lipoprotein": "LDL Cholesterol",
    "ldl-cholesterol": "LDL Cholesterol", "ldl chol": "LDL Cholesterol",
    "ldl (bad cholesterol)": "LDL Cholesterol",

    "vldl cholesterol": "VLDL Cholesterol", "vldl": "VLDL Cholesterol",
    "vldl-c": "VLDL Cholesterol", "very low density lipoprotein": "VLDL Cholesterol",

    "non-hdl cholesterol": "Non-HDL Cholesterol",
    "non hdl cholesterol": "Non-HDL Cholesterol", "non-hdl": "Non-HDL Cholesterol",

    "tc/hdl ratio": "TC/HDL Ratio", "cholesterol/hdl ratio": "TC/HDL Ratio",
    "total cholesterol/hdl": "TC/HDL Ratio", "tc:hdl": "TC/HDL Ratio",
    "ldl/hdl ratio": "LDL/HDL Ratio", "ldl:hdl": "LDL/HDL Ratio",

    # ══════════════════ THYROID ══════════════════

    "tsh": "TSH", "thyroid stimulating hormone": "TSH",
    "thyrotropin": "TSH", "s. tsh": "TSH", "serum tsh": "TSH",
    "tsh3": "TSH", "tsh (3rd generation)": "TSH",

    "free t3": "Free T3", "ft3": "Free T3",
    "free triiodothyronine": "Free T3", "triiodothyronine free": "Free T3",
    "t3 (free)": "Free T3",

    "total t3": "Total T3", "t3": "Total T3",
    "triiodothyronine": "Total T3", "serum t3": "Total T3",
    "t3 (total)": "Total T3",

    "free t4": "Free T4", "ft4": "Free T4",
    "free thyroxine": "Free T4", "thyroxine free": "Free T4",
    "t4 (free)": "Free T4",

    "total t4": "Total T4", "t4": "Total T4",
    "thyroxine": "Total T4", "serum t4": "Total T4",
    "thyroxine (total)": "Total T4", "t4 (total)": "Total T4",

    # ══════════════════ DIABETES / GLUCOSE ══════════════════

    "fasting blood glucose": "Fasting Blood Glucose",
    "fbs": "Fasting Blood Glucose", "fasting glucose": "Fasting Blood Glucose",
    "fasting blood sugar": "Fasting Blood Glucose", "fpg": "Fasting Blood Glucose",
    "fasting plasma glucose": "Fasting Blood Glucose",
    "glucose fasting": "Fasting Blood Glucose",
    "blood glucose (fasting)": "Fasting Blood Glucose",
    "fasting blood glucose (fbg)": "Fasting Blood Glucose",

    "postprandial glucose": "Postprandial Blood Glucose",
    "ppbs": "Postprandial Blood Glucose", "post meal glucose": "Postprandial Blood Glucose",
    "2-hour glucose": "Postprandial Blood Glucose",
    "post prandial blood sugar": "Postprandial Blood Glucose",
    "glucose pp": "Postprandial Blood Glucose",

    "random blood glucose": "Random Blood Glucose",
    "rbs": "Random Blood Glucose", "random glucose": "Random Blood Glucose",
    "blood glucose random": "Random Blood Glucose",
    "random blood sugar": "Random Blood Glucose",

    "hba1c": "HbA1c", "glycated hemoglobin": "HbA1c",
    "glycosylated hemoglobin": "HbA1c", "a1c": "HbA1c",
    "hemoglobin a1c": "HbA1c", "haemoglobin a1c": "HbA1c",
    "glycohemoglobin": "HbA1c", "glycohaemoglobin": "HbA1c",
    "hb a1c": "HbA1c",

    # Generic "glucose" → assume fasting context (most common)
    "glucose": "Fasting Blood Glucose", "blood glucose": "Fasting Blood Glucose",
    "blood sugar": "Fasting Blood Glucose",

    # ══════════════════ IRON STUDIES ══════════════════

    "serum iron": "Serum Iron", "iron": "Serum Iron",
    "s. iron": "Serum Iron", "fe": "Serum Iron",

    "tibc": "TIBC", "total iron binding capacity": "TIBC",
    "total iron-binding capacity": "TIBC", "iron binding capacity": "TIBC",

    "transferrin saturation": "Transferrin Saturation",
    "iron saturation": "Transferrin Saturation",
    "% saturation": "Transferrin Saturation", "ts%": "Transferrin Saturation",
    "tsat": "Transferrin Saturation", "% transferrin saturation": "Transferrin Saturation",

    "ferritin": "Serum Ferritin", "serum ferritin": "Serum Ferritin",
    "s. ferritin": "Serum Ferritin",

    # ══════════════════ COAGULATION ══════════════════

    "pt": "Prothrombin Time", "prothrombin time": "Prothrombin Time",
    "pro time": "Prothrombin Time", "pt (sec)": "Prothrombin Time",

    "inr": "INR", "international normalized ratio": "INR",
    "pt/inr": "INR", "pt-inr": "INR",

    "aptt": "aPTT", "activated partial thromboplastin time": "aPTT",
    "partial thromboplastin time": "aPTT", "ptt": "aPTT",
    "kaolin cephalin clotting time": "aPTT", "kcct": "aPTT",
    "aptt (sec)": "aPTT",

    "fibrinogen": "Fibrinogen", "plasma fibrinogen": "Fibrinogen",
    "fibrinogen level": "Fibrinogen",

    "d-dimer": "D-Dimer", "d dimer": "D-Dimer", "ddimer": "D-Dimer",
    "fibrin degradation products": "D-Dimer", "fdp": "D-Dimer",

    "bleeding time": "Bleeding Time", "bt": "Bleeding Time",
    "clotting time": "Clotting Time", "ct": "Clotting Time",

    # ══════════════════ INFLAMMATORY / CARDIAC / MISC ══════════════════

    "crp": "CRP", "c-reactive protein": "CRP", "c reactive protein": "CRP",
    "hs-crp": "hsCRP", "high sensitivity crp": "hsCRP",
    "high sensitivity c-reactive protein": "hsCRP",

    "amylase": "Amylase", "serum amylase": "Amylase",
    "lipase": "Lipase", "serum lipase": "Lipase",

    "troponin i": "Troponin I", "troponin t": "Troponin T",
    "troponin": "Troponin I", "cardiac troponin": "Troponin I",
    "ctni": "Troponin I",

    "bnp": "BNP", "brain natriuretic peptide": "BNP",
    "nt-probnp": "NT-proBNP", "nt probnp": "NT-proBNP",

    "prolactin": "Prolactin", "prl": "Prolactin",

    "vitamin d": "Vitamin D", "25-oh vitamin d": "Vitamin D",
    "25-hydroxyvitamin d": "Vitamin D", "vitamin d3": "Vitamin D",
    "25(oh)d": "Vitamin D", "25 oh vitamin d": "Vitamin D",
    "calcidiol": "Vitamin D",

    "vitamin b12": "Vitamin B12", "cobalamin": "Vitamin B12",
    "cyanocobalamin": "Vitamin B12", "b12": "Vitamin B12",

    "folate": "Folate", "folic acid": "Folate", "serum folate": "Folate",
    "serum folic acid": "Folate",

    "psa": "PSA", "prostate specific antigen": "PSA", "total psa": "PSA",
}


# Pydantic removed — we parse JSON directly for robustness and token efficiency


# ─────────────────────────────────────────────────────────────────────────────
# Canonical name resolution
# ─────────────────────────────────────────────────────────────────────────────

def _canonicalize(raw_name: str) -> str:
    """
    Map a raw lab parameter name to its canonical name using the alias dictionary.
    Applies progressively looser matching to maximize hit rate.
    Returns the raw_name itself if no match found (passed through for LLM downstream).
    """
    key = raw_name.strip().lower()

    # 1. Exact match
    if key in PARAM_ALIASES:
        return PARAM_ALIASES[key]

    # 2. Remove common noise tokens and retry
    noise = ["serum", "blood", "plasma", "s.", "b.", "(total)", "(direct)", "(indirect)",
             "(free)", "level", "count", "test", "assay", ",", ".", "-"]
    cleaned = key
    for n in noise:
        cleaned = cleaned.replace(n, " ")
    cleaned = " ".join(cleaned.split())
    if cleaned in PARAM_ALIASES:
        return PARAM_ALIASES[cleaned]

    # 3. Partial / contains match (longest match wins)
    best = None
    best_len = 0
    for alias, canonical in PARAM_ALIASES.items():
        if alias in key and len(alias) > best_len:
            best, best_len = canonical, len(alias)
    if best:
        return best

    # 4. No match — return original (pass-through; validator will use report ref ranges)
    return raw_name.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Numeric helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_float(val) -> Optional[float]:
    """Convert string/number to float, handling various formats."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        clean = str(val).replace(",", "").strip()
        match = re.search(r"(\d+(\.\d+)?)", clean)
        return float(match.group(1)) if match else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Compact extraction prompt — ~300 tokens (was ~1400 with Pydantic instructions)
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """Extract ALL laboratory test values from this blood/lab report. Output JSON only, no other text.

Required JSON structure:
{{
  "report_type": "CBC|LFT|KFT|LIPID|THYROID|COAGULATION|IRON|DIABETES|COMPREHENSIVE|MIXED|UNKNOWN",
  "patient_name": null,
  "patient_age": null,
  "patient_gender": null,
  "lab_values": [
    {{"raw_name": "Hemoglobin", "value": 6.8, "unit": "g/dL", "ref_low": 12.0, "ref_high": 15.5, "flag": "L"}},
    {{"raw_name": "WBC", "value": 7.5, "unit": "x10\u00b3/\u03bcL", "ref_low": 4.0, "ref_high": 11.0, "flag": null}}
  ]
}}

CORE RULES:
1. value = patient's RESULT only — the first standalone number immediately after the parameter name.
2. ref_low / ref_high = reference range from the report. Null if absent.
   Reference ranges appear as: "12.0-17.5" | "12.0 \u2013 17.5" | "(12.0-17.5)" | "12.0 to 17.5" | "Ref: 12-17"
3. flag = abnormal marker as printed: H / L / HH / LL / HIGH / LOW / A / * / \u2191 / \u2193 / CRITICAL
   (null if absent — do NOT infer the flag; only capture what is printed)
4. Extract ALL parameters visible in the report, including non-CBC or unknown test names.
5. Handles any panel: CBC, LFT, KFT, Lipid, Thyroid, Coagulation, Iron, Electrolytes, HbA1c, etc.

UNIT & SCALE RULES:
6. OCR character corrections inside numbers: O\u21920, l\u21921, I\u21921, S\u21925 (e.g. "l2.5"\u219212.5, "O.9"\u21920.9)
7. European decimal comma: "6,8"\u21926.8; thousands separator: "1.234,5"\u21921234.5
8. Indian lakh notation: "1.5 lakh"\u2192150000; "10,000"\u219210000
9. WBC/Platelets in x10\u00b3 format: keep as printed (e.g. 7.5 not 7500)

OCR / IMAGE REPORT RULES (applies when text is garbled or table columns are merged):
10. Each parameter line in OCR output typically follows this order:
      [Parameter Name] [Patient Value] [Unit] [Reference Range] [Flag]
    Example: "Haemoglobin 11.2 g/dL 13.0-17.0 L"
    Another: "S. Creatinine 0.9 mg/dL (0.7-1.3)"
11. When column structure is broken or text is merged on one line:
    - Parameter name = word(s) / abbreviation before the first number
    - Patient value  = FIRST numeric token after the parameter name
    - Reference range = a paired number pattern like "12.5-17.0" or "(12-17)"
    - Flag = a letter/symbol at end of line: H, L, A, *, \u2191, \u2193, or word HIGH/LOW
12. Disambiguating patient value vs. reference range:
    - Patient value appears BEFORE any range notation (dash between two numbers, parentheses, "to", "Ref:")
    - In a range "a-b", ref_low=a and ref_high=b (a < b always)
    - If only one number is visible after the parameter name, treat it as the patient value (ref_low/high = null)
13. Ignore: page headers, footers, lab name, doctor name, patient address, barcodes — only test results.
14. Differential counts (Neutrophils %, Lymphocytes %): extract as percentage values, not absolute counts.

REPORT:
{text}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Default units for canonical params (fallback when OCR misses unit)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_UNITS = {
    "Hemoglobin": "g/dL", "Total RBC count": "mill/cumm",
    "Packed Cell Volume": "%", "MCV": "fL", "MCH": "pg",
    "MCHC": "g/dL", "RDW": "%", "Total WBC count": "cumm",
    "Platelet Count": "cumm", "Neutrophils": "%", "Lymphocytes": "%",
    "Monocytes": "%", "Eosinophils": "%", "Basophils": "%",
    "Absolute Neutrophils": "cumm", "Absolute Lymphocytes": "cumm",
    "Absolute Monocytes": "cumm", "Absolute Eosinophils": "cumm",
    "Absolute Basophils": "cumm", "ESR": "mm/hr", "MPV": "fL",
    "PDW": "%", "PCT": "%",
    "ALT": "U/L", "AST": "U/L", "ALP": "U/L", "GGT": "U/L",
    "Total Bilirubin": "mg/dL", "Direct Bilirubin": "mg/dL",
    "Indirect Bilirubin": "mg/dL", "Total Protein": "g/dL",
    "Albumin": "g/dL", "Globulin": "g/dL", "LDH": "U/L",
    "Creatinine": "mg/dL", "BUN": "mg/dL", "Blood Urea": "mg/dL",
    "Uric Acid": "mg/dL", "eGFR": "mL/min/1.73m²",
    "Sodium": "mEq/L", "Potassium": "mEq/L", "Chloride": "mEq/L",
    "Bicarbonate": "mEq/L", "Calcium": "mg/dL", "Phosphorus": "mg/dL",
    "Magnesium": "mg/dL",
    "Total Cholesterol": "mg/dL", "Triglycerides": "mg/dL",
    "HDL Cholesterol": "mg/dL", "LDL Cholesterol": "mg/dL",
    "VLDL Cholesterol": "mg/dL",
    "TSH": "mIU/L", "Free T3": "pg/mL", "Total T3": "ng/dL",
    "Free T4": "ng/dL", "Total T4": "μg/dL",
    "Fasting Blood Glucose": "mg/dL", "Postprandial Blood Glucose": "mg/dL",
    "Random Blood Glucose": "mg/dL", "HbA1c": "%",
    "Serum Iron": "μg/dL", "TIBC": "μg/dL",
    "Transferrin Saturation": "%", "Serum Ferritin": "ng/mL",
    "Prothrombin Time": "sec", "INR": "", "aPTT": "sec",
    "Fibrinogen": "mg/dL", "D-Dimer": "μg/mL FEU",
    "CRP": "mg/L", "hsCRP": "mg/L", "Vitamin D": "ng/mL",
    "Vitamin B12": "pg/mL", "Folate": "ng/mL",
}


# ─────────────────────────────────────────────────────────────────────────────
# JSON parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_json(content: str) -> dict:
    """
    Robustly extract and parse JSON from LLM response.
    Handles ```json ... ``` markdown wrappers and leading/trailing text.
    """
    content = content.strip()
    # Strip markdown code fences
    for fence in ("```json", "```"):
        if fence in content:
            parts = content.split(fence)
            # Find the part after the opening fence that contains a JSON object
            for part in parts[1:]:
                candidate = part.split("```")[0].strip()
                if candidate.startswith("{"):
                    content = candidate
                    break
    # Find the outermost JSON object
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(content[start:end])


def _call_llm_json(prompt: str, primary_llm, fallback_llm) -> dict:
    """
    Call LLM and parse JSON response. Tries primary then fallback.
    Returns parsed dict or raises on total failure.
    """
    for i, llm in enumerate([primary_llm, fallback_llm]):
        label = "fast" if i == 0 else "quality"
        try:
            resp = llm.invoke(prompt)
            content = resp.content if hasattr(resp, "content") else str(resp)
            return _parse_llm_json(content)
        except json.JSONDecodeError as e:
            logger.warning(f"extract_parameters: {label} model JSON parse failed: {e}")
        except Exception as e:
            logger.warning(f"extract_parameters: {label} model call failed: {e}")
    raise RuntimeError("All LLM models failed for extraction")


# ─────────────────────────────────────────────────────────────────────────────
# Main node
# ─────────────────────────────────────────────────────────────────────────────

def extract_parameters_node(state):
    """
    Universal extraction node.
    Uses 8b fast model (20k TPM) as primary — adequate for JSON extraction.
    Falls back to 70b quality model on failure.
    Direct JSON parsing — no PydanticOutputParser overhead (~700 token saving).
    """
    text = state.raw_text or ""
    if not text.strip():
        return {
            "extracted_params": {},
            "errors": state.errors + ["No text to extract from."],
        }

    prompt = _EXTRACTION_PROMPT.format(text=text)

    # 8b: high TPM (20k/min), good at JSON extraction
    # 70b: quality fallback
    fast = get_fast_llm(max_tokens=2048)
    quality = get_llm(max_tokens=2048)

    try:
        data = _call_llm_json(prompt, fast, quality)
    except Exception as e:
        logger.error(f"extract_parameters: all models failed: {e}")
        return {
            "extracted_params": {},
            "errors": state.errors + [f"LLM extraction failed: {e}"],
        }

    report_type = str(data.get("report_type", "UNKNOWN")).upper()
    lab_values = data.get("lab_values", [])
    if not isinstance(lab_values, list):
        lab_values = []

    logger.info(
        f"extract_parameters: LLM returned {len(lab_values)} values, "
        f"report_type={report_type}"
    )

    # ── Build extracted_params dict ──────────────────────────────────────────
    extracted: dict = {}

    for lv in lab_values:
        if not isinstance(lv, dict):
            continue

        raw_name = str(lv.get("raw_name") or "").strip()
        if not raw_name:
            continue

        raw_val = _parse_float(lv.get("value"))
        if raw_val is None:
            logger.debug(f"extract_parameters: skipping '{raw_name}' — unparseable value")
            continue

        canonical = _canonicalize(raw_name)

        # Dedup: keep entry with more metadata
        if canonical in extracted:
            existing = extracted[canonical]
            has_meta = lv.get("ref_low") is not None or lv.get("flag")
            existing_meta = existing.get("report_ref_low") is not None or existing.get("report_flag")
            if not has_meta and existing_meta:
                continue

        unit = lv.get("unit") or DEFAULT_UNITS.get(canonical)
        ref_low = _parse_float(lv.get("ref_low"))
        ref_high = _parse_float(lv.get("ref_high"))
        flag = lv.get("flag")
        if flag:
            flag = str(flag).strip() or None

        extracted[canonical] = {
            "raw_name": raw_name,
            "value": raw_val,
            "unit": unit,
            "report_ref_low": ref_low,
            "report_ref_high": ref_high,
            "report_flag": flag,
            "scale_note": f"Universal extraction — {report_type}",
        }

    # ── Patient info ─────────────────────────────────────────────────────────
    patient_info = {}
    for src_key, dst_key in [
        ("patient_name", "Name"), ("patient_age", "Age"),
        ("patient_gender", "Gender"), ("report_date", "ReportDate"),
        ("lab_name", "LabName"),
    ]:
        val = data.get(src_key)
        if val:
            patient_info[dst_key] = str(val)

    logger.info(
        f"extract_parameters: {len(extracted)} canonical params, "
        f"report_type={report_type}"
    )

    return {
        "extracted_params": extracted,
        "patient_info": patient_info,
        "report_type": report_type,
    }
