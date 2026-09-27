"""AI oncology analytics assistant.

Question -> Claude (tool use) -> governed metric (semantic layer) or validated read-only SQL -> warehouse
-> results -> natural-language explanation grounded in the returned rows.

The model never receives database credentials and can only call two tools:
* ``query_metric`` - compiles a governed metric from semantic_layer.yml (preferred).
* ``run_sql``      - ad-hoc SELECT, validated by sql_guard and executed on the read-only role.
Every executed query is returned alongside the answer for auditability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic
import yaml
from pydantic import ValidationError

from oncoinsight.assistant.semantic import MetricRequest, SemanticError, load_layer, run_metric
from oncoinsight.assistant.sql_guard import UnsafeSQLError, validate_sql
from oncoinsight.common.config import Settings, get_settings
from oncoinsight.common.db import connect
from oncoinsight.common.logging import get_logger

log = get_logger(__name__)

MAX_TOOL_ROUNDS = 8
ROWS_TO_MODEL = 200

SYSTEM_PROMPT = """You are OncoInsight's analytics assistant for an oncology network's analysts. You answer questions \
about breast cancer care pathways, time to treatment, outcomes, recurrence, cost and equity using ONLY data you retrieve \
with your tools from the OncoInsight warehouse.

Data context:
- Primary cohort: TCGA-BRCA (NCI Genomic Data Commons), 1,098 patients from 40 contributing sites (TCGA tissue source \
sites; some are biorepositories rather than treating hospitals - hospital comparisons should use is_benchmarkable = true).
- Survival endpoints are the TCGA PanCancer Clinical Data Resource OS/DSS/PFI. Validation cohort: METABRIC (n=2,509).
- Time intervals are days from the index diagnosis (which in TCGA is usually the surgical specimen date).
- Diagnosis year is the finest time grain available (no month). Costs are ESTIMATES using CMS 2026 reference prices.
- This is observational research data: describe associations, never claim a treatment is better or causal, and never \
give medical advice about an individual.

How to work:
1. Prefer query_metric with governed metrics. Use run_sql only when no governed metric fits (e.g. reading analytics.* \
statistical results or ops.kpi_alerts). SQL must use schema-qualified tables from the allow-list.
2. For "why" questions (e.g. why did delays increase), look at the KPI alert, then decompose the change by hospital, stage, \
subtype and volume across years, and check analytics.delay_drivers / analytics.hospital_risk_adjusted_delay.
3. Values marked suppressed (n<11) must not be reported as numbers.
4. In the final answer: lead with the direct answer, cite the specific numbers and group sizes you retrieved, state \
caveats (small n, crude vs adjusted, data limitations) briefly, and keep it under ~250 words. Use a compact markdown \
table when comparing groups.

