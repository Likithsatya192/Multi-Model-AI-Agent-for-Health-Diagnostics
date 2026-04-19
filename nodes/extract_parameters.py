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

import base64
import logging
import mimetypes
import os
import re
import json
from typing import List, Optional, Union
from langchain_core.messages import SystemMessage, HumanMessage
from utils.llm_utils import get_fast_llm, get_llm, get_vision_llm, MEDICAL_SYSTEM_PROMPT

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
    # Indian lab dot-abbreviations for RBC (T.R.B.C / TRB.C on printed reports)
    "trbc": "Total RBC count", "t.r.b.c": "Total RBC count", "trb.c": "Total RBC count",
    "t r b c": "Total RBC count", "t.r.b.c.": "Total RBC count",

    # PCV / HCT
    "pcv": "Packed Cell Volume", "hct": "Packed Cell Volume",
    "hematocrit": "Packed Cell Volume", "haematocrit": "Packed Cell Volume",
    "packed cell volume": "Packed Cell Volume", "packed cell vol": "Packed Cell Volume",
    "packed cell volume (pcv)": "Packed Cell Volume",
    # OCR corruptions of PCV (P→p, C→e/c, V→Y common Tesseract errors)
    "pey": "Packed Cell Volume", "pcv%": "Packed Cell Volume", "p.c.v": "Packed Cell Volume",
    "pev": "Packed Cell Volume", "p c v": "Packed Cell Volume",

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
    # Indian lab dot-abbreviations (e.g. T.W.B.C on printed reports)
    "t.w.b.c": "Total WBC count", "t w b c": "Total WBC count", "t.w.b.c.": "Total WBC count",

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
    "free psa": "Free PSA", "fpsa": "Free PSA", "free prostate specific antigen": "Free PSA",

    # ══════════════════ HAEMATOLOGY EXTENDED ══════════════════

    "reticulocyte count": "Reticulocyte Count", "retic count": "Reticulocyte Count",
    "reticulocytes": "Reticulocyte Count", "absolute reticulocytes": "Reticulocyte Count",
    "reticulocyte percentage": "Reticulocyte Percentage", "retic %": "Reticulocyte Percentage",
    "reticulocyte %": "Reticulocyte Percentage", "reticulocytes %": "Reticulocyte Percentage",

    "g6pd": "G6PD", "g6pd activity": "G6PD",
    "glucose-6-phosphate dehydrogenase": "G6PD", "glucose 6 phosphate dehydrogenase": "G6PD",
    "g-6-p-d": "G6PD",

    # ══════════════════ CARDIAC MARKERS ══════════════════

    "troponin i": "Troponin I", "ctni": "Troponin I", "cardiac troponin i": "Troponin I",
    "troponin": "Troponin I", "cardiac troponin": "Troponin I",
    "troponin t": "Troponin T", "ctnt": "Troponin T", "cardiac troponin t": "Troponin T",
    "high sensitivity troponin i": "High-sensitivity Troponin I",
    "high-sensitivity troponin i": "High-sensitivity Troponin I",
    "hs troponin i": "High-sensitivity Troponin I", "hstni": "High-sensitivity Troponin I",
    "hs-tni": "High-sensitivity Troponin I",

    "bnp": "BNP", "brain natriuretic peptide": "BNP", "b-type natriuretic peptide": "BNP",
    "nt-probnp": "NT-proBNP", "nt probnp": "NT-proBNP",
    "n-terminal pro-bnp": "NT-proBNP", "n terminal pro bnp": "NT-proBNP",

    "ck": "CK", "creatine kinase": "CK", "cpk": "CK", "creatine phosphokinase": "CK",
    "serum ck": "CK", "serum cpk": "CK",
    "ck-mb": "CK-MB", "ck mb": "CK-MB", "creatine kinase mb": "CK-MB",
    "ck-mb fraction": "CK-MB", "ckmb": "CK-MB",

    "myoglobin": "Myoglobin", "serum myoglobin": "Myoglobin",

    "homocysteine": "Homocysteine", "total homocysteine": "Homocysteine",
    "plasma homocysteine": "Homocysteine", "hcy": "Homocysteine",

    # ══════════════════ LIPID EXTENDED ══════════════════

    "apolipoprotein a1": "Apolipoprotein A1", "apo a-1": "Apolipoprotein A1",
    "apo a1": "Apolipoprotein A1", "apoa1": "Apolipoprotein A1",
    "apolipoprotein b": "Apolipoprotein B", "apo b": "Apolipoprotein B",
    "apob": "Apolipoprotein B", "apo b-100": "Apolipoprotein B",
    "lipoprotein(a)": "Lipoprotein(a)", "lp(a)": "Lipoprotein(a)",
    "lpa": "Lipoprotein(a)", "lipoprotein a": "Lipoprotein(a)",

    # ══════════════════ THYROID EXTENDED ══════════════════

    "anti-tpo": "Anti-TPO", "anti tpo": "Anti-TPO",
    "thyroid peroxidase antibody": "Anti-TPO", "tpo ab": "Anti-TPO",
    "anti-thyroid peroxidase": "Anti-TPO", "tpo antibody": "Anti-TPO",
    "tpoab": "Anti-TPO",

    "anti-tg": "Anti-Tg", "anti tg": "Anti-Tg",
    "thyroglobulin antibody": "Anti-Tg", "tg ab": "Anti-Tg",
    "anti-thyroglobulin": "Anti-Tg", "tgab": "Anti-Tg",

    "thyroglobulin": "Thyroglobulin", "tg": "Thyroglobulin", "serum thyroglobulin": "Thyroglobulin",

    "anti-trab": "Anti-TRAb", "trab": "Anti-TRAb",
    "tsh receptor antibody": "Anti-TRAb", "anti-tsh receptor": "Anti-TRAb",
    "thyroid stimulating antibody": "Anti-TRAb", "tsh receptor ab": "Anti-TRAb",

    # ══════════════════ REPRODUCTIVE / SEX HORMONES ══════════════════

    "fsh": "FSH", "follicle stimulating hormone": "FSH",
    "follicle-stimulating hormone": "FSH", "serum fsh": "FSH",

    "lh": "LH", "luteinizing hormone": "LH", "luteinising hormone": "LH",
    "serum lh": "LH",

    "prolactin": "Prolactin", "prl": "Prolactin", "serum prolactin": "Prolactin",

    "estradiol": "Estradiol", "e2": "Estradiol", "oestradiol": "Estradiol",
    "17-beta estradiol": "Estradiol", "17beta estradiol": "Estradiol",
    "serum estradiol": "Estradiol",

    "progesterone": "Progesterone", "serum progesterone": "Progesterone",
    "plasma progesterone": "Progesterone",

    "testosterone": "Total Testosterone", "total testosterone": "Total Testosterone",
    "serum testosterone": "Total Testosterone", "s. testosterone": "Total Testosterone",

    "free testosterone": "Free Testosterone", "free t": "Free Testosterone",
    "free testosterone (direct)": "Free Testosterone",

    "dhea-s": "DHEA-S", "dheas": "DHEA-S",
    "dehydroepiandrosterone sulfate": "DHEA-S", "dhea sulfate": "DHEA-S",
    "dehydroepiandrosterone sulphate": "DHEA-S",

    "shbg": "SHBG", "sex hormone binding globulin": "SHBG",
    "sex-hormone binding globulin": "SHBG",

    "amh": "AMH", "anti-mullerian hormone": "AMH", "anti-müllerian hormone": "AMH",
    "mullerian inhibiting substance": "AMH", "mis": "AMH",

    "beta-hcg": "Beta-hCG", "hcg": "Beta-hCG", "b-hcg": "Beta-hCG",
    "bhcg": "Beta-hCG", "human chorionic gonadotropin": "Beta-hCG",
    "human chorionic gonadotrophin": "Beta-hCG", "pregnancy hormone": "Beta-hCG",
    "beta hcg": "Beta-hCG",

    # ══════════════════ ADRENAL HORMONES ══════════════════

    "cortisol": "Cortisol", "serum cortisol": "Cortisol",
    "morning cortisol": "Cortisol", "8am cortisol": "Cortisol",
    "plasma cortisol": "Cortisol",

    "acth": "ACTH", "adrenocorticotropic hormone": "ACTH",
    "adrenocorticotropin": "ACTH", "corticotropin": "ACTH",
    "plasma acth": "ACTH",

    "aldosterone": "Aldosterone", "serum aldosterone": "Aldosterone",
    "plasma aldosterone": "Aldosterone",

    "renin": "Renin", "plasma renin activity": "Renin",
    "pra": "Renin", "renin activity": "Renin",

    # ══════════════════ PARATHYROID / GROWTH ══════════════════

    "pth": "PTH", "parathyroid hormone": "PTH", "parathormone": "PTH",
    "intact pth": "PTH", "ipth": "PTH", "serum pth": "PTH",

    "igf-1": "IGF-1", "igf1": "IGF-1",
    "insulin-like growth factor 1": "IGF-1", "somatomedin c": "IGF-1",
    "insulin like growth factor 1": "IGF-1",

    "growth hormone": "Growth Hormone", "gh": "Growth Hormone",
    "somatotropin": "Growth Hormone", "hgh": "Growth Hormone",
    "human growth hormone": "Growth Hormone",

    # ══════════════════ DIABETES EXTENDED ══════════════════

    "insulin": "Insulin", "fasting insulin": "Insulin", "serum insulin": "Insulin",
    "plasma insulin": "Insulin",

    "c-peptide": "C-Peptide", "c peptide": "C-Peptide",
    "connecting peptide": "C-Peptide", "serum c-peptide": "C-Peptide",

    "fructosamine": "Fructosamine", "glycated protein": "Fructosamine",
    "serum fructosamine": "Fructosamine",

    "homa-ir": "HOMA-IR", "homa ir": "HOMA-IR",
    "homeostatic model assessment": "HOMA-IR",

    # ══════════════════ TUMOUR MARKERS ══════════════════

    "cea": "CEA", "carcinoembryonic antigen": "CEA", "s. cea": "CEA",

    "ca-125": "CA-125", "ca 125": "CA-125", "cancer antigen 125": "CA-125",
    "ovarian cancer antigen": "CA-125",

    "ca 19-9": "CA 19-9", "ca19-9": "CA 19-9", "ca-19-9": "CA 19-9",
    "cancer antigen 19-9": "CA 19-9", "carbohydrate antigen 19-9": "CA 19-9",

    "ca 15-3": "CA 15-3", "ca15-3": "CA 15-3", "ca-15-3": "CA 15-3",
    "cancer antigen 15-3": "CA 15-3",

    "ca 72-4": "CA 72-4", "ca72-4": "CA 72-4", "tag-72": "CA 72-4",

    "afp": "AFP", "alpha-fetoprotein": "AFP", "alpha fetoprotein": "AFP",
    "serum afp": "AFP",

    "nse": "NSE", "neuron-specific enolase": "NSE", "neuron specific enolase": "NSE",

    "cyfra 21-1": "CYFRA 21-1", "cyfra21-1": "CYFRA 21-1",
    "cytokeratin-19 fragment": "CYFRA 21-1", "cytokeratin 19 fragment": "CYFRA 21-1",

    "beta-2 microglobulin": "Beta-2 Microglobulin", "b2m": "Beta-2 Microglobulin",
    "beta2 microglobulin": "Beta-2 Microglobulin", "b2 microglobulin": "Beta-2 Microglobulin",

    # ══════════════════ AUTOIMMUNE / RHEUMATOLOGY ══════════════════

    "rheumatoid factor": "Rheumatoid Factor", "rf": "Rheumatoid Factor",
    "ra factor": "Rheumatoid Factor", "rheumatoid factor (rf)": "Rheumatoid Factor",

    "anti-ccp": "Anti-CCP", "anti ccp": "Anti-CCP",
    "anti-cyclic citrullinated peptide": "Anti-CCP",
    "cyclic citrullinated peptide antibody": "Anti-CCP", "acpa": "Anti-CCP",

    "ana": "ANA", "antinuclear antibody": "ANA", "anti-nuclear antibody": "ANA",
    "ana screen": "ANA", "antinuclear ab": "ANA",

    "anti-dsdna": "Anti-dsDNA", "anti ds-dna": "Anti-dsDNA",
    "anti double stranded dna": "Anti-dsDNA", "anti dsdna": "Anti-dsDNA",
    "ds dna antibody": "Anti-dsDNA", "double stranded dna antibody": "Anti-dsDNA",

    "c3 complement": "C3 Complement", "c3": "C3 Complement",
    "complement c3": "C3 Complement", "complement component 3": "C3 Complement",

    "c4 complement": "C4 Complement", "c4": "C4 Complement",
    "complement c4": "C4 Complement", "complement component 4": "C4 Complement",

    "aso": "Anti-Streptolysin O", "asot": "Anti-Streptolysin O",
    "anti-streptolysin o": "Anti-Streptolysin O",
    "anti streptolysin o": "Anti-Streptolysin O", "aso titre": "Anti-Streptolysin O",
    "streptolysin o antibody": "Anti-Streptolysin O", "aso titer": "Anti-Streptolysin O",

    # ══════════════════ IMMUNOGLOBULINS ══════════════════

    "igg": "IgG", "immunoglobulin g": "IgG", "serum igg": "IgG",
    "iga": "IgA", "immunoglobulin a": "IgA", "serum iga": "IgA",
    "igm": "IgM", "immunoglobulin m": "IgM", "serum igm": "IgM",
    "ige": "IgE", "total ige": "IgE", "immunoglobulin e": "IgE",
    "serum ige": "IgE",

    # ══════════════════ NUTRITIONAL / VITAMINS ══════════════════

    "vitamin a": "Vitamin A", "retinol": "Vitamin A", "serum vitamin a": "Vitamin A",
    "vitamin e": "Vitamin E", "alpha-tocopherol": "Vitamin E", "tocopherol": "Vitamin E",
    "vitamin c": "Vitamin C", "ascorbic acid": "Vitamin C", "l-ascorbic acid": "Vitamin C",
    "zinc": "Zinc", "serum zinc": "Zinc", "plasma zinc": "Zinc",
    "copper": "Copper", "serum copper": "Copper", "plasma copper": "Copper",
    "selenium": "Selenium", "serum selenium": "Selenium",
    "ceruloplasmin": "Ceruloplasmin", "serum ceruloplasmin": "Ceruloplasmin",
    "prealbumin": "Prealbumin", "transthyretin": "Prealbumin", "pab": "Prealbumin",
    "pre-albumin": "Prealbumin",

    # ══════════════════ RENAL / URINE ══════════════════

    "cystatin c": "Cystatin C", "cystatin-c": "Cystatin C", "serum cystatin c": "Cystatin C",
    "transferrin": "Transferrin", "serum transferrin": "Transferrin",
    "urine protein": "Urine Protein", "urine total protein": "Urine Protein",
    "protein urine": "Urine Protein", "u/r protein": "Urine Protein",
    "24h urine protein": "24h Urine Protein", "24 hour urine protein": "24h Urine Protein",
    "urine protein 24h": "24h Urine Protein",
    "microalbumin": "Microalbumin", "urine microalbumin": "Microalbumin",
    "urine albumin": "Microalbumin", "spot urine albumin": "Microalbumin",
    "acr": "ACR", "albumin creatinine ratio": "ACR",
    "albumin:creatinine ratio": "ACR", "uacr": "ACR",
    "urine creatinine": "Urine Creatinine", "creatinine urine": "Urine Creatinine",
    "urine specific gravity": "Urine Specific Gravity", "usg": "Urine Specific Gravity",
    "urine sg": "Urine Specific Gravity", "specific gravity": "Urine Specific Gravity",
    "urine ph": "Urine pH", "urine reaction": "Urine pH", "u/r ph": "Urine pH",

    # ══════════════════ METABOLIC / MISC ══════════════════

    "lactic acid": "Lactic Acid", "lactate": "Lactic Acid",
    "blood lactate": "Lactic Acid", "serum lactate": "Lactic Acid",
    "ammonia": "Ammonia", "blood ammonia": "Ammonia",
    "nh3": "Ammonia", "plasma ammonia": "Ammonia",

    "homocysteine": "Homocysteine", "total homocysteine": "Homocysteine",
    "plasma homocysteine": "Homocysteine", "hcy": "Homocysteine",

    "fructosamine": "Fructosamine", "glycated protein": "Fructosamine",

    # ══════════════════ BONE METABOLISM ══════════════════

    "osteocalcin": "Osteocalcin", "bone gla protein": "Osteocalcin", "bgp": "Osteocalcin",
    "bone alp": "Bone ALP", "bone alkaline phosphatase": "Bone ALP",
    "bone-specific alkaline phosphatase": "Bone ALP", "balp": "Bone ALP",
    "c-telopeptide": "C-Telopeptide", "ctx": "C-Telopeptide",
    "c-terminal telopeptide": "C-Telopeptide", "serum ctx": "C-Telopeptide",
    "beta-crosslaps": "C-Telopeptide",

    # ══════════════════ INFECTIOUS / SEROLOGY ══════════════════

    "dengue ns1 antigen": "Dengue NS1 Antigen", "ns1 antigen": "Dengue NS1 Antigen",
    "dengue ns1": "Dengue NS1 Antigen", "ns1 ag": "Dengue NS1 Antigen",
    "widal test": "Widal Test", "widal": "Widal Test",
    "typhidot": "Widal Test", "salmonella antibody": "Widal Test",
    "hbsag": "HBsAg", "hepatitis b surface antigen": "HBsAg",
    "hepatitis b ag": "HBsAg", "hbs antigen": "HBsAg",
    "anti-hcv": "Anti-HCV", "hepatitis c antibody": "Anti-HCV",
    "hcv antibody": "Anti-HCV", "anti hcv": "Anti-HCV",
    "anti-hbs": "Anti-HBs", "hepatitis b surface antibody": "Anti-HBs",
    "hbs antibody": "Anti-HBs",
    "hiv antibody": "HIV Antibody", "hiv 1/2 antibody": "HIV Antibody",
    "anti-hiv": "HIV Antibody", "hiv screen": "HIV Antibody",
}


