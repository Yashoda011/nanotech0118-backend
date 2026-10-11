"""Scientific compute — server-side port of frontend src/lib/science.ts.
Uses numpy/scipy for real numerics (deterministic seeded demo model).
DISCLAIMER: illustrative demo model, not validated for lab decisions."""

import numpy as np

DEMO_DISCLAIMER = "Illustrative demo model — results are generated for interface demonstration and are not scientifically validated."


def scherrer_diameter(fwhm_deg: float, theta_deg: float, lambda_nm: float, k: float = 0.9) -> float:
    if fwhm_deg <= 0 or theta_deg <= 0 or lambda_nm <= 0:
        return 0.0
    beta = np.deg2rad(fwhm_deg)
    theta = np.deg2rad(theta_deg)
    return float((k * lambda_nm) / (beta * np.cos(theta)))


def dilution_volume(c1: float, v1: float, c2: float) -> float:
    if c1 <= 0 or c2 <= 0:
        return 0.0
    return float((c2 * v1) / c1)


def ev_to_wavelength(ev: float) -> float:
    return float(1239.841984 / ev) if ev > 0 else 0.0


def wavelength_to_ev(nm: float) -> float:
    return float(1239.841984 / nm) if nm > 0 else 0.0


def run_simulation(material_id: str, electrical_index: float, model: str,
                   temperature_k: float, size_nm: float, iterations: int) -> dict:
    seed = (sum(ord(c) for c in material_id) + round(temperature_k)
            + round(size_nm) + iterations + len(model) * 17) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    points = 24
    thermal_factor = 1 + (temperature_k - 300) / 1400
    size_factor = 1 + np.log10(max(size_nm, 1) + 1) / 3
    xs = np.linspace(0, 100, points)
    if model == "electron":
        base = electrical_index * thermal_factor * np.exp(-xs / 160)
    elif model == "thermal":
        base = electrical_index * 0.72 * size_factor * (1 - np.exp(-xs / 55))
    else:
        base = electrical_index * 0.9 * np.tanh(xs / 42)
    noise = (rng.random(points) - 0.5) * electrical_index * 0.08
    demo = np.maximum(0, base + noise)
    ctrl_factor = 0.62 if model == "electron" else 0.8
    control = np.maximum(0, base * ctrl_factor + (rng.random(points) - 0.5) * 2)
    series = [{"x": round(float(x)), "demo": round(float(d), 2), "control": round(float(c), 2)}
              for x, d, c in zip(xs, demo, control)]
    peak = round(float(np.max(demo)), 2)
    mean = round(float(np.mean(demo)), 2)
    unit = {"electron": "S/cm (index)", "thermal": "W/m·K (index)"}.get(model, "GPa (index)")
    return {"model": model, "materialId": material_id, "temperatureK": temperature_k,
            "sizeNm": size_nm, "iterations": iterations, "peak": peak, "mean": mean,
            "series": series, "unit": unit, "disclaimer": DEMO_DISCLAIMER}


def dataset_stats(series: list[dict]) -> dict:
    """pandas-style describe per series using numpy (no pandas import cost at runtime)."""
    import pandas as pd
    out: dict = {}
    for s in series:
        vals = pd.Series([p["value"] for p in s.get("points", [])], dtype=float)
        if len(vals) == 0:
            continue
        desc = vals.describe()
        out[s.get("name", "series")] = {k: round(float(v), 4) for k, v in desc.to_dict().items()}
    return out
