from pathlib import Path
import os
import subprocess
import sys

def test_run_smoke(tmp_path):
    env = dict(os.environ)
    env["COHERE_API_KEY"] = ""  # force fallback
    out = tmp_path / "out"
    cmd = [sys.executable, "-m", "ddgpt", "run", "--input", "sample_docs", "--out", str(out)]
    env["PYTHONPATH"] = "src"
    subprocess.check_call(cmd, cwd=Path(__file__).resolve().parents[1], env=env)
    assert (out / "extracted.json").exists()
    assert (out / "flags.json").exists()
    assert (out / "ic_summary.md").exists()
