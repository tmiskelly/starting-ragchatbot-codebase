#!/bin/bash

# Quality check script for the RAG chatbot codebase
# This script runs all code quality tools

set -e  # Exit on any error

echo "🔍 Running code quality checks..."

# Change to the project root directory
cd "$(dirname "$0")/.."

echo "📦 Installing/updating dependencies..."
uv sync

echo "🖤 Running Black formatter..."
uv run black backend/ --check --diff

echo "📋 Running isort import sorter..."
uv run isort backend/ --check-only --diff

echo "🔎 Running flake8 linter..."
uv run flake8 backend/

echo "🏷️  Running mypy type checker..."
uv run mypy backend/

echo "✅ All quality checks passed!"