from __future__ import annotations

import os
import platform
import subprocess
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ddgpt import __version__ as ddgpt_version
from ddgpt.utils.hashing import sha256_file

class InputFile(BaseModel):
    path: str
    sha256: str

def build_inputs_manifest(paths: List[str]) -> List[InputFile]:
    return [InputFile(path=p, sha256=sha256_file(p)) for p in paths]


def get_git_commit() -> Optional[str]:
    """Best-effort git HEAD of the ddgpt install itself -- not the input
    documents -- so a manifest can be traced back to the exact code revision
    that produced it. Resolved from this file's location, not the caller's
    cwd, so it works the same whether invoked from the repo root or not."""
    repo_root = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def hash_output_files(paths: List[Path]) -> Dict[str, str]:
    return {p.name: sha256_file(str(p)) for p in paths if p.exists()}


def build_audit_manifest(
    input_paths: List[str],
    output_paths: List[Path],
    cfg: Any,
    extractor_availability: Dict[str, str],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """One consolidated, reproducibility-oriented record per run: what code
    and config produced it, what inputs went in, what extractors/models were
    actually used, and a hash of every output artifact -- so any of
    extracted.json/flags.json/ic_memo.pdf can later be verified as having
    come from this exact run rather than being hand-edited afterward."""
    flags = result.get("flags", [])
    severity_counts: Dict[str, int] = {}
    for f in flags:
        severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

    return {
        "run_id": str(uuid.uuid4()),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ddgpt_version": ddgpt_version,
        "git_commit": get_git_commit(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "operator": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
        "inputs": [m.dict() for m in build_inputs_manifest(input_paths)],
        "extractors": extractor_availability,
        "models": {
            "cohere_model": cfg.model.model,
            "ollama_model": cfg.ollama.model,
            "ollama_host": cfg.ollama.host,
        },
        "document_count": len(result.get("extracted", [])),
        "flags_by_severity": severity_counts,
        "risk_score": result.get("risk_score"),
        "recommendation": result.get("recommendation"),
        "stage_timings_s": result.get("timings"),
        "output_hashes": hash_output_files(output_paths),
    }
