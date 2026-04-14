"""
Universal blood report parameter extraction.

Handles ANY blood test panel from ANY country's lab format:
  CBC/FBC, LFT/LFTs, KFT/RFT, Lipid Panel, Thyroid, Coagulation,
  Iron Studies, HbA1c/Diabetes, Electrolytes, and mixed/comprehensive panels.

Strategy:
  1. Dynamic LLM extraction — no fixed schema; captures ALL visible lab values as a list
  2. Comprehensive alias map (250+ aliases) — maps raw lab names to canonical names
  3. Report-embedded reference ranges — captured per value, used as fallback in validation
  4. Quality model (70b) for max accuracy; fast model as fallback
"""

import re
import logging
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm, get_fast_llm

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


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models for universal dynamic extraction
# ─────────────────────────────────────────────────────────────────────────────

class LabValue(BaseModel):
    """One extracted lab result from any blood/lab report."""
    raw_name: str = Field(description="Parameter name EXACTLY as printed in the report")
    value: float = Field(description="Patient result numeric value (NOT reference range)")
    unit: Optional[str] = Field(None, description="Unit as printed: g/dL, mg/dL, %, U/L, etc.")
    ref_low: Optional[float] = Field(None, description="Reference range lower bound FROM the report")
    ref_high: Optional[float] = Field(None, description="Reference range upper bound FROM the report")
    flag: Optional[str] = Field(None, description="Abnormal flag from report: H, L, HH, LL, HIGH, LOW, CRITICAL, *, ↑, ↓, A, etc.")


