import logging

logger = logging.getLogger(__name__)

# Clinical severity thresholds — percent deviation from reference midpoint
# Format: (mild_pct, moderate_pct, severe_pct)
_SEVERITY_THRESHOLDS = {
    "default":                  (10, 25, 50),
    # Haematology — small absolute changes are clinically significant
    "Hemoglobin":               (10, 20, 35),
    "Platelets":                (15, 35, 60),
    "Platelet Count":           (15, 35, 60),
    "Total WBC count":          (20, 40, 70),
    "Neutrophils":              (15, 30, 50),
    # Electrolytes — even 5-10 % deviation from midpoint is clinically significant
    "Potassium":                (5,  10, 20),
    "Sodium":                   (2,   5, 10),
    "Calcium":                  (5,  12, 25),
    # Coagulation
    "INR":                      (10, 25, 50),
    "Prothrombin Time":         (10, 20, 40),
    # Renal
    "Creatinine":               (20, 50, 100),
    # Glucose / HbA1c
    "Fasting Blood Glucose":    (10, 30, 60),
    "Random Blood Glucose":     (10, 30, 60),
    "Postprandial Blood Glucose": (10, 30, 60),
    "HbA1c":                    (10, 20, 40),
}

# Values that are immediately critical regardless of severity classification
_CRITICAL_LOW_PARAMS = {
    "Hemoglobin":               7.0,    # g/dL — transfusion threshold
    "Platelet Count":           50000,  # /cumm — spontaneous bleeding risk
    "Total WBC count":          2000,   # /cumm — severe leukopenia / infection risk
    "Potassium":                2.5,    # mEq/L — life-threatening cardiac arrhythmia
    "Sodium":                   120.0,  # mEq/L — severe hyponatremia (seizure/coma risk)
    "Fasting Blood Glucose":    50.0,   # mg/dL — severe hypoglycemia
    "Random Blood Glucose":     50.0,
    "Postprandial Blood Glucose": 50.0,
}

_CRITICAL_HIGH_PARAMS = {
    "Total WBC count":          30000,  # /cumm — leukemoid reaction / possible leukemia
    "Platelet Count":           1000000, # /cumm — extreme thrombocytosis
    "Potassium":                6.5,    # mEq/L — life-threatening hyperkalemia
    "Sodium":                   160.0,  # mEq/L — severe hypernatremia
    "INR":                      3.0,    # — severe coagulopathy / over-anticoagulation
    "Total Bilirubin":          15.0,   # mg/dL — severe jaundice / hepatic failure
    "Creatinine":               10.0,   # mg/dL — severe uremia
    "Fasting Blood Glucose":    500.0,  # mg/dL — hyperglycemic crisis
    "Random Blood Glucose":     500.0,
    "Postprandial Blood Glucose": 500.0,
    "HbA1c":                    10.0,   # % — very poor glycaemic control
    "Amylase":                  1000.0, # U/L — severe acute pancreatitis
    "Lipase":                   1000.0, # U/L — severe acute pancreatitis
}


def _compute_severity(param: str, value: float, low: float, high: float, status: str) -> str:
    """
    Returns: 'normal' | 'mild' | 'moderate' | 'severe' | 'critical'
    Based on percent deviation from the reference midpoint.
    """
    if status == "normal":
        return "normal"

    midpoint = (low + high) / 2
    if midpoint == 0:
        return "mild"

    deviation_pct = abs(value - midpoint) / midpoint * 100
    thresholds = _SEVERITY_THRESHOLDS.get(param, _SEVERITY_THRESHOLDS["default"])
    mild_t, mod_t, severe_t = thresholds

    if deviation_pct < mild_t:
        return "mild"
    elif deviation_pct < mod_t:
        return "moderate"
    elif deviation_pct < severe_t:
        return "severe"
    else:
        return "severe"


def _check_critical(param: str, value: float, status: str) -> bool:
    """True if this value crosses an immediately critical threshold."""
    if status == "low" and param in _CRITICAL_LOW_PARAMS:
        return value <= _CRITICAL_LOW_PARAMS[param]
    if status == "high" and param in _CRITICAL_HIGH_PARAMS:
        return value >= _CRITICAL_HIGH_PARAMS[param]
    return False


def model1_interpretation_node(state):
    """
    Node: Clinical interpretation of validated parameters.

    Adds beyond what validate_standardize provides:
    - Severity level: normal / mild / moderate / severe
    - Critical alert flag for dangerous values
    - Percent deviation from reference midpoint
    - Clinical priority (routine / watch / urgent / critical)
    """
    validated = state.validated_params or {}
    interpreted = {}

    for name, info in validated.items():
        v = info.get("value")
        ref = info.get("reference", {})
        low = ref.get("low")
        high = ref.get("high")
        flag = info.get("flag", "UNKNOWN")  # LOW / HIGH / NORMAL from validate node

        status = flag.lower() if flag in ("LOW", "HIGH", "NORMAL") else "unknown"

        # Severity classification
        severity = "unknown"
        deviation_pct = None
        is_critical = False

        if v is not None and low is not None and high is not None:
            severity = _compute_severity(name, v, low, high, status)
            midpoint = (low + high) / 2
            if midpoint != 0:
                deviation_pct = round((v - midpoint) / midpoint * 100, 1)
            is_critical = _check_critical(name, v, status)
            # Escalate severity to critical if threshold crossed
            if is_critical:
                severity = "critical"

        # Clinical priority mapping
        priority = {
            "normal":   "routine",
            "mild":     "watch",
            "moderate": "urgent",
            "severe":   "urgent",
            "critical": "critical",
            "unknown":  "routine",
        }.get(severity, "routine")

        interpreted[name] = {
            "value": v,
            "unit": info.get("unit"),
            "reference": ref,
            "status": status,           # low / high / normal / unknown
            "severity": severity,       # normal / mild / moderate / severe / critical
            "deviation_pct": deviation_pct,  # % from midpoint, +ve = high, -ve = low
            "is_critical": is_critical,
            "priority": priority,       # routine / watch / urgent / critical
        }

        if is_critical:
            logger.warning(
                f"CRITICAL value detected: {name}={v} {info.get('unit','')} "
                f"(ref {low}-{high})"
            )

    return {"param_interpretation": interpreted}
