---
name: eval-scenario
description: Run ddgpt eval on eval/scenarios/scenario_01 and report expected versus actual flags.
disable-model-invocation: true
---

Run the evaluation scenario and compare flags.

1. Run `./due_gpt/bin/python -m ddgpt eval --scenario eval/scenarios/scenario_01 --out outputs/eval_run`.
2. The command only logs PASS or FAIL to `outputs/eval_run/run.log` and
   exits 0 either way, so read the log to find the result.
3. Show the expected and actual `(type, severity)` pairs side by side.
4. Report which extractors were active, since the result depends on them.
5. Never edit `expected_flags.json` to make a run pass. If the expected
   file looks stale, say so and ask the owner.
