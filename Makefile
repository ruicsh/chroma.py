.PHONY: lint format typecheck test run check samples clean

lint:
	uv run ruff check chroma/

format:
	uv run ruff format chroma/

typecheck:
	uv run pyright chroma/

test:
	uv run python -m unittest discover -v -s chroma/tests

run:
	uv run python -m chroma $(or $(filter-out $@,$(MAKECMDGOALS)),6366f1)

samples:
	uv run python -m chroma 6366f1 -o samples/tailwind-v4.css
	uv run python -m chroma 6366f1 -f tailwind-v3 -o samples/tailwind-v3.js
	uv run python -m chroma 6366f1 -f css -o samples/theme.css
	uv run python -m chroma 6366f1 -f ts -o samples/theme.ts
	uv run python -m chroma 6366f1 -f dtcg -o samples/theme.dtcg.json
	uv run python -m chroma 6366f1 -f figma -o samples/figma.json
	uv run python -m chroma 6366f1 -f json -o samples/tokens.json
	uv run python -m chroma 6366f1 -f sass -o samples/theme.scss
	uv run python -m chroma 6366f1 -f less -o samples/theme.less
	uv run python -m chroma 6366f1 -f stylus -o samples/theme.styl

%:
	@true

check: lint format typecheck test
	@echo "All checks passed."

clean:
	find chroma -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find chroma -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true