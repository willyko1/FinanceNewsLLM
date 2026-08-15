.PHONY: install dev test lint eval

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn finresearch.web:app --reload

test:
	pytest -q

lint:
	ruff check .

eval:
	python evals/run.py
