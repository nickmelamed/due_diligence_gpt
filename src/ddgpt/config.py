from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional

class ModelConfig(BaseModel):
    provider: str = Field(default="cohere")
    model: str = Field(default="command-r-plus")
    temperature: float = Field(default=0.0)

class RuleConfig(BaseModel):
    aum_tolerance_pct: float = Field(default=0.03)
    mgmt_fee_abs_pct: float = Field(default=0.25)  # percentage points (0.25 = 25 bps)
    target_irr_abs_pct: float = Field(default=2.0)

class RunConfig(BaseModel):
    use_cohere: bool = True
    cache_dir: str = ".cache"
    prompts_dir: str = "prompts"
    extract_prompt: str = "extract_v1.txt"
    memo_prompt: str = "memo_v1.txt"
    rules: List[str] = Field(default_factory=lambda: ["numeric_mismatch", "definition_drift"])

class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    rules: RuleConfig = Field(default_factory=RuleConfig)
    run: RunConfig = Field(default_factory=RunConfig)
