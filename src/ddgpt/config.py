from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List

class ModelConfig(BaseModel):
    provider: str = "cohere"
    model: str = "command-a-03-2025"
    temperature: float = 0.0

class RuleConfig(BaseModel):
    aum_tolerance_pct: float = 0.03
    mgmt_fee_abs_pct: float = 0.25
    target_irr_abs_pct: float = 2.0

class OCRConfig(BaseModel):
    enabled: bool = True
    dpi: int = 300

class RunConfig(BaseModel):
    use_cohere: bool = True

    cache_dir: str = ".cache"

    prompts_dir: str = "prompts"

    extract_prompt: str = "extract_v1.txt"

    memo_prompt: str = "memo_v1.txt"

    enable_ocr: bool = True

    enable_pdf_output: bool = True

    enable_streamlit: bool = True

class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)

    rules: RuleConfig = Field(default_factory=RuleConfig)

    ocr: OCRConfig = Field(default_factory=OCRConfig)

    run: RunConfig = Field(default_factory=RunConfig)
