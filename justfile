# Default: list available commands
default:
    @just --list

# Uv sync with dev dependencies
sync-dev:
    uv sync --group dev

# Run pytest
test *ARGS:
    uv run pytest {{ ARGS }}

# Linting
lint *ARGS:
    uv run ruff check . {{ ARGS }}

# Formatting
format:
    uv run ruff format .

# Remove all .pyc files and __pycache__ directories
clean-pyc:
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete

# Remove build/test artifacts
clean: clean-pyc
    rm -rf .pytest_cache .coverage htmlcov build dist *.egg-info