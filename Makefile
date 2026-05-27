SERVICE ?= change-quality-agent
HOST ?= 127.0.0.1
PORT ?= 8000
LOG_LINES ?= 200
LOG_SINCE ?= 1 hour ago
JOURNAL_VACUUM_SIZE ?= 1G
JOURNAL_VACUUM_TIME ?= 14d

.PHONY: help test dev run logs logs-follow logs-since logs-disk-usage logs-vacuum-size logs-vacuum-time service-status service-restart

help:
	@echo "Change Quality Agent targets"
	@echo ""
	@echo "Local development:"
	@echo "  make test              Run the pytest suite"
	@echo "  make dev               Run FastAPI dev server with reload"
	@echo "  make run               Run FastAPI production-style server"
	@echo ""
	@echo "systemd/journald logs (override SERVICE=<unit>):"
	@echo "  make logs              Show recent logs; LOG_LINES=$(LOG_LINES)"
	@echo "  make logs-follow       Follow service logs"
	@echo "  make logs-since        Show logs since LOG_SINCE=\"$(LOG_SINCE)\""
	@echo "  make logs-disk-usage   Show journal disk usage"
	@echo "  make logs-vacuum-size  Vacuum journal to JOURNAL_VACUUM_SIZE=$(JOURNAL_VACUUM_SIZE)"
	@echo "  make logs-vacuum-time  Vacuum journal to JOURNAL_VACUUM_TIME=$(JOURNAL_VACUUM_TIME)"
	@echo ""
	@echo "systemd service:"
	@echo "  make service-status    Show systemd service status"
	@echo "  make service-restart   Restart the systemd service"


test:
	uv run pytest


dev:
	LOG_LEVEL=$${LOG_LEVEL:-INFO} ACCESS_LOG_ENABLED=$${ACCESS_LOG_ENABLED:-true} AUTH_DEV_MODE=$${AUTH_DEV_MODE:-true} uv run fastapi dev --host $(HOST) --port $(PORT)


run:
	LOG_LEVEL=$${LOG_LEVEL:-INFO} ACCESS_LOG_ENABLED=$${ACCESS_LOG_ENABLED:-true} uv run fastapi run --host $(HOST) --port $(PORT)


logs:
	journalctl -u $(SERVICE) -n $(LOG_LINES) --no-pager


logs-follow:
	journalctl -u $(SERVICE) -f


logs-since:
	journalctl -u $(SERVICE) --since "$(LOG_SINCE)" --no-pager


logs-disk-usage:
	journalctl --disk-usage


logs-vacuum-size:
	sudo journalctl --vacuum-size=$(JOURNAL_VACUUM_SIZE)


logs-vacuum-time:
	sudo journalctl --vacuum-time=$(JOURNAL_VACUUM_TIME)


service-status:
	systemctl status $(SERVICE) --no-pager


service-restart:
	sudo systemctl restart $(SERVICE)
