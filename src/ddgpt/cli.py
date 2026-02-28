from __future__ import annotations
from pathlib import Path
import json
import typer
from dotenv import load_dotenv

from ddgpt.config import Config
from ddgpt.pipeline import run_pipeline, extract_all, run_rules, build_reports, discover_files, write_run_manifests
from ddgpt.utils.logging import setup_logger

app = typer.Typer(add_completion=False, help="DDGPT — Diligence extraction + contradiction flags (Cohere).")

def _load_cfg(config_path: str | None) -> Config:
    if not config_path:
        return Config()
    p = Path(config_path)
    if not p.exists():
        raise typer.BadParameter(f"Config file not found: {config_path}")
    if p.suffix.lower() == ".json":
        return Config.model_validate_json(p.read_text(encoding="utf-8"))
    import yaml
    return Config.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))

@app.command()
def run(
    input: str = typer.Option("sample_docs", "--input"),
    out: str = typer.Option("outputs/run_demo", "--out"),
    config: str = typer.Option(None, "--config"),
):
    load_dotenv()
    cfg = _load_cfg(config)
    logger = setup_logger(str(Path(out) / "run.log"))
    run_pipeline(input, out, cfg, logger)
    logger.info("✅ run complete")

@app.command()
def extract(
    input: str = typer.Option("sample_docs", "--input"),
    out: str = typer.Option("outputs/extract_only", "--out"),
    config: str = typer.Option(None, "--config"),
):
    load_dotenv()
    cfg = _load_cfg(config)
    logger = setup_logger(str(Path(out) / "run.log"))
    paths = discover_files(input)
    write_run_manifests(paths, cfg, out)
    extracted = extract_all(paths, cfg, out, logger)
    logger.info(f"✅ extracted {len(extracted)} documents")

@app.command()
def flag(
    out: str = typer.Option("outputs/extract_only", "--out"),
    config: str = typer.Option(None, "--config"),
):
    load_dotenv()
    cfg = _load_cfg(config)
    logger = setup_logger(str(Path(out) / "run.log"))
    extracted_path = Path(out) / "extracted.json"
    if not extracted_path.exists():
        raise typer.BadParameter(f"Missing extracted.json in {out}. Run extract first.")
    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    flags = run_rules(extracted, cfg, out, logger)
    logger.info(f"✅ produced {len(flags)} flags")

@app.command()
def report(
    out: str = typer.Option("outputs/extract_only", "--out"),
    config: str = typer.Option(None, "--config"),
):
    load_dotenv()
    cfg = _load_cfg(config)
    logger = setup_logger(str(Path(out) / "run.log"))
    extracted = json.loads((Path(out)/"extracted.json").read_text(encoding="utf-8"))
    flags = json.loads((Path(out)/"flags.json").read_text(encoding="utf-8")) if (Path(out)/"flags.json").exists() else []
    build_reports(extracted, flags, cfg, out, logger)
    logger.info("✅ reports written")

@app.command()
def eval(
    scenario: str = typer.Option("eval/scenarios/scenario_01", "--scenario"),
    out: str = typer.Option("outputs/eval_run", "--out"),
):
    load_dotenv()
    cfg = Config()
    logger = setup_logger(str(Path(out) / "run.log"))
    run_pipeline(str(Path(scenario)/"input"), out, cfg, logger)
    expected_path = Path(scenario) / "expected_flags.json"
    if expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        actual = json.loads((Path(out)/"flags.json").read_text(encoding="utf-8"))
        exp_types = sorted([f["type"] for f in expected])
        act_types = sorted([f["type"] for f in actual])
        if exp_types == act_types:
            logger.info("✅ eval PASS: flag types match expected")
        else:
            logger.info(f"❌ eval FAIL\nexpected={exp_types}\nactual={act_types}")
    else:
        logger.info("No expected_flags.json found; ran scenario only.")

if __name__ == "__main__":
    app()
