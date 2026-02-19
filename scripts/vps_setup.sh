#!/bin/bash
# VPS Setup Script for Streamlined AI Scout

echo "🚀 Starting VPS Setup..."

# Update and install system dependencies for Playwright
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    unzip \
    tar

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install requirements
echo "📥 Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium

# Import cookies if cookies.txt exists
if [ -f "cookies.txt" ]; then
    echo "🍪 Importing cookies from cookies.txt..."
    python3 scripts/import_cookies.py cookies.txt x_cookies.json
fi

echo "✅ VPS Setup Complete!"
echo "👉 Run the app with: source venv/bin/activate && python run.py"
