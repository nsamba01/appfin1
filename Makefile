# ICHESS Finance — raccourcis d'exploitation
.PHONY: help init up down build logs ps restart test test-backend test-frontend migrate backup restore shell clean

help:
	@echo "Cibles disponibles :"
	@echo "  make init          Génère .env (clés + mots de passe initiaux)"
	@echo "  make build         Construit les images Docker"
	@echo "  make up            Démarre la pile"
	@echo "  make down          Arrête la pile"
	@echo "  make ps            État des services"
	@echo "  make logs          Journaux en continu"
	@echo "  make test          Tests backend (conteneur) + frontend (local)"
	@echo "  make test-backend  Tests backend dans Docker"
	@echo "  make test-frontend Tests frontend (vitest)"
	@echo "  make migrate       Applique les migrations"
	@echo "  make backup        Sauvegarde PostgreSQL"
	@echo "  make restore F=... Restaure une sauvegarde"
	@echo "  make shell         Shell Django dans le conteneur backend"

init:
	./scripts/init-secrets.sh

build:
	docker compose build

up:
	docker compose up -d
	@echo "Application : http://localhost:$${NGINX_HTTP_PORT:-8080}"

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f

test: test-backend test-frontend

test-backend:
	docker compose --profile test run --rm backend-test

test-frontend:
	cd frontend && npm run test

migrate:
	docker compose exec backend python manage.py migrate

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh $(F)

shell:
	docker compose exec backend python manage.py shell

clean:
	docker compose down -v
