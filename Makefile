PY ?= python3.11
VENV := backend/.venv
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: install dev backend frontend test clean

install: $(VENV) frontend/node_modules
	@test -f .env || cp .env.example .env

$(VENV): backend/requirements.txt
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install -q -r backend/requirements.txt
	@touch $(VENV)

frontend/node_modules: frontend/package.json
	cd frontend && npm install
	@touch frontend/node_modules

## Run backend and frontend together; Ctrl+C stops both.
## Ports: make dev BACKEND_PORT=8100 FRONTEND_PORT=3100
dev: install
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && .venv/bin/uvicorn main:app --reload --port $(BACKEND_PORT)) & \
	(cd frontend && API_URL=http://localhost:$(BACKEND_PORT) npm run dev -- -p $(FRONTEND_PORT)) & \
	wait

backend: $(VENV)
	cd backend && .venv/bin/uvicorn main:app --reload --port $(BACKEND_PORT)

frontend: frontend/node_modules
	cd frontend && API_URL=http://localhost:$(BACKEND_PORT) npm run dev -- -p $(FRONTEND_PORT)

test: $(VENV)
	cd backend && .venv/bin/pytest -q

clean:
	rm -rf $(VENV) frontend/node_modules frontend/.next frontend/.next-dev
