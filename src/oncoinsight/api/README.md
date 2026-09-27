# `api/`: OncoInsight REST API (FastAPI)

[← package overview](../README.md)

Run it locally, then open the interactive docs at `http://localhost:8011/docs` (Docker stack: `:8010/docs`):

```bash
uv run uvicorn oncoinsight.api.main:app --port 8011
```

| Area | Endpoints |
|---|---|
| Ops | `GET /health`, `/pipeline/runs`, `/data-quality` |
| KPIs | `GET /kpis/summary`, `/kpis/annual`, `/alerts` |
| Care journey | `GET /pathways`, `/pathways/transitions`, `/delays/hospitals`, `/delays/risk-adjusted`, `/delays/drivers`, `/patients/{barcode}` |
| Outcomes | `GET /survival/km`, `/survival/cox`, `/recurrence/summary`, `/recurrence/models`, **`POST /survival/compare`** (live two-cohort KM + RMST + log-rank), `POST /predict/recurrence-risk` |
| Value & equity | `GET /costs`, `/disparities` |
| Semantic layer & AI | `GET /metrics`, `POST /metrics/query`, `POST /assistant/ask` |

## Production touches

- Every query runs on the **read-only** `onco_reader` role.
- Optional authentication: set `ONCO_API_KEY` and send `X-API-Key` (`/health` and docs stay open for load balancers).
- Each response carries an `x-request-id`, and a structured access log records method, path, status and latency.
- Small groups (n < 11) are suppressed. The recurrence scorer is labelled as a demonstration, not for clinical use.
