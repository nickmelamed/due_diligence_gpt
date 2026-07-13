from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Dict

class ModelConfig(BaseModel):
    provider: str = "cohere"
    model: str = "command-a-03-2025"
    temperature: float = 0.0

class OllamaConfig(BaseModel):
    # Second, independent LLM extractor backed by a local open-weight model.
    # `enabled` only takes effect if an Ollama server is actually reachable
    # at pipeline build time; otherwise this extractor silently skips
    # itself, the same way CohereExtractor does when CO_API_KEY is unset.
    enabled: bool = True
    model: str = "llama3.2:3b"
    temperature: float = 0.0
    host: str = "http://localhost:11434"

class RuleConfig(BaseModel):
    aum_tolerance_pct: float = 0.03
    mgmt_fee_abs_pct: float = 0.25
    target_irr_abs_pct: float = 2.0

    # Deliberately tighter than target_irr_abs_pct: that tolerance is for
    # *cross-document* comparison, where some drift is expected (different
    # as-of dates, marketing vs underwriting). This is for a *single*
    # document contradicting itself, where even a couple points of
    # difference paired with a different gross/net label is suspicious.
    internal_irr_mention_tolerance_pct: float = 1.0

class OCRConfig(BaseModel):
    enabled: bool = True
    dpi: int = 300

class TrustConfig(BaseModel):
    """Extractor trust priors and document-authority weights. Previously
    hardcoded constants in fusion_extractor.py/postprocess.py; exposed here
    so trust priors can be tuned per engagement without a code change."""

    extractor_weights: Dict[str, float] = Field(default_factory=lambda: {
        "RegexExtractor": 0.95,
        "CohereExtractor": 0.70,
        "OllamaExtractor": 0.60,
    })
    extractor_default_weight: float = 0.50

    # First substring match (checked in dict order) against the lowercased
    # doc_name wins; falls back to authority_default_weight.
    authority_weights: Dict[str, float] = Field(default_factory=lambda: {
        "lpa": 0.98,
        "agreement": 0.95,
        "audited": 0.93,
        "financial": 0.90,
        "statement": 0.85,
        "quarter": 0.75,
        "update": 0.70,
        "deck": 0.55,
    })
    authority_default_weight: float = 0.50

class RunConfig(BaseModel):
    use_cohere: bool = True

    cache_dir: str = ".cache"
    enable_disk_cache: bool = True

    prompts_dir: str = "prompts"

    extract_prompt: str = "extract_v1.txt"

    memo_prompt: str = "memo_v1.txt"

    enable_ocr: bool = True

    enable_pdf_output: bool = True

    enable_streamlit: bool = True

    # Strip obviously sensitive identifiers (emails, phone numbers, SSNs,
    # account numbers) out of page text before it's sent to any third-party
    # LLM API. Local-only extraction (use_cohere=False, no Ollama) never
    # leaves the machine at all regardless of this flag.
    redact_before_llm: bool = False

class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)

    rules: RuleConfig = Field(default_factory=RuleConfig)

    ocr: OCRConfig = Field(default_factory=OCRConfig)

    trust: TrustConfig = Field(default_factory=TrustConfig)

    run: RunConfig = Field(default_factory=RunConfig)
