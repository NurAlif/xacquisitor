#!/bin/bash
# Setup Playwright for macOS and Linux

echo "🚀 Setting up Playwright..."

# Check if we are in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: You are not in a virtual environment. It is recommended to use one."
    read -p "Do you want to continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing playwright python package..."
pip install playwright

echo "🌐 Downloading Chromium browser..."
playwright install chromium

echo "✅ Playwright setup complete!"
