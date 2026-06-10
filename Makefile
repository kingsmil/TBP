# HDB Match — developer commands.
# The `test-core` target runs WITHOUT any third-party deps (stdlib unittest),
# so it works in restricted environments. Other targets need a full local setup.

.PHONY: help db-up db-down db-migrate seed live-load listings-load docker-up docker-down test-core test backend frontend-install frontend-dev frontend-test

help:
	@echo "db-up           Start PostGIS + Redis (docker compose)"
	@echo "db-down         Stop containers"
	@echo "db-migrate      Apply SQL migrations to PostGIS"
	@echo "seed            Generate mock data and load it"
	@echo "live-load       Load live HDB resale data from data.gov.sg into PostGIS"
	@echo "listings-load   Load active HDB Flat Portal listings (use --limit via ARGS)"
	@echo "docker-up       Start db, redis, backend, and frontend in Docker"
	@echo "docker-down     Stop Docker stack"
	@echo "test-core       Run dependency-free core tests (stdlib unittest)"
	@echo "test            Run full backend test suite (needs pytest)"
	@echo "backend         Run FastAPI dev server"
	@echo "frontend-install / frontend-dev / frontend-test"

db-up:
	docker compose up -d db redis

db-down:
	docker compose down

db-migrate:
	cd backend && python -m app.db.migrate

seed:
	cd backend && python -m app.data.seed

live-load:
	docker compose run --rm live-loader

listings-load:
	cd backend && python -m app.data.hdb_listings

docker-up:
	docker compose up -d --build db redis backend frontend

docker-down:
	docker compose down

test-core:
	cd backend && python -m unittest discover -s tests -p "test_*.py" -v

test:
	cd backend && pytest -q

backend:
	cd backend && python -m app.run_server

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-test:
	cd frontend && npm run test
