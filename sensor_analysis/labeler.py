"""
Rule-based labeler for water quality (clean/dirty) using strict WHO-inspired thresholds.

Strict policy (default) for domestic tap water used for drinking:
- pH clean if 6.5 <= pH <= 8.5
- Turbidity clean if NTU <= 1.0 (ideal for disinfection; 1–5 flagged borderline)
- TDS clean if <= 500 mg/L (desirable limit; 500–1000 borderline)

If only two labels are required, borderline cases are considered "dirty" under strict policy.
Missing metrics are treated as violations (dirty) in strict mode.

Returns a dict with:
- label: "clean" | "dirty"
- is_clean: bool
- reasons: list[str] explaining violations or stating compliant
- confidence: float in [0, 1] indicating margin distance to thresholds (for clean), or 0 if dirty
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TypedDict, Union, Iterable


@dataclass
class LabelConfig:
    # Thresholds for strict policy
    ph_min: float = 6.5
    ph_max: float = 8.5
    ntu_clean_max: float = 1.0     # strict clean threshold
    ntu_borderline_max: float = 5.0
    tds_clean_max: float = 500.0    # strict clean threshold
    tds_borderline_max: float = 1000.0
    # Policy flags
    strict: bool = True             # if True, treat borderline as dirty
    require_all_metrics: bool = True  # if True, missing metrics => dirty


def _clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def compute_margins(ph: Optional[float], tds: Optional[float], ntu: Optional[float], cfg: LabelConfig) -> Dict[str, float]:
    """Compute normalized margins to the clean thresholds for informational confidence.
    For clean cases, confidence = min of these margins.
    Margins in [0,1], where 1.0 is far inside the clean region, 0 at the threshold/beyond.
    """
    # pH margin: ideal center is anywhere inside [ph_min, ph_max]. Use distance to nearest bound, scaled by 1.0 pH unit.
    if ph is None:
        m_ph = 0.0
    elif cfg.ph_min <= ph <= cfg.ph_max:
        m_ph = _clamp(min(ph - cfg.ph_min, cfg.ph_max - ph) / 1.0, 0.0, 1.0)
    else:
        m_ph = 0.0

    # TDS margin: ideal <= tds_clean_max; scale with 500 mg/L span
    if tds is None:
        m_tds = 0.0
    elif tds <= cfg.tds_clean_max:
        m_tds = _clamp((cfg.tds_clean_max - tds) / max(cfg.tds_clean_max, 1.0), 0.0, 1.0)
    else:
        m_tds = 0.0

    # NTU margin: ideal <= ntu_clean_max; scale with 1.0 NTU span
    if ntu is None:
        m_ntu = 0.0
    elif ntu <= cfg.ntu_clean_max:
        m_ntu = _clamp((cfg.ntu_clean_max - ntu) / max(cfg.ntu_clean_max, 1.0), 0.0, 1.0)
    else:
        m_ntu = 0.0

    return {"ph": m_ph, "tds": m_tds, "ntu": m_ntu}


class LabelResult(TypedDict):
    label: str
    is_clean: bool
    reasons: List[str]
    confidence: float
    margins: Dict[str, float]


def compute_label(
    ph: Optional[float],
    tds_mgL: Optional[float],
    turbidity_ntu: Optional[float],
    config: Optional[LabelConfig] = None,
) -> LabelResult:
    cfg = config or LabelConfig()

    reasons: List[str] = []
    missing: List[str] = []

    # Validate presence
    if ph is None:
        missing.append("ph")
    if tds_mgL is None:
        missing.append("tds")
    if turbidity_ntu is None:
        missing.append("ntu")

    if cfg.require_all_metrics and missing:
        reasons.append(f"Missing metrics: {', '.join(missing)}")

    # Check ranges
    if ph is not None and not (cfg.ph_min <= ph <= cfg.ph_max):
        which = "<" if ph < cfg.ph_min else ">"
        bound = cfg.ph_min if ph < cfg.ph_min else cfg.ph_max
        reasons.append(f"pH out of range: {ph} ({which} {bound})")

    if turbidity_ntu is not None:
        if turbidity_ntu > cfg.ntu_clean_max:
            # Flag borderline if within WHO 5 NTU but above strict 1 NTU
            if turbidity_ntu <= cfg.ntu_borderline_max:
                reasons.append(f"Turbidity borderline: {turbidity_ntu} NTU (> {cfg.ntu_clean_max})")
            else:
                reasons.append(f"Turbidity high: {turbidity_ntu} NTU (> {cfg.ntu_borderline_max})")

    if tds_mgL is not None:
        if tds_mgL > cfg.tds_clean_max:
            if tds_mgL <= cfg.tds_borderline_max:
                reasons.append(f"TDS borderline: {tds_mgL} mg/L (> {cfg.tds_clean_max})")
            else:
                reasons.append(f"TDS high: {tds_mgL} mg/L (> {cfg.tds_borderline_max})")

    # Determine label
    any_violation = any(
        s.startswith("Missing") or
        s.startswith("pH out") or
        s.startswith("Turbidity") or
        s.startswith("TDS")
        for s in reasons
    )

    # Under strict policy, borderline counts as violation/dirty.
    is_clean = not any_violation
    label = "clean" if is_clean else "dirty"

    # Confidence for clean cases
    margins = compute_margins(ph, tds_mgL, turbidity_ntu, cfg)
    confidence = min(margins.values()) if is_clean else 0.0

    if is_clean:
        reasons = [
            f"Compliant: pH={ph}, TDS={tds_mgL} mg/L, NTU={turbidity_ntu}"
        ]

    return {
        "label": label,
        "is_clean": is_clean,
        "reasons": reasons,
        "confidence": round(confidence, 3),
        "margins": {k: round(v, 3) for k, v in margins.items()},
    }


def _resolve_columns(df_columns: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Try to resolve column names for pH, TDS, and Turbidity.
    Supports common variants found in datasets.
    """
    cols_lower = {c.lower(): c for c in df_columns}

    ph_col = None
    for key in ["ph", "pH"]:
        if key.lower() in cols_lower:
            ph_col = cols_lower[key.lower()]
            break

    # TDS: often named Solids in water_potability.csv (mg/L)
    tds_candidates = ["tds", "TDS", "solids", "Solids"]
    tds_col = None
    for key in tds_candidates:
        if key.lower() in cols_lower:
            tds_col = cols_lower[key.lower()]
            break

    ntu_candidates = ["ntu", "turbidity", "Turbidity"]
    ntu_col = None
    for key in ntu_candidates:
        if key.lower() in cols_lower:
            ntu_col = cols_lower[key.lower()]
            break

    return ph_col, tds_col, ntu_col


