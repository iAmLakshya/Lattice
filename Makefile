PYTHON := python3
UV := uv
SRC := src/lattice
TESTS := tests

CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

.DEFAULT_GOAL := help

.PHONY: setup install dev hooks env lint lint-fix format format-check typecheck check pre-commit \
        test test-fast test-cov test-verbose test-file test-match \
        docker-up docker-down docker-restart docker-reset docker-status docker-logs \
        shell-postgres shell-memgraph build clean run repl deps-check deps-update loc ci ci-lint ci-test help

setup: env dev hooks docker-up
	@echo "$(GREEN)Setup complete. Run 'make check' to verify.$(RESET)"

install:
	$(UV) pip install -e .

dev:
	$(UV) pip install -e ".[dev]"

hooks:
	pre-commit install

env:
	@test -f .env || cp .env.example .env && echo "Created .env from .env.example"

lint:
	ruff check $(SRC)

lint-fix:
	ruff check $(SRC) --fix

format:
	ruff format $(SRC)

format-check:
	ruff format $(SRC) --check

typecheck:
	mypy $(SRC)

check: format-check lint typecheck test
	@echo "$(GREEN)All checks passed.$(RESET)"

pre-commit:
	pre-commit run --all-files

test:
	pytest $(TESTS)

test-fast:
	pytest $(TESTS) -m "not integration"

test-cov:
	pytest $(TESTS) --cov=$(SRC) --cov-report=term-missing --cov-report=html
	@echo "$(CYAN)Coverage report: htmlcov/index.html$(RESET)"

test-verbose:
	pytest $(TESTS) -v --tb=short

test-file:
	pytest $(F) -v

test-match:
	pytest $(TESTS) -v -k "$(K)"

docker-up:
	docker-compose up -d
	@echo "$(CYAN)Waiting for services...$(RESET)"
	@sleep 3
	@$(MAKE) docker-status

docker-down:
	docker-compose down

docker-restart: docker-down docker-up

docker-reset:
	docker-compose down -v
	docker-compose up -d
	@echo "$(YELLOW)All data volumes reset.$(RESET)"

docker-status:
	@echo "$(CYAN)Service Status:$(RESET)"
	@docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "$(CYAN)Health Checks:$(RESET)"
	@curl -sf http://localhost:6333/health > /dev/null && echo "  Qdrant:       $(GREEN)healthy$(RESET)" || echo "  Qdrant:       $(YELLOW)unavailable$(RESET)"
	@curl -sf http://localhost:3000 > /dev/null && echo "  Memgraph Lab: $(GREEN)healthy$(RESET)" || echo "  Memgraph Lab: $(YELLOW)unavailable$(RESET)"
	@docker exec -it lattice-postgres pg_isready -U lattice -d lattice > /dev/null 2>&1 && echo "  Postgres:     $(GREEN)healthy$(RESET)" || echo "  Postgres:     $(YELLOW)unavailable$(RESET)"

docker-logs:
ifdef S
	docker-compose logs -f $(S)
else
	docker-compose logs -f
endif

shell-postgres:
	docker exec -it lattice-postgres psql -U lattice -d lattice

shell-memgraph:
	docker exec -it code-rag-memgraph mgconsole

build: clean
	$(PYTHON) -m build
	@echo "$(GREEN)Built packages in dist/$(RESET)"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf dist build *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleaned.$(RESET)"

run:
	lattice

repl:
	$(PYTHON) -c "from lattice.cli.bootstrap import *; import asyncio" -i

deps-check:
	$(UV) pip list --outdated

deps-update:
	$(UV) pip install -U -e ".[dev]"

loc:
	@echo "$(CYAN)Lines of Code:$(RESET)"
	@find $(SRC) -name "*.py" -exec cat {} + | wc -l | xargs echo "  Python:"
	@find $(TESTS) -name "*.py" -exec cat {} + | wc -l | xargs echo "  Tests: "

ci: ci-lint ci-test
	@echo "$(GREEN)CI pipeline passed.$(RESET)"

