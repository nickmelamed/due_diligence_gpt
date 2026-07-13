import os
from pathlib import Path
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.cohere_extractor import CohereExtractor
from ddgpt.extract.ollama_extractor import OllamaExtractor, ollama_is_available
from ddgpt.extract.vision_extractor import OllamaVisionExtractor, ollama_vision_is_available
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


def build_chart_extractor(cfg):
    """Chart/graph vision extractor -- separate from build_extractors since
    it doesn't implement the Extractor ABC (it works off page images, not
    page text, and produces a supplementary chart_extractions list rather
    than one of the six fused scalar metrics). Returns None if disabled,
    using an unsupported provider, or the configured model isn't actually
    pulled/reachable -- same "skip gracefully" pattern as CohereExtractor/
    OllamaExtractor."""
    if not cfg.vision.enabled:
        return None

    if cfg.vision.provider != "ollama":
        return None

    if not ollama_vision_is_available(cfg.vision.host, cfg.vision.model):
        return None

    prompt_text = (Path(cfg.run.prompts_dir) / cfg.vision.prompt).read_text()

    return OllamaVisionExtractor(
        prompt_text,
        model=cfg.vision.model,
        host=cfg.vision.host,
        temperature=cfg.vision.temperature,
        dpi=cfg.vision.dpi,
        max_pages=cfg.vision.max_pages,
    )


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

    if not cfg.vision.enabled:
        status["VisionChartExtractor"] = "disabled in config"
    elif cfg.vision.provider != "ollama":
        status["VisionChartExtractor"] = f"skipped: unsupported provider '{cfg.vision.provider}' (only 'ollama' implemented)"
    elif not ollama_vision_is_available(cfg.vision.host, cfg.vision.model):
        status["VisionChartExtractor"] = (
            f"skipped: model '{cfg.vision.model}' not pulled/reachable at {cfg.vision.host} "
            f"(run: ollama pull {cfg.vision.model})"
        )
    else:
        status["VisionChartExtractor"] = "active"

    return status


def build_pipeline(cfg, extractors, rules, chart_extractor=None) -> DiligencePipeline:
    return DiligencePipeline(
        extractors,
        rules,
        trust_config=cfg.trust,
        redact_before_llm=cfg.run.redact_before_llm,
        chart_extractor=chart_extractor,
        cache_dir=cfg.run.cache_dir,
        enable_disk_cache=cfg.run.enable_disk_cache,
    )
