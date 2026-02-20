#!/bin/bash
# VPS Setup Script for Streamlined AI Scout

echo "🚀 Starting VPS Setup..."

# Update and install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-full unzip tar

# Create virtual environment with more robust check
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv || {
        echo "⚠️  Falling back to explicit python3.12-venv..."
        sudo apt-get install -y python3.12-venv
        python3 -m venv venv
    }
fi

# Activate venv and install requirements
echo "📥 Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright and its OS dependencies
echo "🌐 Installing Playwright and dependencies..."
playwright install chromium
playwright install-deps chromium

# Import cookies if cookies.txt exists
if [ -f "cookies.txt" ]; then
    echo "🍪 Importing cookies from cookies.txt..."
    python3 scripts/import_cookies.py cookies.txt x_cookies.json
fi

echo "✅ VPS Setup Complete!"
echo "👉 Run the app with: source venv/bin/activate && python run.py"
