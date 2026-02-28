.PHONY: install run test eval

install:
	python -m pip install -r requirements.txt
	python -m pip install -e .

run:
	python -m ddgpt run --input sample_docs --out outputs/run_demo

test:
	pytest -q

eval:
	python -m ddgpt eval --scenario eval/scenarios/scenario_01 --out outputs/eval_run
