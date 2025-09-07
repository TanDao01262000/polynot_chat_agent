.PHONY: dev dev-d prod build stop logs clean restart setup install test test-local test-chat test-feedback test-level lint run-local

# Development (with auto-reload)
dev:
	docker-compose up --build

# Development (detached)
dev-d:
	docker-compose up -d --build

# Production (without auto-reload)
prod:
	docker build -t polynot-chat-agent .
	docker run -p 8000:8000 polynot-chat-agent

# Build only
build:
	docker-compose build

# Stop containers
stop:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Restart
restart:
	docker-compose restart

# Setup virtual environment
setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

# Install dependencies
install:
	.venv/bin/pip install -r requirements.txt

# Run tests
test:
	docker-compose exec polynot-chat-agent python -m pytest

# Run tests locally (without Docker)
test-local:
	source .venv/bin/activate && python -m pytest

# Run specific test - chat agent
test-chat:
	source .venv/bin/activate && python -m pytest tests/test_chat_agent.py -v

# Run specific test - feedback tool
test-feedback:
	source .venv/bin/activate && python -m pytest tests/test_feedback_tool.py -v

# Run specific test - level evaluator
test-level:
	source .venv/bin/activate && python -m pytest tests/test_level_evaluator.py -v

# Run API server locally
run-local:
	source .venv/bin/activate && python src/main.py

# Check code quality
lint:
	source .venv/bin/activate && python -m flake8 src/*.py --max-line-length=100 --ignore=E501,W503
