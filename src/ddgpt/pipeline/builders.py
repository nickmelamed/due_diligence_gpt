from pathlib import Path
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.cohere_extractor import CohereExtractor
from ddgpt.rules.numeric_mismatch import NumericMismatchRule
from ddgpt.rules.definition_drift import DefinitionDriftRule

def build_extractors(cfg):
    prompt_text = (Path(cfg.run.prompts_dir) / cfg.run.extract_prompt).read_text()

    extractors = []
    if cfg.run.use_cohere:
        extractors.append(
            CohereExtractor(cfg.model.model, cfg.model.temperature, prompt_text)
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
        DefinitionDriftRule()
    ]