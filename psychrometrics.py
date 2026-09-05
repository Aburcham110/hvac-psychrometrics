#!/usr/bin/env python3
"""Educational I-P psychrometric approximations (stdlib only).

Not a substitute for a calibrated psychrometer or OEM psych apps.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import List, Optional

DISCLAIMER = (
    "EDUCATIONAL ONLY — approximate I-P formulas. "
    "Not a substitute for a calibrated psychrometer, sling, or OEM psychrometric apps."
)

# Magnus-type saturation vapor pressure over water (hPa), T in °C
def es_hpa(t_c: float) -> float:
    return 6.112 * math.exp((17.62 * t_c) / (243.12 + t_c))


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


@dataclass
class State:
    db_f: float
    rh: Optional[float]
    wb_f: Optional[float]
    dew_f: float
    rh_pct: float
    w_lb_lb: float  # humidity ratio
    h_btu_lb: float  # enthalpy approx
    notes: List[str]


def rh_from_db_wb(db_f: float, wb_f: float, p_psia: float = 14.696) -> float:
    """Approx RH from DB/WB using vapor pressures (educational)."""
    db_c, wb_c = f_to_c(db_f), f_to_c(wb_f)
    if wb_f > db_f + 0.05:
        raise ValueError("wet-bulb cannot exceed dry-bulb")
    es_db = es_hpa(db_c)
    es_wb = es_hpa(wb_c)
    # Simple psychrometric: e ≈ es_wb - P*(db-wb)*0.00066*(1+0.00115*wb_c)  (hPa, P in hPa)
    p_hpa = p_psia * 68.94757
    e = es_wb - p_hpa * (db_c - wb_c) * 0.00066 * (1.0 + 0.00115 * wb_c)
    e = max(0.01, e)
    return max(0.0, min(100.0, 100.0 * e / es_db))


def dew_from_rh(db_f: float, rh_pct: float) -> float:
    db_c = f_to_c(db_f)
    e = es_hpa(db_c) * (rh_pct / 100.0)
    # Invert Magnus
    ln = math.log(e / 6.112)
    td_c = (243.12 * ln) / (17.62 - ln)
    return c_to_f(td_c)


def humidity_ratio(db_f: float, rh_pct: float, p_psia: float = 14.696) -> float:
    db_c = f_to_c(db_f)
    e_hpa = es_hpa(db_c) * (rh_pct / 100.0)
    e_psia = e_hpa / 68.94757
    # W = 0.622 * e / (P - e)
    return 0.622 * e_psia / max(1e-6, (p_psia - e_psia))


def enthalpy_ip(db_f: float, w: float) -> float:
    # h ≈ 0.24*T + W*(1061 + 0.444*T)  BTU/lb dry air
    return 0.24 * db_f + w * (1061.0 + 0.444 * db_f)


def analyze(
    *,
    db_f: float,
    rh: Optional[float] = None,
    wb_f: Optional[float] = None,
    target_sh_f: Optional[float] = None,
    p_psia: float = 14.696,
) -> State:
    notes: List[str] = []
    if rh is None and wb_f is None:
        raise ValueError("provide --rh or --wb")
    if rh is not None and wb_f is not None:
        notes.append("Both RH and WB given — using RH; WB ignored for state")
        rh_pct = float(rh)
    elif rh is not None:
        rh_pct = float(rh)
    else:
        rh_pct = rh_from_db_wb(db_f, float(wb_f), p_psia)
        notes.append("RH derived approximately from DB/WB")

    if not 0 <= rh_pct <= 100:
        raise ValueError("RH must be 0–100%")

    dew = dew_from_rh(db_f, rh_pct)
    w = humidity_ratio(db_f, rh_pct, p_psia)
    h = enthalpy_ip(db_f, w)
    if target_sh_f is not None:
        notes.append(
            f"Air-side context: evaporator SH target ~{target_sh_f:.0f} °F is refrigerant-side; "
            "compare coil TD / leaving air separately — this tool is moist-air only"
        )
    notes.append("Sea-level P default 14.696 psia unless --psia overridden")
    return State(
        db_f=db_f,
        rh=rh,
        wb_f=wb_f,
        dew_f=dew,
        rh_pct=rh_pct,
        w_lb_lb=w,
        h_btu_lb=h,
        notes=notes,
    )


def format_report(s: State) -> str:
    lines = [
        DISCLAIMER,
        "",
        f"Dry-bulb: {s.db_f:.1f} °F",
    ]
    if s.wb_f is not None:
        lines.append(f"Wet-bulb (input): {s.wb_f:.1f} °F")
    lines += [
        f"RH: {s.rh_pct:.1f} %",
        f"Dew point (approx): {s.dew_f:.1f} °F",
        f"Humidity ratio W (approx): {s.w_lb_lb:.5f} lb/lb da",
        f"Enthalpy h (approx): {s.h_btu_lb:.1f} BTU/lb da",
        "",
        "Notes:",
    ]
    for n in s.notes:
        lines.append(f"  • {n}")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Educational I-P psychrometric approximations.",
        epilog=DISCLAIMER,
    )
    p.add_argument("-i", "--interactive", action="store_true")
    p.add_argument("--db", type=float, help="Dry-bulb °F")
    p.add_argument("--rh", type=float, help="Relative humidity %")
    p.add_argument("--wb", type=float, help="Wet-bulb °F")
    p.add_argument("--target-sh", type=float, default=None, help="Optional refrigerant SH context °F")
    p.add_argument("--psia", type=float, default=14.696, help="Barometric pressure psia")
    return p


def pf(prompt: str, default: Optional[float] = None) -> float:
    while True:
        suf = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suf}: ").strip()
        if not raw and default is not None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            print("Enter a number.")


def main(argv: Optional[List[str]] = None) -> int:
    ns = build_parser().parse_args(argv)
    try:
        if ns.interactive:
            print(DISCLAIMER)
            print()
            db = pf("Dry-bulb °F")
            mode = input("Use RH% or wet-bulb? [rh/wb] [rh]: ").strip().lower() or "rh"
            rh = wb = None
            if mode.startswith("w"):
                wb = pf("Wet-bulb °F")
            else:
                rh = pf("RH %")
            tsh = input("Optional target SH °F (blank skip): ").strip()
            target_sh = float(tsh) if tsh else None
            st = analyze(db_f=db, rh=rh, wb_f=wb, target_sh_f=target_sh, p_psia=ns.psia)
        else:
            if ns.db is None:
                raise SystemExit("Need --db and (--rh or --wb), or -i")
            st = analyze(
                db_f=ns.db,
                rh=ns.rh,
                wb_f=ns.wb,
                target_sh_f=ns.target_sh,
                p_psia=ns.psia,
            )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(format_report(st))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