# ─────────────────────────────────────────────────────────────────────────────
# Differential count: % name → Absolute name, keyed by unit
# Many reports print both a % section (DLC) and an absolute section.
# Both rows share the same raw_name (e.g. "Lymphocytes"), but units differ.
# Without this map the absolute count silently overwrites the % reading.
# ─────────────────────────────────────────────────────────────────────────────
_DIFF_PCT_TO_ABS: dict[str, str] = {
    "Neutrophils":  "Absolute Neutrophils",
    "Lymphocytes":  "Absolute Lymphocytes",
    "Monocytes":    "Absolute Monocytes",
    "Eosinophils":  "Absolute Eosinophils",
    "Basophils":    "Absolute Basophils",
}
_PCT_UNIT_TOKENS = {"%", "percent", "pct", "per cent"}

# Pydantic removed — we parse JSON directly for robustness and token efficiency


# ─────────────────────────────────────────────────────────────────────────────
# Canonical name resolution
# ─────────────────────────────────────────────────────────────────────────────

def _canonicalize(raw_name: str) -> tuple[str, bool]:
    """
    Map raw lab parameter name to canonical name.
    Returns (name, matched) — `matched=False` means no alias hit (caller decides
    whether to keep or drop based on auxiliary evidence like ref range / unit).
    """
    key = raw_name.strip().lower()

    # 1. Exact match
    if key in PARAM_ALIASES:
        return PARAM_ALIASES[key], True

    # 2. Remove common noise tokens and retry
    noise = ["serum", "blood", "plasma", "s.", "b.", "(total)", "(direct)", "(indirect)",
             "(free)", "level", "count", "test", "assay", ",", ".", "-"]
    cleaned = key
    for n in noise:
        cleaned = cleaned.replace(n, " ")
    cleaned = " ".join(cleaned.split())
    if cleaned in PARAM_ALIASES:
        return PARAM_ALIASES[cleaned], True

    # 2b. Try condensed (no spaces) — catches "t w b c" → "twbc"
    condensed = cleaned.replace(" ", "")
    if condensed in PARAM_ALIASES:
        return PARAM_ALIASES[condensed], True

    # 3. Partial / contains match — require alias length >= 4 to avoid OCR
    #    gibberish like "Poa" accidentally matching 2-3 char aliases.
    best = None
    best_len = 0
    for alias, canonical in PARAM_ALIASES.items():
        if len(alias) < 4:
            continue
        if alias in key and len(alias) > best_len:
            best, best_len = canonical, len(alias)
    if best:
        return best, True

    # 4. No match — return stripped original; caller decides.
    return raw_name.strip(), False