class UniversalExtractionOutput(BaseModel):
    report_type: str = Field(
        description=(
            "Blood test panel type — one of: CBC, LFT, KFT, LIPID_PANEL, THYROID, "
            "COAGULATION, IRON_STUDIES, DIABETES, ELECTROLYTES, COMPREHENSIVE, MIXED, or UNKNOWN"
        )
    )
    lab_values: List[LabValue] = Field(
        description="ALL numeric lab values found in the report, without exception"
    )
    patient_name: Optional[str] = Field(None, description="Patient name if visible")
    patient_age: Optional[str] = Field(None, description="Patient age if visible")
    patient_gender: Optional[str] = Field(None, description="Patient gender if visible")
    report_date: Optional[str] = Field(None, description="Report/collection date if visible")
    lab_name: Optional[str] = Field(None, description="Laboratory/hospital name if visible")


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
# Universal extraction prompt
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """You are a universal medical lab report parser. Your ONLY job:
Extract EVERY numeric laboratory test result visible in the report below.

You MUST handle ANY blood/lab report regardless of:
- Panel type: CBC, LFT, KFT/RFT, Lipid Panel, Thyroid, Coagulation, Iron Studies, HbA1c, Electrolytes, Comprehensive, or any combination
- Country of origin: India (path labs, NABL-certified), USA (CLIA), Europe (ISO 15189), Middle East, Asia
- Lab format: portrait/landscape tables, multi-column, multi-row, handwritten OCR
- Number format: European decimals (1,5 = 1.5), Indian lakhs (1,50,000), scientific (10^3), with/without separators
- OCR quality: handle common errors: O↔0, l↔1, I↔1, rn↔m, S↔5

══════════════════════════════════════════
MANDATORY EXTRACTION RULES
══════════════════════════════════════════

1. PATIENT RESULT vs REFERENCE RANGE
   - Patient result = the column labeled "Result", "Value", "Patient Result", "Observed",
     or the FIRST numeric column after the parameter name.
   - Reference range = columns labeled "Reference Range", "Normal Range", "Ref Range",
     "Biological Reference Interval", or the format "X.X - Y.Y" / "X.X–Y.Y".
   - NEVER extract reference range values as the patient result.
   - If BOTH appear in same row: result is the patient value; capture ref_low/ref_high separately.

2. INCLUDE EVERYTHING
   - Extract ALL numeric test results. Do NOT filter by what you know.
   - Include parameters you don't recognize — extract them with their raw_name.
   - Do NOT skip a value because it looks normal or unimportant.

3. REFERENCE RANGES IN REPORT
   - When a reference range appears (e.g. "4.0 - 11.0", "13.0-17.0"), extract ref_low and ref_high.
   - These are critical fallbacks when our database lacks a parameter.

4. FLAGS
   - Capture any flag printed next to or after the value:
     H, L, HH, LL, HIGH, LOW, CRITICAL, A (abnormal), *, ↑, ↓, +, ++, +++
   - If no flag printed: set flag to null (do NOT infer H/L yourself).

5. OCR ERROR HANDLING
   - "O" in a numeric context → likely "0"
   - Decimal separators: "," in European format = ".", "." in Indian = thousands separator if >3 digits
   - "1.5 lakh" → 150000, "2 lakh" → 200000
   - Superscripts rendered flat: "4.5 x 10^3" = 4500 or keep as 4.5 based on unit context
   - For WBC/Platelets with x10³ unit → value as printed (do not multiply by 1000)
   - Stray characters from table borders: ignore single chars like |, —, /, _ adjacent to numbers

6. DEMOGRAPHICS
   - Extract patient_name, patient_age, patient_gender, report_date, lab_name if visible
   - Do NOT infer gender from name

7. REPORT TYPE
   - Identify the primary test panel(s) present

══════════════════════════════════════════
RAW REPORT TEXT
══════════════════════════════════════════
{text}

══════════════════════════════════════════
OUTPUT FORMAT
══════════════════════════════════════════
{format_instructions}
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
# Main node
# ─────────────────────────────────────────────────────────────────────────────

def extract_parameters_node(state):
    """
    Universal extraction node.
    Extracts ALL lab parameters from any blood report type.
    Maps raw names to canonical names via alias dictionary.
    Preserves report-embedded reference ranges for validation fallback.
    """
    text = state.raw_text or ""
    if not text.strip():
        return {
            "extracted_params": {},
            "errors": state.errors + ["No text to extract from."],
        }

    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=UniversalExtractionOutput)

    prompt = _EXTRACTION_PROMPT.format(
        text=text,
        format_instructions=parser.get_format_instructions(),
    )

    def _invoke(llm):
        raw_resp = llm.invoke(prompt)
        return parser.invoke(raw_resp)

    # Use quality model — accuracy is paramount for extraction
    result = None
    try:
        result = _invoke(get_llm())
        logger.info(
            f"extract_parameters: quality model succeeded — "
            f"report_type={result.report_type}, "
            f"{len(result.lab_values)} values extracted"
        )
    except Exception as e:
        logger.warning(f"extract_parameters quality model failed: {e}. Trying fast model.")
        try:
            result = _invoke(get_fast_llm())
            logger.info(
                f"extract_parameters: fast model fallback succeeded — "
                f"{len(result.lab_values)} values"
            )
        except Exception as e2:
            logger.error(f"extract_parameters: all models failed: {e2}")
            return {
                "extracted_params": {},
                "errors": state.errors + [f"LLM extraction failed: {e2}"],
            }

    # ── Build extracted_params dict ──────────────────────────────────────────
    extracted: dict = {}
    seen_canonical: dict = {}  # canonical_name → index, for dedup

    for lv in result.lab_values:
        raw_val = _parse_float(lv.value)
        if raw_val is None:
            logger.debug(f"extract_parameters: skipping '{lv.raw_name}' — value not parseable")
            continue

        canonical = _canonicalize(lv.raw_name)

        # Dedup: if same canonical already seen, keep the one with better metadata
        if canonical in seen_canonical:
            existing = extracted[canonical]
            # Prefer entry that has ref ranges or flag
            has_meta = lv.ref_low is not None or lv.flag is not None
            existing_meta = existing.get("report_ref_low") is not None or existing.get("report_flag") is not None
            if not has_meta and existing_meta:
                continue  # keep existing

        unit = lv.unit or DEFAULT_UNITS.get(canonical)
        ref_low = _parse_float(lv.ref_low)
        ref_high = _parse_float(lv.ref_high)

        extracted[canonical] = {
            "raw_name": lv.raw_name,
            "value": raw_val,
            "unit": unit,
            "report_ref_low": ref_low,    # from report's own reference column
            "report_ref_high": ref_high,
            "report_flag": lv.flag,       # as printed in report (H/L/etc.)
            "scale_note": f"Universal extraction — {result.report_type}",
        }
        seen_canonical[canonical] = True

    # ── Patient info ─────────────────────────────────────────────────────────
    patient_info = {}
    if result.patient_name:
        patient_info["Name"] = result.patient_name
    if result.patient_age:
        patient_info["Age"] = str(result.patient_age)
    if result.patient_gender:
        patient_info["Gender"] = result.patient_gender
    if result.report_date:
        patient_info["ReportDate"] = result.report_date
    if result.lab_name:
        patient_info["LabName"] = result.lab_name

    logger.info(
        f"extract_parameters: {len(extracted)} canonical params built, "
        f"report_type={result.report_type}"
    )

    return {
        "extracted_params": extracted,
        "patient_info": patient_info,
        "report_type": result.report_type,
    }
