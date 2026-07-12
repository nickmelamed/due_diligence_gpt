from pathlib import Path
import os
import subprocess
import sys

def test_run_smoke(tmp_path):
    env = dict(os.environ)
    env["CO_API_KEY"] = ""  # force regex-only fallback; load_dotenv(override=False) won't clobber a set-but-empty var
    out = tmp_path / "out"
    cmd = [sys.executable, "-m", "ddgpt", "run", "--input", "sample_docs", "--out", str(out)]
    env["PYTHONPATH"] = "src"
    subprocess.check_call(cmd, cwd=Path(__file__).resolve().parents[1], env=env)
    assert (out / "extracted.json").exists()
    assert (out / "flags.json").exists()
    assert (out / "ic_memo.md").exists()
