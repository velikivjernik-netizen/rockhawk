.PHONY: up down logs test backend-test frontend-test demo migrate fmt

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	cd backend && alembic upgrade head

backend-test:
	cd backend && python3 -m pytest -q

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test

demo:
	cp -n .env.example .env || true
	docker compose up --build
