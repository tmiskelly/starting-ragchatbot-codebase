#!/bin/bash

# Auto-format script for the RAG chatbot codebase
# This script automatically formats code using black and isort

set -e  # Exit on any error

echo "🔧 Auto-formatting code..."

# Change to the project root directory
cd "$(dirname "$0")/.."

echo "📦 Installing/updating dependencies..."
uv sync

echo "🖤 Running Black formatter..."
uv run black backend/

echo "📋 Running isort import sorter..."
uv run isort backend/

echo "✅ Code formatting complete!"