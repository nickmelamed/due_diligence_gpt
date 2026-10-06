.PHONY: setup install run test eval lint typecheck test-fast style agent-check ci

PY ?= python3

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e ".[dev]"

install: setup

run:
	python -m ddgpt run --input sample_docs --out outputs/run_demo

lint:
	ruff check .

typecheck:
	mypy

test:
	pytest -q

test-fast:
	pytest -x -q -m "not slow"

eval:
	python -m ddgpt eval --scenario eval/scenarios/scenario_01 --out outputs/eval_run

style:
	$(PY) scripts/agent/check_style.py --changed .

# The fast checks the Stop hook runs before Claude may end a turn.
agent-check: lint typecheck test-fast style

ci: lint typecheck test style
	$(PY) scripts/agent/check_tests.py --warn
