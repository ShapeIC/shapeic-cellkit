#!/usr/bin/env bash

WORK_DIR=$(pwd)

PYTHON_VERSION="3.12.8"
VENV=".venv"
PACKAGE_DIR="$WORK_DIR/IHP/"

echo "Checking pyenv..."

if ! command -v pyenv >/dev/null 2>&1; then
    echo "ERROR: pyenv is not installed or is not available in PATH."
    exit 1
fi

echo "Installing Python $PYTHON_VERSION if necessary..."
pyenv install -s "$PYTHON_VERSION"

echo "Setting local Python version..."
pyenv local "$PYTHON_VERSION"

PYTHON_BIN="$(pyenv which python)"

echo "Using:"
"$PYTHON_BIN" --version

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV"
fi

echo "Upgrading pip..."
"$VENV/bin/python" -m pip install --upgrade pip

if [ -f requirements.txt ]; then
    echo "Installing requirements..."
    "$VENV/bin/python" -m pip install -r requirements.txt
fi

echo "Installing local package..."
"$VENV/bin/python" -m pip install "$PACKAGE_DIR"

echo
echo "Installation completed."
