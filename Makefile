COMPOSE := docker compose --profile prod
DEV_COMPOSE := docker compose --profile dev

.PHONY: up down logs build dev test lint verify config

up: build
	docker compose --profile dev down --remove-orphans
	$(COMPOSE) up -d --wait

down:
	docker compose --profile prod --profile dev down --remove-orphans

logs:
	$(COMPOSE) logs -f

build:
	$(COMPOSE) build

dev:
	docker compose --profile prod down --remove-orphans
	$(DEV_COMPOSE) up --build

test:
	$(DEV_COMPOSE) run --rm --no-deps backend-dev sh -c 'uv sync --frozen --no-install-project && pytest'
	$(DEV_COMPOSE) run --rm --no-deps frontend-dev sh -c 'pnpm install --frozen-lockfile --force && pnpm test'

lint:
	$(DEV_COMPOSE) run --rm --no-deps backend-dev sh -c 'uv sync --frozen --no-install-project && ruff check .'
	$(DEV_COMPOSE) run --rm --no-deps frontend-dev sh -c 'pnpm install --frozen-lockfile --force && pnpm lint'

config:
	docker compose --profile prod config --quiet
	docker compose --profile dev config --quiet

verify: config build
	$(COMPOSE) up -d --wait
	curl --fail --silent --show-error http://127.0.0.1:8001/health > /dev/null
	curl --fail --silent --show-error http://127.0.0.1:8080/ > /dev/null
