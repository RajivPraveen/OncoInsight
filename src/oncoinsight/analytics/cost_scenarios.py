"""What-if re-pricing of reference-priced cost lines (used by the dashboard Cost page).

Scenarios act on individual cost lines, not averages, so results aggregate correctly to any grouping.
The baseline is recomputed from units x unit price with the same formula as the scenario, so an unchanged
scenario yields a delta of exactly zero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

RT_DELIVERY, RT_MANAGEMENT, TRASTUZUMAB = "cpt_77412_pfs_nf", "cpt_77427_pfs_nf", "j9355_asp"


@dataclass(frozen=True)
class Scenario:
    hypofractionation: bool = False
    fractions: int = 16                 # per radiation course when hypofractionation is on
    trastuzumab_discount_pct: float = 0  # biosimilar uptake
    other_drug_change_pct: float = 0
    fee_schedule_change_pct: float = 0   # Physician Fee Schedule (all CPT lines)


def reprice(lines: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    """lines needs price_id, cost_component, units, unit_price_usd. Adds baseline and scenario columns."""
    s = lines.copy()
    s["baseline"] = s.units * s.unit_price_usd
    units = s.units.astype(float).copy()
    if sc.hypofractionation:
        rd, rm = s.price_id == RT_DELIVERY, s.price_id == RT_MANAGEMENT
        units[rd] = np.minimum(s.loc[rd, "units"], sc.fractions)
        units[rm] = np.minimum(s.loc[rm, "units"], np.ceil(sc.fractions / 5))
    price = s.unit_price_usd.astype(float).copy()
    tras = s.price_id == TRASTUZUMAB
    price[tras] *= 1 - sc.trastuzumab_discount_pct / 100
    other = (s.cost_component == "drug") & ~tras
    price[other] *= 1 + sc.other_drug_change_pct / 100
    price[s.price_id.str.startswith("cpt_")] *= 1 + sc.fee_schedule_change_pct / 100
    s["scenario"] = units * price
    return s
