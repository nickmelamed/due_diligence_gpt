---
name: eval-scenario
description: Run ddgpt eval on eval/scenarios/scenario_01 and report expected versus actual flags.
disable-model-invocation: true
---

1. Run `./due_gpt/bin/python -m ddgpt eval --scenario eval/scenarios/scenario_01 --out outputs/eval_run`.
2. The command exits 1 on FAIL. Read PASS or FAIL in
   `outputs/eval_run/run.log`.
3. Show the expected and actual `(type, severity)` pairs side by side.
4. Report which extractors were active, since the result depends on them.
5. Do not edit `expected_flags.json` to force a pass. If it looks stale, ask
   the owner.
