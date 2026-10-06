import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ddgpt import cli
from ddgpt.extract.regex_extractor import RegexExtractor

REPO = Path(__file__).resolve().parents[1]
SCENARIO = REPO / "eval" / "scenarios" / "scenario_01"


def _offline(monkeypatch, tmp_path):
    # Regex only, so the result does not depend on Cohere or a local Ollama.
    monkeypatch.setenv("CO_API_KEY", "")
    monkeypatch.setattr(cli, "build_extractors", lambda cfg: [RegexExtractor()])
    monkeypatch.setattr(cli, "build_chart_extractor", lambda cfg: None)
    monkeypatch.chdir(tmp_path)


def test_eval_passes_on_the_bundled_scenario(monkeypatch, tmp_path):
    _offline(monkeypatch, tmp_path)

    result = CliRunner().invoke(cli.app, ["eval", "--scenario", str(SCENARIO), "--out", str(tmp_path / "out")])

    assert result.exit_code == 0
    assert "eval PASS" in (tmp_path / "out" / "run.log").read_text()


def test_eval_exits_nonzero_when_expected_flags_differ(monkeypatch, tmp_path):
    _offline(monkeypatch, tmp_path)
    scenario = tmp_path / "scenario"
    shutil.copytree(SCENARIO, scenario)
    (scenario / "expected_flags.json").write_text(json.dumps([{"severity": "RED", "type": "MGMT_FEE_MISMATCH"}]))

    result = CliRunner().invoke(cli.app, ["eval", "--scenario", str(scenario), "--out", str(tmp_path / "out")])

    assert result.exit_code == 1
    assert "eval FAIL" in (tmp_path / "out" / "run.log").read_text()