# ─────────────────────────────────────────────────────────────────────────────
# Hallucination / OCR-garbage defences
# ─────────────────────────────────────────────────────────────────────────────

# Small whitelist of medically-meaningful stems for unknown-param validation.
# If canonicalize misses and no stem matches, the entry is treated as garbage.
_MEDICAL_STEMS = (
    "hemo", "haemo", "cyte", "cytic", "phil", "blast", "globul", "protein",
    "bilirub", "transamin", "phosphat", "creat", "urea", "glucose", "chol",
    "trigly", "iron", "ferrit", "calc", "magn", "sodium", "potass", "chlor",
    "bicarb", "albumin", "thyro", "thyrox", "triiodo", "hormon", "antigen",
    "antibod", "vitam", "folate", "reactiv", "platelet", "thromb", "coagul",
    "lymph", "neutro", "mono", "eosino", "baso", "erythro", "leuko", "leuco",
    "hematocr", "corpuscul",
)


def _value_in_text(value: float, text: str) -> bool:
    """
    Check whether `value` appears literally in the raw report text.
    Tolerates commas (Indian/US thousands) and common decimal precisions.
    Used to drop hallucinated values the LLM invented but aren't in the report.
    """
    if value is None:
        return False
    # Strip commas and non-breaking spaces so "3,41,000" and "341000" both match.
    normalized = re.sub(r"[,\u00a0]", "", text)
    candidates = set()
    if value == int(value):
        ival = int(value)
        candidates.add(str(ival))
        candidates.add(f"{ival}.0")
    else:
        # Non-integer: don't round to an integer — "0.9" should not match a stray
        # "1" in the text (precision-0 rounding produced false positives).
        for prec in (1, 2, 3, 4):
            s = f"{value:.{prec}f}"
            candidates.add(s)
            stripped = s.rstrip("0").rstrip(".")
            if stripped and "." in stripped:
                candidates.add(stripped)
    for c in candidates:
        if not c:
            continue
        pattern = r"(?<!\d)" + re.escape(c) + r"(?!\d)"
        if re.search(pattern, normalized):
            return True
    return False