ci-lint:
	@echo "$(CYAN)Running lint checks...$(RESET)"
	ruff check $(SRC)
	ruff format $(SRC) --check
	mypy $(SRC)

ci-test:
	@echo "$(CYAN)Running tests...$(RESET)"
	pytest $(TESTS) --cov=$(SRC) --cov-report=xml -v

help:
	@echo ""
	@echo "$(CYAN)Lattice Development Commands$(RESET)"
	@echo ""
	@echo "$(YELLOW)Setup$(RESET)"
	@echo "  $(GREEN)setup$(RESET)          Complete dev setup (env, deps, hooks, docker)"
	@echo "  $(GREEN)install$(RESET)        Install package (production)"
	@echo "  $(GREEN)dev$(RESET)            Install with dev dependencies"
	@echo "  $(GREEN)hooks$(RESET)          Install pre-commit hooks"
	@echo "  $(GREEN)env$(RESET)            Create .env from example"
	@echo ""
	@echo "$(YELLOW)Code Quality$(RESET)"
	@echo "  $(GREEN)lint$(RESET)           Run linter"
	@echo "  $(GREEN)lint-fix$(RESET)       Run linter with auto-fix"
	@echo "  $(GREEN)format$(RESET)         Format code"
	@echo "  $(GREEN)format-check$(RESET)   Check formatting"
	@echo "  $(GREEN)typecheck$(RESET)      Run type checker (mypy)"
	@echo "  $(GREEN)check$(RESET)          Run all checks"
	@echo "  $(GREEN)pre-commit$(RESET)     Run pre-commit on all files"
	@echo ""
	@echo "$(YELLOW)Testing$(RESET)"
	@echo "  $(GREEN)test$(RESET)           Run all tests"
	@echo "  $(GREEN)test-fast$(RESET)      Run tests (skip integration)"
	@echo "  $(GREEN)test-cov$(RESET)       Run tests with coverage"
	@echo "  $(GREEN)test-verbose$(RESET)   Run tests with verbose output"
	@echo "  $(GREEN)test-file$(RESET)      Run specific file (F=path/to/test.py)"
	@echo "  $(GREEN)test-match$(RESET)     Run matching tests (K=pattern)"
	@echo ""
	@echo "$(YELLOW)Infrastructure$(RESET)"
	@echo "  $(GREEN)docker-up$(RESET)      Start services"
	@echo "  $(GREEN)docker-down$(RESET)    Stop services"
	@echo "  $(GREEN)docker-restart$(RESET) Restart services"
	@echo "  $(GREEN)docker-reset$(RESET)   Reset services (removes data)"
	@echo "  $(GREEN)docker-status$(RESET)  Show service health"
	@echo "  $(GREEN)docker-logs$(RESET)    Tail logs (S=service)"
	@echo ""
	@echo "$(YELLOW)Database$(RESET)"
	@echo "  $(GREEN)shell-postgres$(RESET) Connect to PostgreSQL"
	@echo "  $(GREEN)shell-memgraph$(RESET) Connect to Memgraph"
	@echo ""
	@echo "$(YELLOW)Build$(RESET)"
	@echo "  $(GREEN)build$(RESET)          Build distribution packages"
	@echo "  $(GREEN)clean$(RESET)          Remove build artifacts"
	@echo ""
	@echo "$(YELLOW)Utilities$(RESET)"
	@echo "  $(GREEN)run$(RESET)            Run the CLI"
	@echo "  $(GREEN)repl$(RESET)           Python REPL with package"
	@echo "  $(GREEN)deps-check$(RESET)     Check outdated dependencies"
	@echo "  $(GREEN)deps-update$(RESET)    Update dependencies"
	@echo "  $(GREEN)loc$(RESET)            Count lines of code"
	@echo ""
	@echo "$(YELLOW)CI$(RESET)"
	@echo "  $(GREEN)ci$(RESET)             Run full CI pipeline"
	@echo "  $(GREEN)ci-lint$(RESET)        Run CI lint steps"
	@echo "  $(GREEN)ci-test$(RESET)        Run CI test steps"
	@echo ""
