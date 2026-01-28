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

# 2. Create a local tarball and update the formula to point to it
echo "📦 Creating local source tarball..."
tar -czf dnsgauge-test.tar.gz --exclude='.git' --exclude='dnsgauge-test.tar.gz' .
SHA=$(shasum -a 256 dnsgauge-test.tar.gz | awk '{print $1}')
LOCAL_PATH=$(pwd)/dnsgauge-test.tar.gz

echo "📝 Updating formula with local source and SHA..."
# Create a temporary formula for testing
cp Formula/dnsgauge.rb Formula/dnsgauge_test.rb
# Using line-specific replacement for the main URL and SHA (typically on lines 6 and 7)
sed -i '' "6s|url \".*\"|url \"file://$LOCAL_PATH\"|" Formula/dnsgauge_test.rb
sed -i '' "7s|sha256 \".*\"|sha256 \"$SHA\"|" Formula/dnsgauge_test.rb
# Add explicit version since it can't be inferred from local file URL
sed -i '' "/url \"file:.*\"/a \\
  version \"1.0.0\"
" Formula/dnsgauge_test.rb

echo "📝 Copying formula to tap..."
TAP_REPO=$(brew --repository local/test)
mkdir -p "$TAP_REPO/Formula"
cp Formula/dnsgauge_test.rb "$TAP_REPO/Formula/dnsgauge.rb"
rm Formula/dnsgauge_test.rb # Cleanup temp file

# 3. Test installation
echo "🚀 Testing installation..."
# Uninstall first if already installed (from any tap) to ensure a clean slate
brew uninstall dnsgauge 2>/dev/null || true
brew install local/test/dnsgauge

# 4. Run basic test defined in the formula
echo "🧪 Running formula tests..."
brew test local/test/dnsgauge

# 5. Audit for quality
echo "🔍 Auditing formula for quality..."
brew audit --formula local/test/dnsgauge

# 6. Run the actual tool
echo "🧪 Running functional tests..."
dnsgauge --version
dnsgauge --help > /dev/null
# Run a quick test with 1 domain to ensure network/dns works
dnsgauge --domains 1 --timeout 5.0
dnsgauge --comprehensive

# Cleanup
rm dnsgauge-test.tar.gz

echo -e "${GREEN}🎉 Homebrew formula test completed successfully!${NC}"
