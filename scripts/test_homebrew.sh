#!/bin/bash

# Homebrew Testing Script for dnsgauge
# This script automates the process of testing the formula in a local tap.

set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}🍺 Starting Homebrew formula test...${NC}"

# 1. Create a local testing tap if it doesn't exist
if ! brew tap | grep -q "^local/test$"; then
  echo "📦 Creating local testing tap 'local/test'..."
  brew tap-new local/test
else
  echo "✅ Local testing tap 'local/test' already exists."
fi

# 2. Copy the formula file to the tap
echo "📝 Copying formula to tap..."
TAP_REPO=$(brew --repository local/test)
mkdir -p "$TAP_REPO/Formula"
cp Formula/dnsgauge.rb "$TAP_REPO/Formula/"

# 3. Test installation
echo "🚀 Testing installation..."
# Uninstall first if already installed from this tap to ensure a clean slate
brew uninstall local/test/dnsgauge 2>/dev/null || true
brew install local/test/dnsgauge

# 4. Run basic test defined in the formula
echo "🧪 Running formula tests..."
brew test local/test/dnsgauge

# 5. Audit for quality
echo "🔍 Auditing formula for quality..."
brew audit --formula local/test/dnsgauge

echo -e "${GREEN}🎉 Homebrew formula test completed successfully!${NC}"
