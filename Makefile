.PHONY: lint format typecheck test run check clean

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

%:
	@true

check: lint format typecheck test
	@echo "All checks passed."

clean:
	find chroma -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find chroma -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true