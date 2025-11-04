#!/usr/bin/env bash
# Render build script
set -o errexit

# Install poetry
pip install poetry

# Install dependencies (no dev dependencies)
poetry install --no-dev

# Note: Migrations would go here if using Alembic
# poetry run alembic upgrade head