Semantic layer (governed metrics, dimensions and SQL-accessible tables):
"""

TOOLS = [
    {
        "name": "query_metric",
        "description": ("Compute a governed metric from the semantic layer, optionally grouped by up to 3 dimensions "
                        "and filtered. Returns rows with the dimension values, 'value' and 'n' (group size). "
                        "Filter values must match the stored category labels exactly (e.g. stage_major 'III', "
                        "receptor_subtype 'Triple negative', pathway_modality 'Chemotherapy')."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Metric name from the semantic layer"},
                "dimensions": {"type": "array", "items": {"type": "string"}, "description": "Group-by dimensions"},
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {"type": "string"},
                            "operator": {"type": "string", "enum": ["=", "!=", ">", ">=", "<", "<=", "in", "not in"]},
                            "value": {"type": "string", "description": "Scalar value, or a JSON array string for in / not in"},
                        },
                        "required": ["dimension", "operator", "value"],
                        "additionalProperties": False,
                    },
                },
                "limit": {"type": "integer", "description": "Max rows (<= 500)"},
            },
            "required": ["metric", "dimensions", "filters", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_sql",
        "description": ("Run one read-only PostgreSQL SELECT against allow-listed curated tables (marts.*, analytics.*, "
                        "ops.kpi_alerts). Use schema-qualified names. Results are capped at 500 rows."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A single SELECT statement"},
                "purpose": {"type": "string", "description": "One sentence: what this query answers"},
            },
            "required": ["sql", "purpose"],
            "additionalProperties": False,
        },
    },
]


@dataclass
class ExecutedQuery:
    tool: str
    sql: str
    params: dict = field(default_factory=dict)
    rows: list[dict] = field(default_factory=list)
    error: str | None = None
    purpose: str | None = None


@dataclass
class AssistantAnswer:
    question: str
    answer: str
    queries: list[ExecutedQuery]
    model: str
    stop_reason: str | None
    usage: dict = field(default_factory=dict)


def _coerce_filter_value(v: str):
    s = v.strip()
    if s.startswith("["):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def _jsonable(rows: list[dict]) -> list[dict]:
    return json.loads(json.dumps(rows, default=str))


def execute_tool(name: str, args: dict, settings: Settings) -> tuple[str, ExecutedQuery, bool]:
    """Run a tool call. Returns (tool_result_content, audit_record, is_error)."""
    if name == "query_metric":
        try:
            req = MetricRequest(
                metric=args["metric"], dimensions=args.get("dimensions", []), limit=args.get("limit", 100),
                filters=[{**f, "value": _coerce_filter_value(str(f["value"]))} for f in args.get("filters", [])])
            q, rows = run_metric(req, settings)
            rec = ExecutedQuery("query_metric", q.sql, q.params, _jsonable(rows))
            return json.dumps({"metric_description": q.description, "row_count": len(rows),
                               "rows": rec.rows[:ROWS_TO_MODEL]}), rec, False
        except (SemanticError, ValidationError, KeyError) as exc:
            return f"Error: {exc}", ExecutedQuery("query_metric", json.dumps(args), error=str(exc)), True
    if name == "run_sql":
        raw = args.get("sql", "")
        try:
            safe = validate_sql(raw, settings.assistant_max_rows)
            with connect(settings, readonly=True) as conn:
                cur = conn.execute(safe)
                cols = [c.name for c in cur.description]
                rows = _jsonable([dict(zip(cols, r, strict=True)) for r in cur.fetchall()])
            rec = ExecutedQuery("run_sql", safe, rows=rows, purpose=args.get("purpose"))
            return json.dumps({"row_count": len(rows), "rows": rows[:ROWS_TO_MODEL]}), rec, False
        except UnsafeSQLError as exc:
            return f"Rejected by SQL guard: {exc}", ExecutedQuery("run_sql", raw, error=str(exc)), True
        except Exception as exc:  # database error: return it so the model can correct its query
            msg = str(exc).splitlines()[0]
            return f"Database error: {msg}", ExecutedQuery("run_sql", raw, error=msg), True
    return f"Error: unknown tool {name}", ExecutedQuery(name, "", error="unknown tool"), True


def _system_blocks() -> list[dict]:
    layer = yaml.safe_dump(load_layer(), sort_keys=True, allow_unicode=True)  # deterministic -> cacheable prefix
    return [{"type": "text", "text": SYSTEM_PROMPT + layer, "cache_control": {"type": "ephemeral"}}]


def ask(question: str, history: list[dict] | None = None, settings: Settings | None = None,
        client: anthropic.Anthropic | None = None) -> AssistantAnswer:
    s = settings or get_settings()
    if client is None:
        if s.anthropic_api_key is None or not s.anthropic_api_key.get_secret_value():
            raise RuntimeError("ANTHROPIC_API_KEY is not configured; the AI assistant is disabled. "
                               "Governed metrics remain available through the metric explorer and /metrics API.")
        client = anthropic.Anthropic(api_key=s.anthropic_api_key.get_secret_value())

    messages: list = [*(history or []), {"role": "user", "content": question}]
    queries: list[ExecutedQuery] = []
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    response = None
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=s.assistant_model,
            max_tokens=16000,
            system=_system_blocks(),
            tools=TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            # server-side refusal fallback: a declined request is re-run on Anthropic's recommended model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        for k in usage:
            usage[k] += getattr(response.usage, k, 0) or 0
        if response.stop_reason == "refusal":
            break
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            content, rec, is_error = execute_tool(block.name, block.input, s)
            queries.append(rec)
            log.info("assistant_tool_call", tool=block.name, error=rec.error, rows=len(rec.rows))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})  # all results in one message

    if response is None:
        raise RuntimeError("no response from model")
    if response.stop_reason == "refusal":
        answer = "The request was declined by the model's safety system. Try rephrasing it as an aggregate analytics question."
    else:
        answer = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "tool_use":
            answer = (answer + "\n\n" if answer else "") + "_Stopped after the maximum number of analysis steps._"
    return AssistantAnswer(question, answer, queries, response.model, response.stop_reason, usage)
