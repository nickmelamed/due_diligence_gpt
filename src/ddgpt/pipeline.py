from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json

from ddgpt.config import Config
from ddgpt.utils.hashing import sha256_file
from ddgpt.io.loaders import load_document
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.cohere_extractor import CohereExtractor
from ddgpt.extract.postprocess import verify_and_score
from ddgpt.provenance.audit import build_inputs_manifest
from ddgpt.rules.numeric_mismatch import NumericMismatchRule
from ddgpt.rules.definition_drift import DefinitionDriftRule
from ddgpt.report.tables import to_facts_table
from ddgpt.report.ic_memo import generate_ic_summary

def _load_prompt(prompts_dir: str, name: str) -> str:
    return (Path(prompts_dir) / name).read_text(encoding="utf-8")

def discover_files(input_dir: str) -> List[str]:
    paths = []
    for ext in ("*.pdf", "*.txt"):
        paths.extend([str(p) for p in Path(input_dir).glob(ext)])
    return sorted(paths)

def _cache_path(cache_dir: str, file_sha: str) -> Path:
    return Path(cache_dir) / f"{file_sha}.json"

def write_run_manifests(paths: List[str], cfg: Config, out_dir: str) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "config.json").write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    inputs = [x.model_dump() for x in build_inputs_manifest(paths)]
    (Path(out_dir) / "inputs.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")

def extract_all(paths: List[str], cfg: Config, out_dir: str, logger) -> List[Dict[str, Any]]:
    Path(cfg.run.cache_dir).mkdir(parents=True, exist_ok=True)
    prompt_text = _load_prompt(cfg.run.prompts_dir, cfg.run.extract_prompt)

    extractor = None
    if cfg.run.use_cohere:
        try:
            extractor = CohereExtractor(cfg.model.model, cfg.model.temperature, prompt_text)
        except Exception as e:
            logger.info(f"cohere disabled or unavailable; using regex fallback. Error={type(e).__name__}: {e}")
            extractor = None

    fallback = RegexExtractor()

    extracted_docs: List[Dict[str, Any]] = []
    for path in paths:
        fsha = sha256_file(path)
        cp = _cache_path(cfg.run.cache_dir, fsha)

        if cp.exists():
            logger.info(f"cache hit: {Path(path).name}")
            extracted_docs.append(json.loads(cp.read_text(encoding="utf-8")))
            continue

        doc_name, pages = load_document(path)
        logger.info(f"extracting: {doc_name}")

        try:
            doc = extractor.extract(doc_name, pages) if extractor else fallback.extract(doc_name, pages)
        except Exception as e:
            logger.info(f"cohere extraction failed for {doc_name}; fallback to regex. Error={type(e).__name__}: {e}")
            doc = fallback.extract(doc_name, pages)
            doc.notes.append(f"NOTE: Cohere extraction failed; used regex fallback. Error: {type(e).__name__}: {e}")

        doc = verify_and_score(doc, pages)
        data = doc.model_dump()
        cp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        extracted_docs.append(data)

    (Path(out_dir) / "extracted.json").write_text(json.dumps(extracted_docs, indent=2), encoding="utf-8")
    return extracted_docs

def run_rules(extracted: List[Dict[str, Any]], cfg: Config, out_dir: str, logger) -> List[Dict[str, Any]]:
    rules = []
    if "numeric_mismatch" in cfg.run.rules:
        rules.append(NumericMismatchRule(cfg.rules.aum_tolerance_pct, cfg.rules.mgmt_fee_abs_pct, cfg.rules.target_irr_abs_pct))
    if "definition_drift" in cfg.run.rules:
        rules.append(DefinitionDriftRule())

    flags = []
    for r in rules:
        flags.extend([f.model_dump() for f in r.apply(extracted)])

    (Path(out_dir) / "flags.json").write_text(json.dumps(flags, indent=2), encoding="utf-8")
    return flags

def build_reports(extracted: List[Dict[str, Any]], flags: List[Dict[str, Any]], cfg: Config, out_dir: str, logger) -> None:
    df = to_facts_table(extracted)
    df.to_csv(Path(out_dir) / "facts_table.csv", index=False)

    memo_prompt = _load_prompt(cfg.run.prompts_dir, cfg.run.memo_prompt)
    memo = generate_ic_summary(extracted, flags, memo_prompt=memo_prompt)
    (Path(out_dir) / "ic_summary.md").write_text(memo, encoding="utf-8")

def run_pipeline(input_dir: str, out_dir: str, cfg: Config, logger) -> None:
    paths = discover_files(input_dir)
    if not paths:
        raise RuntimeError(f"No .pdf or .txt files found in {input_dir}")
    write_run_manifests(paths, cfg, out_dir)
    extracted = extract_all(paths, cfg, out_dir, logger)
    flags = run_rules(extracted, cfg, out_dir, logger)
    build_reports(extracted, flags, cfg, out_dir, logger)
