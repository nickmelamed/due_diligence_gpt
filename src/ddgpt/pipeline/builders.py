import os
from pathlib import Path
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.cohere_extractor import CohereExtractor
from ddgpt.extract.ollama_extractor import OllamaExtractor, ollama_is_available
from ddgpt.rules.numeric_mismatch import NumericMismatchRule
from ddgpt.rules.definition_drift import DefinitionDriftRule
from ddgpt.rules.internal_inconsistency import InternalInconsistencyRule
from ddgpt.rules.extractor_disagreement import ExtractorDisagreementRule
from ddgpt.rules.irr_mention_conflict import IRRMentionConflictRule
from ddgpt.pipeline.orchestrator import DiligencePipeline

def build_extractors(cfg):
    prompt_text = (Path(cfg.run.prompts_dir) / cfg.run.extract_prompt).read_text()

    extractors = []
    if cfg.run.use_cohere and os.getenv("CO_API_KEY"):
        extractors.append(
            CohereExtractor(cfg.model.model, cfg.model.temperature, prompt_text)
        )

    if cfg.ollama.enabled and ollama_is_available(cfg.ollama.host):
        extractors.append(
            OllamaExtractor(cfg.ollama.model, cfg.ollama.temperature, prompt_text, host=cfg.ollama.host)
        )

    extractors.append(RegexExtractor())
    return extractors


def build_rules(cfg):
    return [
        NumericMismatchRule(
            cfg.rules.aum_tolerance_pct,
            cfg.rules.mgmt_fee_abs_pct,
            cfg.rules.target_irr_abs_pct
        ),
        DefinitionDriftRule(),
        InternalInconsistencyRule(),
        ExtractorDisagreementRule(),
        IRRMentionConflictRule(cfg.rules.internal_irr_mention_tolerance_pct),
    ]


def extractor_availability(cfg) -> dict:
    """Status of every optional LLM extractor, whether or not it ended up in
    the ensemble -- so a missing API key or an unreachable local Ollama
    server is a visible, explained skip rather than a silent absence from
    the audit trail with no indication anything was even considered."""
    status = {}

    if not cfg.run.use_cohere:
        status["CohereExtractor"] = "disabled in config"
    elif not os.getenv("CO_API_KEY"):
        status["CohereExtractor"] = "skipped: CO_API_KEY not set"
    else:
        status["CohereExtractor"] = "active"

    if not cfg.ollama.enabled:
        status["OllamaExtractor"] = "disabled in config"
    elif not ollama_is_available(cfg.ollama.host):
        status["OllamaExtractor"] = f"skipped: no Ollama server reachable at {cfg.ollama.host}"
    else:
        status["OllamaExtractor"] = "active"

    return status


def build_pipeline(cfg, extractors, rules) -> DiligencePipeline:
    return DiligencePipeline(
        extractors,
        rules,
        trust_config=cfg.trust,
        redact_before_llm=cfg.run.redact_before_llm,
        cache_dir=cfg.run.cache_dir,
        enable_disk_cache=cfg.run.enable_disk_cache,
    )
