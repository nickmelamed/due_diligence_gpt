from __future__ import annotations
from pathlib import Path
import json
import typer
from dotenv import load_dotenv
import pandas as pd 
from typing import List

from ddgpt.config import Config
from ddgpt.utils.logging import setup_logger
from ddgpt.pipeline.orchestrator import DiligencePipeline
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.cohere_extractor import CohereExtractor
from ddgpt.rules.numeric_mismatch import NumericMismatchRule
from ddgpt.rules.definition_drift import DefinitionDriftRule
from ddgpt.pipeline.builders import build_extractors, build_rules
from ddgpt.risk.engine import RiskEngine
from ddgpt.copilot.ic_copilot import ICCopilot
from ddgpt.report.tables import to_facts_table
from ddgpt.io.loaders import load_document

app = typer.Typer(add_completion=False, help="DDGPT — Diligence extraction + contradiction flags (Cohere).")

def discover_files(input_dir: str) -> List[str]:
    paths = []
    for ext in ("*.pdf", "*.txt"):
        paths.extend([str(p) for p in Path(input_dir).glob(ext)])
    return sorted(paths)

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

    # Build extractors
    prompt_text = (Path(cfg.run.prompts_dir) / cfg.run.extract_prompt).read_text()

    extractors = []
    if cfg.run.use_cohere:
        extractors.append(
            CohereExtractor(cfg.model.model, cfg.model.temperature, prompt_text)
        )
    extractors.append(RegexExtractor())

    # Build rules
    rules = [
        NumericMismatchRule(
            cfg.rules.aum_tolerance_pct,
            cfg.rules.mgmt_fee_abs_pct,
            cfg.rules.target_irr_abs_pct
        ),
        DefinitionDriftRule()
    ]

    # Build pipeline
    pipeline = DiligencePipeline(extractors, rules)

    # Load documents
    paths = discover_files(input)
    docs = [load_document(p) for p in paths]

    # Run pipeline
    result = pipeline.run(docs)

    # Save outputs
    Path(out).mkdir(parents=True, exist_ok=True)

    (Path(out) / "extracted.json").write_text(
        json.dumps(result["extracted"], indent=2)
    )

    (Path(out) / "flags.json").write_text(
        json.dumps(result["flags"], indent=2)
    )

    (Path(out) / "ic_memo.md").write_text(result["ic_memo"])

    logger.info("✅ run complete (new pipeline)")

@app.command()
def extract(
    input: str = typer.Option("sample_docs", "--input"),
    out: str = typer.Option("outputs/extract_only", "--out"),
    config: str = typer.Option(None, "--config"),
):
    load_dotenv()
    cfg = _load_cfg(config)
    logger = setup_logger(str(Path(out) / "run.log"))
    
    extractors = build_extractors(cfg)
    rules = build_rules(cfg)

    pipeline = DiligencePipeline(extractors, rules)

    paths = discover_files(input)
    docs = [load_document(p) for p in paths]

    extracted = []
    for doc_name, pages in docs:
        doc = pipeline.extractor.extract(doc_name, pages)
        extracted.append(doc.dict())

    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "extracted.json").write_text(json.dumps(extracted, indent=2))

    logger.info(f"✅ extracted {len(extracted)} documents (new pipeline)")

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

    rules = build_rules(cfg)
    risk_engine = RiskEngine(rules)

    flags, risk_score = risk_engine.evaluate(extracted)

    (Path(out) / "flags.json").write_text(
        json.dumps([f.dict() for f in flags], indent=2)
    )

    logger.info(f"✅ produced {len(flags)} flags | risk_score={risk_score:.3f}")

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
    
    extracted = json.loads((Path(out)/"extracted.json").read_text())
    flags = json.loads((Path(out)/"flags.json").read_text()) if (Path(out)/"flags.json").exists() else []

    # structured table
    df = to_facts_table(extracted)
    df.to_csv(Path(out) / "facts_table.csv", index=False)

    # IC copilot
    copilot = ICCopilot()
    memo = copilot.generate(extracted, flags)

    (Path(out) / "ic_memo.md").write_text(memo)

    logger.info("✅ reports written (table + IC memo)")

@app.command()
def eval(
    scenario: str = typer.Option("eval/scenarios/scenario_01", "--scenario"),
    out: str = typer.Option("outputs/eval_run", "--out"),
):
    load_dotenv()
    cfg = Config()
    logger = setup_logger(str(Path(out) / "run.log"))

    extractors = build_extractors(cfg)
    rules = build_rules(cfg)
    pipeline = DiligencePipeline(extractors, rules)

    input_dir = Path(scenario) / "input"
    paths = discover_files(str(input_dir))
    docs = [load_document(p) for p in paths]

    result = pipeline.run(docs)

    Path(out).mkdir(parents=True, exist_ok=True)

    (Path(out)/"flags.json").write_text(
        json.dumps(result["flags"], indent=2)
    )

    expected_path = Path(scenario) / "expected_flags.json"

    if expected_path.exists():
        expected = json.loads(expected_path.read_text())
        actual = result["flags"]

        exp_types = sorted([f["type"] for f in expected])
        act_types = sorted([f["type"] for f in actual])

        if exp_types == act_types:
            logger.info("eval PASS")
        else:
            logger.info(f"eval FAIL\nexpected={exp_types}\nactual={act_types}")

if __name__ == "__main__":
    app()
