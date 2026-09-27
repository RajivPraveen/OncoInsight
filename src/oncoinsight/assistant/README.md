# `assistant/`: governed semantic layer and LLM analytics assistant

[← package overview](../README.md)

Lets an analyst ask questions in plain English **without** giving a language model free access to the database.

| File | What it does |
|---|---|
| `semantic_layer.yml` | **24 governed metrics** (e.g. `median_days_to_chemotherapy`, `pct_chemo_over_90d`, `standard_cycle_completion_pct`, `mean_estimated_cost_usd`) over curated marts, each with declared dimensions and a description, plus the allow-list of tables ad-hoc SQL may touch |
| `semantic.py` | Compiles a metric request into **parameterised** SQL (values are never interpolated), runs it on the read-only role and suppresses groups with n < 11 |
| `sql_guard.py` | Parses ad-hoc SQL with `sqlglot` and rejects anything that isn't a single `SELECT` over allow-listed curated tables: DML, raw/staging tables, dangerous functions (`pg_sleep`, `dblink`, …) and multi-statement input. Enforces a `LIMIT` |
| `agent.py` | Tool-use loop on the Anthropic Claude API with two strict-schema tools, `query_metric` (preferred) and `run_sql` (guarded). Uses a cached semantic-layer system prompt, adaptive thinking and a server-side refusal fallback. Returns the answer **plus every query it executed** for audit |

## Defence in depth

1. Governed metrics first.
2. Static SQL validation.
3. Execution as `onco_reader`: read-only transactions, 30 s timeout, no access to raw or staging schemas.
4. Small-cell suppression.

Set `ANTHROPIC_API_KEY` in `.env` to enable the chat. The governed metric explorer works without it.