def _looks_like_ocr_garbage(name: str) -> bool:
    """
    Heuristic gibberish detection for unrecognized parameter names.
    Catches OCR artifacts like 'Wa ney Lem Yodan Are' / 'Copirapams' / 'Poa'.
    """
    if not name:
        return True
    stripped = name.strip()
    if len(stripped) < 3:
        return True
    # If none of the known medical stems appear, treat as garbage.
    lower = stripped.lower()
    if any(stem in lower for stem in _MEDICAL_STEMS):
        return False
    # Multi-word names without a medical stem are very likely OCR noise
    # (real params have stable vocabulary). Allow single-token abbreviations
    # since those are already mostly in the alias dict and didn't match.
    tokens = stripped.split()
    if len(tokens) >= 2:
        return True
    # Single token, no stem, short and lowercase-mixed: garbage.
    if len(stripped) < 5 and not stripped.isupper():
        return True
    return False


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

_EXTRACTION_PROMPT = """Extract laboratory test values LITERALLY PRESENT in this blood/lab report. Output JSON only, no other text.

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

=== ABSOLUTE ANTI-HALLUCINATION RULES (violating ANY of these = wrong answer) ===
A. ONLY extract parameters whose NAME and NUMERIC VALUE are both LITERALLY printed in the REPORT text below.
B. NEVER invent, impute, fill-in, complete, or "correct" values. If a parameter is missing, OMIT IT. Do NOT add it.
C. NEVER copy a typical reference value (e.g. Creatinine 0.9, Sodium 140) from memory — if the number is not in the text, the parameter does not exist.
D. NEVER "fix" a patient value you think looks wrong. Copy the digits exactly as printed (e.g. if report shows 10.0, output 10.0 — not 11.2).
E. If OCR mangled a parameter name into gibberish, SKIP IT. Do not guess what it was.
F. patient_age: copy exactly as printed, including units like "8 Month(s)" or "45 Years". Do NOT convert.
G. patient_gender: copy exactly ("Male", "Female") — do NOT infer from name.

CORE EXTRACTION RULES:
1. value = the patient's RESULT only — the first standalone number immediately after the parameter name.
2. ref_low / ref_high = reference range AS PRINTED in the report. Null if not printed.
   Ranges appear as: "12.0-17.5" | "12.0 \u2013 17.5" | "(12.0-17.5)" | "12.0 to 17.5" | "Ref: 12-17"
   For pediatric reports showing multiple ranges (e.g. Male / Female / Child), pick the one that matches the patient's age/gender as printed in the header.
3. flag = abnormal marker AS PRINTED: H / L / HH / LL / HIGH / LOW / A / * / \u2191 / \u2193 / CRITICAL
   Null if not printed. Do NOT infer the flag.
4. Extract EVERY parameter visible — do not silently drop TLC, RBC, PCV, MCV, MCH, MCHC, differential counts, CRP, etc., even if the panel has many rows.

UNIT & SCALE RULES:
5. OCR digit corrections INSIDE a visible number: O\u21920, l\u21921, I\u21921 (e.g. "l2.5"\u219212.5). Only apply when a garbled digit is obvious — do NOT synthesize a number from nothing.
6. Indian lakh/comma notation: "3,41,000" \u2192 341000; "10,000" \u2192 10000.
7. WBC/Platelets as printed: "11,000 cells/cu.mm" \u2192 value=11000; "3,41,000 cells/cu.mm" \u2192 value=341000.

OCR LAYOUT RULES:
8. Each parameter line typically reads: [Name] [Patient Value] [Unit] [Reference Range] [Flag]
   Example: "Haemoglobin 10.0 gms/dl 13.0 to 18.0 gms/dl"  \u2192 value=10.0 (NOT 13.0 or 18.0).
9. Patient value appears BEFORE any range notation. In a range "a-b" or "a to b", ref_low=a, ref_high=b.
10. If only ONE number appears after the name, it is the patient value (ref_low/high = null).
11. Ignore: page headers/footers, lab name, doctor name, address, barcodes.
12. Differential counts (Neutrophils, Lymphocytes, etc.) printed as % — extract as the percentage, not an absolute count.

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


# ─────────────────────────────────────────────────────────────────────────────
# System message for the extraction task.
#
# Uses the shared MEDICAL_SYSTEM_PROMPT as the base persona (clinical diagnostic
# specialist) and then appends task-specific rules that OVERRIDE any tendency
# to produce natural-language explanations. Without this override the 70B model
# would frequently respond with prose ("The hemoglobin level is low, which
# suggests …") instead of the raw JSON this node needs, leaving
# extracted_params empty and breaking every downstream node.
# ─────────────────────────────────────────────────────────────────────────────
_EXTRACTION_SYSTEM = (
    "You are a deterministic OCR-to-JSON extractor for laboratory reports. "
    "You are NOT a doctor, NOT a clinician, NOT a reasoner. You do not diagnose, "
    "interpret, or explain findings. Your ONLY job is to copy numbers and names "
    "that are LITERALLY printed in the input text into a JSON structure.\n\n"
    "HARD CONSTRAINTS:\n"
    "- Output RAW JSON only. Response must start with '{' and end with '}'.\n"
    "- No markdown code fences. No commentary. No prose.\n"
    "- NEVER invent, impute, or fill-in values from medical knowledge. If a "
    "  parameter is not printed in the text, DO NOT include it in lab_values.\n"
    "- NEVER substitute a 'typical' value for a missing or illegible one.\n"
    "- NEVER 'correct' a patient value you think looks implausible — copy digits exactly.\n"
    "- If a parameter name is OCR garbage (gibberish), skip it entirely.\n"
    "- If a field within a kept row cannot be determined, set that field to null; "
    "  do not drop the whole row and do not fabricate its value.\n"
    "- Follow the exact JSON schema and rules in the user message."
)


# ─────────────────────────────────────────────────────────────────────────────
# Vision extraction — bypass Tesseract by sending image bytes directly to a
# multimodal LLM. Tesseract struggles with phone photos of printed lab forms
# (shadows, angles, blur), producing garbage like "aClrtrya LABORATORY...".
# The vision path feeds original pixels to the model, which reads the report
# the way a human would.
# ─────────────────────────────────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
_MAX_VISION_PAGES = 4  # cap PDFs to avoid huge multimodal payloads


def _file_to_image_data_urls(path: str) -> List[str]:
    """
    Convert an image file or PDF into a list of base64 data-URLs (one per page).
    Returns [] on failure.
    """
    if not path or not os.path.exists(path):
        return []
    ext = os.path.splitext(path)[1].lower()
    urls: List[str] = []
    try:
        if ext == ".pdf":
            # Render each PDF page to a JPEG via the existing OCR helper.
            from utils.ocr_utils import _pdf_page_to_image
            import fitz
            doc = fitz.open(path)
            num_pages = min(len(doc), _MAX_VISION_PAGES)
            doc.close()
            from io import BytesIO
            for pnum in range(num_pages):
                img = _pdf_page_to_image(path, page_num=pnum, dpi=200)
                buf = BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=85)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                urls.append(f"data:image/jpeg;base64,{b64}")
        elif ext in _IMAGE_EXTS:
            mime, _ = mimetypes.guess_type(path)
            if not mime or not mime.startswith("image/"):
                mime = "image/jpeg"
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            urls.append(f"data:{mime};base64,{b64}")
    except Exception as e:
        logger.warning(f"extract_parameters: failed to prepare image data URLs: {e}")
    return urls


_VISION_PROMPT = """You are looking at a scanned or photographed blood/lab test report. Read the printed values directly from the image and output JSON only.

