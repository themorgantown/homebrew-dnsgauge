#!/bin/bash

# Script to update Homebrew Formula resource blocks based on Python dependencies
# This uses the 'brew update-python-resources' command.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FORMULA="Formula/dnsgauge.rb"

echo -e "${GREEN}🔄 Updating Homebrew resources for $FORMULA...${NC}"

# Check if brew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Please install it first."
    exit 1
fi

# Ensure formula exists
if [ ! -f "$FORMULA" ]; then
    echo "❌ Formula not found at $FORMULA"
    exit 1
fi

# We need the formula to be in a tap for 'update-python-resources' to work
# We'll use the 'local/test' tap we created earlier
if ! brew tap | grep -q "^local/test$"; then
    echo -e "${YELLOW}📦 Creating temporary local tap for update...${NC}"
    brew tap-new local/test
fi

TAP_FORMULA=$(brew --repository local/test)/Formula/dnsgauge.rb
cp "$FORMULA" "$TAP_FORMULA"

echo "📡 Fetching latest PyPI resources..."
# We explicitly mention httpx and dnspython as they are the main dependencies
# The --extra-packages flag ensures they and their sub-dependencies are captured.
brew update-python-resources local/test/dnsgauge --extra-packages httpx,dnspython

# Copy back the updated formula
cp "$TAP_FORMULA" "$FORMULA"

echo -e "${GREEN}✅ Resources updated successfully in $FORMULA${NC}"
echo "📝 Review the changes and commit them to your repository."
