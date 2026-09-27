from types import SimpleNamespace

import pytest

from oncoinsight.assistant import agent
from oncoinsight.assistant.semantic import MetricRequest, SemanticError, compile_metric
from oncoinsight.assistant.sql_guard import UnsafeSQLError, validate_sql
from oncoinsight.common.config import Settings

# ---------------------------------------------------------------- semantic layer


def test_metric_compiles_to_parameterised_sql():
    q = compile_metric(MetricRequest(metric="pct_chemo_over_90d", dimensions=["hospital_name"],
                                     filters=[{"dimension": "stage_major", "operator": "=", "value": "III"}]))
    assert "from marts.mart_patient_360" in q.sql
    assert '"stage_major" = %(f0)s' in q.sql and q.params == {"f0": "III"}
    assert 'group by "hospital_name"' in q.sql


def test_filter_values_are_never_interpolated():
    q = compile_metric(MetricRequest(metric="patients", filters=[
        {"dimension": "race", "operator": "=", "value": "x'; drop table marts.mart_patient_360; --"}]))
    assert "drop table" not in q.sql


def test_undeclared_dimension_rejected():
    with pytest.raises(SemanticError, match="not available"):
        compile_metric(MetricRequest(metric="patients", dimensions=["patient_barcode"]))


def test_in_operator_and_limit_cap():
    q = compile_metric(MetricRequest(metric="patients", dimensions=["stage_major"], limit=10_000,
                                     filters=[{"dimension": "stage_major", "operator": "in", "value": ["I", "II"]}]))
    assert "in (%(f0_0)s, %(f0_1)s)" in q.sql and q.sql.endswith("limit 500")


# ---------------------------------------------------------------- SQL guard


@pytest.mark.parametrize("sql", [
    "delete from marts.mart_patient_360",
    "select * from raw.fhir_patient",
    "select * from stg.stg_fhir__patients",
    "select pg_sleep(5)",
    "select 1; select 2",
    "update marts.mart_patient_360 set age_at_diagnosis = 1",
    "with x as (select * from raw.fhir_patient) select * from x",
])
def test_guard_blocks_unsafe_sql(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)


def test_guard_allows_curated_select_and_enforces_limit():
    out = validate_sql("select hospital_name, count(*) from marts.mart_patient_360 group by 1")
    assert out.upper().endswith("LIMIT 500")
    cte = validate_sql("with t as (select * from analytics.km_summary) select * from t limit 10")
    assert "LIMIT 10" in cte.upper()


# ---------------------------------------------------------------- agent loop (mocked Claude client)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=90, cache_creation_input_tokens=0)


def test_agent_runs_tool_loop_and_returns_audited_queries(monkeypatch):
    tool_turn = SimpleNamespace(stop_reason="tool_use", model="claude-opus-5", usage=_usage(), content=[
        SimpleNamespace(type="tool_use", id="tu_1", name="query_metric",
                        input={"metric": "patients", "dimensions": ["stage_major"], "filters": [], "limit": 10})])
    final = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5", usage=_usage(),
                            content=[SimpleNamespace(type="text", text="Stage II is the largest group (n=621).")])
    fake = FakeMessages([tool_turn, final])
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    audit = agent.ExecutedQuery("query_metric", "select ...", rows=[{"stage_major": "II", "value": 621, "n": 621}])
    monkeypatch.setattr(agent, "execute_tool", lambda name, args, s: ('{"rows": []}', audit, False))

    ans = agent.ask("How many patients per stage?", settings=Settings(), client=client)
    assert ans.answer.startswith("Stage II")
    assert ans.queries == [audit]
    assert ans.usage["cache_read_input_tokens"] == 180
    first = fake.calls[0]
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}  # semantic layer prompt is cached
    assert first["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in first["betas"]
    tool_result = fake.calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tu_1"


def test_agent_handles_refusal(monkeypatch):
    refusal = SimpleNamespace(stop_reason="refusal", model="claude-opus-5", usage=_usage(), content=[])
    client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages([refusal])))
    ans = agent.ask("anything", settings=Settings(), client=client)
    assert "declined" in ans.answer and ans.stop_reason == "refusal"


def test_agent_requires_api_key():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        agent.ask("hi", settings=Settings(ANTHROPIC_API_KEY=""))