Output this EXACT JSON structure (no markdown, no prose):
{{
  "report_type": "CBC|LFT|KFT|LIPID|THYROID|COAGULATION|IRON|DIABETES|COMPREHENSIVE|MIXED|UNKNOWN",
  "patient_name": null,
  "patient_age": null,
  "patient_gender": null,
  "lab_values": [
    {{"raw_name": "Hemoglobin", "value": 10.0, "unit": "g/dL", "ref_low": 13.0, "ref_high": 18.0, "flag": null}}
  ]
}}

ABSOLUTE RULES (violating any = wrong answer):
A. Only include parameters whose name AND numeric value you can READ on the image. If you cannot read a value, OMIT the whole row. Do NOT guess.
B. NEVER copy a typical reference value from medical knowledge. Every number you output must come from the image pixels.
C. NEVER "correct" a patient value. Copy digits exactly as printed (e.g. 10.0 stays 10.0).
D. patient_age: copy verbatim including units, e.g. "8 Month(s)", "45 Years". DO NOT convert.
E. patient_gender: "Male" or "Female" as printed. Do NOT infer.
F. For pediatric reports that print multiple reference ranges (Male / Female / Child), pick the range matching the patient's header age/gender for ref_low/ref_high.
G. Extract EVERY parameter row visible: Hemoglobin, Total Leucocyte Count, differential counts (Polymorphs/Neutrophils, Lymphocytes, Monocytes, Eosinophils, Basophils), Total RBC Count, Packed Cell Volume, Platelet Count, MCV, MCH, MCHC, CRP — any other test rows present. Do not stop early.