def label_dataframe(df, config: Optional[LabelConfig] = None):
    """Return a copy of df with added columns: label, is_clean, reasons, confidence.
    Expects columns for pH, TDS (or Solids), and Turbidity (NTU).
    """
    import pandas as pd

    cfg = config or LabelConfig()
    df = df.copy()

    ph_col, tds_col, ntu_col = _resolve_columns(list(df.columns))
    if ph_col is None or tds_col is None or ntu_col is None:
        missing = [name for name, col in [("pH", ph_col), ("TDS/Solids", tds_col), ("Turbidity", ntu_col)] if col is None]
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    labels: List[str] = []
    cleans: List[bool] = []
    reasons_list: List[str] = []
    confidences: List[float] = []

    for _, row in df.iterrows():
        ph = row.get(ph_col)
        tds = row.get(tds_col)
        ntu = row.get(ntu_col)

        # Coerce to floats if possible
        try:
            ph = float(ph) if ph == ph else ph  # keep None/NaN as-is
        except Exception:
            ph = None
        try:
            tds = float(tds) if tds == tds else tds
        except Exception:
            tds = None
        try:
            ntu = float(ntu) if ntu == ntu else ntu
        except Exception:
            ntu = None

        res = compute_label(ph, tds, ntu, cfg)
        labels.append(str(res.get("label", "dirty")))
        cleans.append(bool(res.get("is_clean", False)))
        # Join reasons defensively
        rlist = res.get("reasons", [])
        if not isinstance(rlist, list):
            rlist = [str(rlist)]
        reasons_list.append("; ".join([str(x) for x in rlist]))
        conf = res.get("confidence", 0.0)
        try:
            confidences.append(float(conf))
        except (TypeError, ValueError):
            confidences.append(0.0)

    df["label"] = labels
    df["is_clean"] = cleans
    df["reasons"] = reasons_list
    df["confidence"] = confidences

    return df
