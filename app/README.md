# `app/`: interactive Streamlit dashboard (13 pages)

[← back to project README](../README.md)

Run it locally at http://localhost:8503 (the Docker stack serves it on `:8502`):

```bash
make dashboard
```

| File | Role |
|---|---|
| `Home.py` | Entry point and router: `st.navigation` with grouped sections (Start here · Care journey · Outcomes & value · Operations & platform) |
| `theme.py` | Design system and shared UI: validated colour palette (colour follows the entity; ordinal ramps for stage/age; reserved status colours), gradient page headers, KPI cards, notes, step cards, the **persistent cohort filter row**, read-only data access with caching, and small-cell guards |
| `charts.py` | Figure factories shared by every page **and** by `scripts/make_readme_assets.py`: cohort-filterable Sankey, sunburst, treemap, world map, Kaplan-Meier with CI bands, cohort comparison, forest plots, violins, scorecard heatmap, animated site timeline, cost stack, dbt lineage graph |
| [`pages/`](pages/) | One file per page (see below) |

## Interaction model

- **One filter row** (diagnosis year, stage, subtype, age group, site type) sits above the content and scopes every
  chart on every page. It persists as you navigate.
- **Click-to-drill:** treemap tiles (Pathways) and site markers (Time to treatment) open patient lists.
- **Live computation:** the Cohort Lab fits Kaplan-Meier/RMST/log-rank on demand, the cost simulator re-prices
  every line, and the delay slider recomputes every rate.
- **Accessibility:** tooltips on every mark, direct labels, legends for multi-series charts, and a CSV download on
  every table. Groups under 11 patients are suppressed.