NUMBER RULES:
- Indian lakh notation "3,41,000" → value: 341000 (integer).
- "11,000 cells/cu.mm" → value: 11000.
- Preserve decimals exactly: "70.1" → 70.1; "22.1" → 22.1.
- flag: copy the letter/symbol printed at end of the row (H/L/HH/LL/HIGH/LOW/A/*/↑/↓). null if no flag printed.
- ref_low/ref_high: copy from the reference column on the same row. null if absent.

Return ONLY the JSON object, starting with '{{' and ending with '}}'.
"""


def _call_vision_json(image_urls: List[str]) -> dict:
    """
    Send image(s) directly to the vision LLM and parse JSON response.
    Uses the stricter anti-hallucination extraction system prompt.
    """
    if not image_urls:
        raise RuntimeError("No image data URLs provided for vision extraction")

    content_blocks = [{"type": "text", "text": _VISION_PROMPT}]
    for url in image_urls:
        content_blocks.append({"type": "image_url", "image_url": {"url": url}})

    messages = [
        SystemMessage(content=_EXTRACTION_SYSTEM),
        HumanMessage(content=content_blocks),
    ]

    llm = get_vision_llm(max_tokens=2048)
    resp = llm.invoke(messages)
    content = resp.content if hasattr(resp, "content") else str(resp)
    return _parse_llm_json(content or "")


def _call_llm_json(prompt: str, primary_llm, fallback_llm) -> dict:
    """
    Call LLM and parse JSON response. Tries primary then fallback.
    Returns parsed dict or raises on total failure.

    Uses the task-tuned extraction system prompt (medical persona + strict
    JSON-only rules) so the 70B model reliably returns the structured
    schema instead of narrative text.
    """
    messages = [
        SystemMessage(content=_EXTRACTION_SYSTEM),
        HumanMessage(content=prompt),
    ]
    last_content: str = ""
    for i, llm in enumerate([primary_llm, fallback_llm]):
        label = "fast" if i == 0 else "quality"
        try:
            resp = llm.invoke(messages)
            content = resp.content if hasattr(resp, "content") else str(resp)
            last_content = content or ""
            return _parse_llm_json(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"extract_parameters: {label} model JSON parse failed: {e}. "
                f"Response preview: {last_content[:400]!r}"
            )
        except Exception as e:
            logger.exception(f"extract_parameters: {label} model call failed: {type(e).__name__}: {e}")
    raise RuntimeError("All LLM models failed for extraction")


# ─────────────────────────────────────────────────────────────────────────────
# Main node
# ─────────────────────────────────────────────────────────────────────────────

def _ocr_looks_garbage(text: str) -> bool:
    """
    Heuristic for when Tesseract OCR clearly failed (phone photos, shadows, blur).
    Signal: very few recognizable medical tokens despite nonzero length.
    """
    if not text:
        return True
    lower = text.lower()
    hits = sum(1 for k in (
        "hemoglobin", "haemoglobin", "platelet", "leucocyte", "leukocyte",
        "rbc", "wbc", "lymphocyte", "neutrophil", "monocyte", "eosinophil",
        "creatinine", "cholesterol", "glucose", "bilirubin", "protein",
    ) if k in lower)
    return hits < 2


def extract_parameters_node(state):
    """
    Universal extraction node.
    Strategy:
      1. If source file is an image or scanned PDF → send image bytes directly
         to a multimodal vision LLM. Bypasses Tesseract, which is unreliable on
         phone photos of lab reports.
      2. Otherwise (or on vision failure) → fall back to text-based extraction
         against the OCR/native-extracted raw_text.
    Both paths share the same anti-hallucination post-filters.
    """
    text = state.raw_text or ""
    file_path = getattr(state, "raw_file_path", None) or ""
    logger.info(
        f"extract_parameters: raw_text length={len(text)} chars, "
        f"file='{file_path}', first 200: {text[:200]!r}"
    )

    ext = os.path.splitext(file_path)[1].lower() if file_path else ""
    has_image_source = ext in _IMAGE_EXTS or ext == ".pdf"
    prefer_vision = has_image_source and (
        not text.strip() or _ocr_looks_garbage(text)
    )

    data = None
    used_vision = False

    # ── Path 1: vision-first for image/photo reports ──────────────────────────
    if prefer_vision:
        logger.info("extract_parameters: trying vision LLM path (OCR unreliable or empty)")
        try:
            image_urls = _file_to_image_data_urls(file_path)
            if image_urls:
                data = _call_vision_json(image_urls)
                used_vision = True
                logger.info(
                    f"extract_parameters: vision LLM returned {len(data.get('lab_values', []))} values"
                )
        except Exception as e:
            logger.warning(f"extract_parameters: vision path failed, falling back to text: {e}")
            data = None

    # ── Path 2: text-based extraction (fallback or non-image source) ──────────
    if data is None:
        if not text.strip():
            return {
                "extracted_params": {},
                "errors": state.errors + ["No text to extract from and vision extraction failed."],
            }
        prompt = _EXTRACTION_PROMPT.format(text=text)
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
    dropped_hallucinated = 0
    dropped_garbage = 0

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

        # Anti-hallucination: for the text path, values must appear literally
        # in raw_text. For the vision path, the model read the image directly
        # so raw_text (OCR) is not ground truth — skip this check but rely on
        # the prompt's strict rules + the OCR-garbage gate below.
        if not used_vision and not _value_in_text(raw_val, text):
            dropped_hallucinated += 1
            logger.warning(
                f"extract_parameters: DROPPED hallucinated '{raw_name}'={raw_val} "
                f"(value not present in raw text)"
            )
            continue

        canonical, matched = _canonicalize(raw_name)

        ref_low = _parse_float(lv.get("ref_low"))
        ref_high = _parse_float(lv.get("ref_high"))
        unit_raw = lv.get("unit")

        # Unit-aware reclassification for differential counts.
        # If canonical is a % differential (e.g. "Lymphocytes") but the
        # extracted unit is an absolute count unit (thou/mm3, cumm, /uL …),
        # remap to the absolute canonical so both rows are preserved separately.
        if canonical in _DIFF_PCT_TO_ABS and unit_raw:
            unit_lower = unit_raw.strip().lower()
            is_pct = any(tok in unit_lower for tok in _PCT_UNIT_TOKENS)
            if not is_pct:
                canonical = _DIFF_PCT_TO_ABS[canonical]
                matched = True

        # OCR-garbage gate: an unrecognized parameter name is only trusted when
        # it has BOTH a unit AND a reference range from the report (strong signal
        # it came from a real structured row) AND doesn't look like OCR noise.
        # Everything else is dropped — most "new" names turn out to be garbage.
        if not matched:
            has_support = bool(unit_raw) and ref_low is not None and ref_high is not None
            if not has_support or _looks_like_ocr_garbage(canonical):
                dropped_garbage += 1
                logger.warning(
                    f"extract_parameters: DROPPED unrecognized param '{raw_name}' "
                    f"(has_unit_ref={has_support}, looks_garbage={_looks_like_ocr_garbage(canonical)})"
                )
                continue

        # Dedup: keep entry with more metadata
        if canonical in extracted:
            existing = extracted[canonical]
            has_meta = ref_low is not None or lv.get("flag")
            existing_meta = existing.get("report_ref_low") is not None or existing.get("report_flag")
            if not has_meta and existing_meta:
                continue

        unit = unit_raw or DEFAULT_UNITS.get(canonical)
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

    if dropped_hallucinated or dropped_garbage:
        logger.info(
            f"extract_parameters: dropped {dropped_hallucinated} hallucinated, "
            f"{dropped_garbage} OCR-garbage params"
        )

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
