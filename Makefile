# ============================================
#  J.A.R.V.I.S. — developer task runner
# ============================================
.PHONY: help install install-dev run test coverage lint typecheck check format clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime dependencies
	pip install -r requirements.txt

install-dev: install  ## Install dev/test dependencies
	pip install pytest pytest-asyncio pytest-cov ruff mypy

run:  ## Launch the interactive CLI
	python -m jarvis

test:  ## Run the test suite
	python -m pytest -q

coverage:  ## Run tests with a coverage report
	python -m pytest --cov=jarvis --cov-report=term-missing

lint:  ## Lint the codebase
	ruff check jarvis tests

typecheck:  ## Static type check (advisory)
	mypy jarvis

check: lint test  ## Lint + test (the CI gate)

format:  ## Auto-format the codebase
	ruff format jarvis tests

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache build dist *.egg-info

# -- web (the official site + the dashboard) ----------------------------------

web-install:  ## Install front-end dependencies (once, and after a pull)
	cd web && npm install

site:  ## Build the official site into web/site/dist
	cd web && npm run build --workspace=site

site-dev:  ## Run the site locally with hot reload (http://localhost:5173)
	cd web && npm run dev --workspace=site

dashboard:  ## Stage the dashboard into web/dashboard/dist
	@mkdir -p web/dashboard/dist
	cp web/dashboard/index.html web/dashboard/dist/index.html

# Nginx bind-mounts web/site/dist and web/dashboard/dist. Both must exist
# before `up -d`, or Docker creates them as empty root-owned directories and
# the two hostnames answer 403.
web-build: site dashboard  ## Build everything Nginx serves

deploy-web: web-build  ## Rebuild the front-ends and make Nginx serve the new files
	docker compose -f docker-compose.yml -f docker-compose.prod.yml \
		exec nginx nginx -s reload
	@echo "Site rebuilt and reloaded."
