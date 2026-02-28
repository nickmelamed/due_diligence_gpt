from __future__ import annotations
from pydantic import BaseModel
from typing import List
from ddgpt.utils.hashing import sha256_file

class InputFile(BaseModel):
    path: str
    sha256: str

def build_inputs_manifest(paths: List[str]) -> List[InputFile]:
    return [InputFile(path=p, sha256=sha256_file(p)) for p in paths]
