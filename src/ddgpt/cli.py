from __future__ import annotations
from pathlib import Path
from datetime import datetime, UTC
import json
import typer
from dotenv import load_dotenv
import pandas as pd
from typing import List

from ddgpt.config import Config
from ddgpt.utils.logging import setup_logger
from ddgpt.utils.cache import disk_cached, content_hash
from ddgpt.pipeline.builders import build_extractors, build_rules, build_pipeline, build_chart_extractor, extractor_availability
from ddgpt.risk.engine import RiskEngine
from ddgpt.copilot.ic_copilot import ICCopilot
from ddgpt.copilot.recommendation_engine import determine_recommendation
from ddgpt.report.tables import to_facts_table
from ddgpt.render.pdf_report import render_ic_pdf
from ddgpt.provenance.audit import build_inputs_manifest, build_audit_manifest
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

def _load_docs(cfg: Config, paths: List[str]):
    docs = []

    for p in paths:
        file_bytes = Path(p).read_bytes()
        key = content_hash(file_bytes, str(cfg.ocr.enabled), str(cfg.ocr.dpi))

        docs.append(
            disk_cached(
                cfg.run.cache_dir,
                "loaded_documents",
                key,
                lambda p=p: load_document(p, ocr_enabled=cfg.ocr.enabled, ocr_dpi=cfg.ocr.dpi),
                enabled=cfg.run.enable_disk_cache,
            )
        )

    return docs

@app.command()
def run(
    input: str = typer.Option("sample_docs", "--input"),
    out: str = typer.Option("outputs/run_demo", "--out"),
    config: str = typer.Option(None, "--config"),
):
    load_dotenv()
    cfg = _load_cfg(config)
    logger = setup_logger(str(Path(out) / "run.log"))

    extractors = build_extractors(cfg)
    rules = build_rules(cfg)
    chart_extractor = build_chart_extractor(cfg)
    pipeline = build_pipeline(cfg, extractors, rules, chart_extractor=chart_extractor)

    avail = extractor_availability(cfg)
    for name, status in avail.items():
        logger.info(f"extractor {name}: {status}")

    paths = discover_files(input)
    docs = _load_docs(cfg, paths)

    result = pipeline.run(docs)

    out_path = Path(out)
    out_path.mkdir(parents=True, exist_ok=True)

    (out_path / "config.json").write_text(json.dumps(cfg.dict(), indent=2))

    (out_path / "inputs.json").write_text(
        json.dumps([m.dict() for m in build_inputs_manifest(paths)], indent=2)
    )

    (out_path / "extracted.json").write_text(
        json.dumps(result["extracted"], indent=2)
    )

    (out_path / "flags.json").write_text(
        json.dumps(result["flags"], indent=2)
    )

    (out_path / "ic_memo.md").write_text(result["ic_memo"])

    facts_df = to_facts_table(result["extracted"])
    facts_df.to_csv(out_path / "facts_table.csv", index=False)

    if cfg.run.enable_pdf_output:
        render_ic_pdf(
            output_path=str(out_path / "ic_memo.pdf"),
            memo=result["ic_memo"],
            flags=result["flags"],
            facts_df=facts_df,
            risk_score=result["risk_score"],
            extracted=result["extracted"],
            recommendation=result["recommendation"]
        )

    output_names = ["config.json", "inputs.json", "extracted.json", "flags.json", "ic_memo.md", "facts_table.csv"]
    if cfg.run.enable_pdf_output:
        output_names.append("ic_memo.pdf")

    manifest = build_audit_manifest(
        input_paths=paths,
        output_paths=[out_path / name for name in output_names],
        cfg=cfg,
        extractor_availability=avail,
        result=result,
    )
    (out_path / "audit_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Lightweight, per-run observability record -- distinct from the audit
    # manifest (which is a reproducibility/compliance record with hashes and
    # git commit): this is meant to be cheap to parse and concatenate across
    # many runs once multi-document aggregation exists.
    severity_counts: dict = {}
    for f in result["flags"]:
        severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

    run_summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "document_count": len(docs),
        "timings_s": result.get("timings"),
        "extractor_availability": avail,
        "flags_by_severity": severity_counts,
        "risk_score": result["risk_score"],
        "recommendation": result["recommendation"]["decision"],
        "recommendation_confidence": result["recommendation"]["confidence"],
    }
    (out_path / "run_summary.json").write_text(json.dumps(run_summary, indent=2))

    logger.info(
        f"✅ run complete | docs={len(docs)} | flags={len(result['flags'])} | "
        f"risk_score={result['risk_score']:.3f} | "
        f"recommendation={result['recommendation']['decision']} | "
        f"stage_timings_s={result.get('timings')}"
    )

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
    chart_extractor = build_chart_extractor(cfg)

    pipeline = build_pipeline(cfg, extractors, rules, chart_extractor=chart_extractor)

    paths = discover_files(input)
    docs = _load_docs(cfg, paths)

    extracted = []
    for doc in docs:
        extracted_doc = pipeline.extractor.extract(doc.doc_name, doc.pages, doc.tables, doc.layout, path=doc.path)
        extracted.append(extracted_doc.dict())

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

    # structured table
    df = to_facts_table(extracted)
    df.to_csv(Path(out) / "facts_table.csv", index=False)

    recommendation = determine_recommendation(flags)
    risk_score = RiskEngine.score_from_severities([f["severity"] for f in flags])

    # IC copilot (falls back to a deterministic template if CO_API_KEY is unset)
    copilot = ICCopilot()
    memo = copilot.generate(extracted, flags, recommendation=recommendation)

    (Path(out) / "ic_memo.md").write_text(memo)

    if cfg.run.enable_pdf_output:
        render_ic_pdf(
            output_path=str(Path(out) / "ic_memo.pdf"),
            memo=memo,
            flags=flags,
            facts_df=df,
            risk_score=risk_score,
            extracted=extracted,
            recommendation=recommendation
        )

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
    chart_extractor = build_chart_extractor(cfg)
    pipeline = build_pipeline(cfg, extractors, rules, chart_extractor=chart_extractor)

    input_dir = Path(scenario) / "input"
    paths = discover_files(str(input_dir))
    docs = _load_docs(cfg, paths)

    result = pipeline.run(docs)

    Path(out).mkdir(parents=True, exist_ok=True)

    (Path(out)/"flags.json").write_text(
        json.dumps(result["flags"], indent=2)
    )

    expected_path = Path(scenario) / "expected_flags.json"

    if expected_path.exists():
        expected = json.loads(expected_path.read_text())
        actual = result["flags"]

        exp_pairs = sorted([(f["type"], f["severity"]) for f in expected])
        act_pairs = sorted([(f["type"], f["severity"]) for f in actual])

        if exp_pairs == act_pairs:
            logger.info("eval PASS")
        else:
            logger.info(f"eval FAIL\nexpected={exp_pairs}\nactual={act_pairs}")

if __name__ == "__main__":
    app()
