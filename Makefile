.PHONY: lint format typecheck test run check samples clean

lint:
	ruff check chroma/

format:
	ruff format chroma/

typecheck:
	pyright chroma/

test:
	python3 -m unittest discover -v -s chroma/tests

run:
	python3 -m chroma $(or $(filter-out $@,$(MAKECMDGOALS)),6366f1)

samples:
	python3 -m chroma 6366f1 -o samples/tailwind-v4.css
	python3 -m chroma 6366f1 -f tailwind-v3 -o samples/tailwind-v3.js
	python3 -m chroma 6366f1 -f css -o samples/chroma.css
	python3 -m chroma 6366f1 -f ts -o samples/chroma-theme.ts
	python3 -m chroma 6366f1 -f dtcg -o samples/chroma-theme.dtcg.json
	python3 -m chroma 6366f1 -f json -o samples/chroma-tokens.json

%:
	@true

check: lint format typecheck test
	@echo "All checks passed."

clean:
	find chroma -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find chroma -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true