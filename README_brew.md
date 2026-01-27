# Homebrew Distribution Guide

This guide explains how to install `dns-latency-cli` using Homebrew and how maintains can update the formula.

## 📦 User Installation

### Method 1: Installing from a Local Formula (Development)
If you have cloned this repository, you can install the tool directly from the source directory:

```bash
brew install --build-from-source ./Formula/dns-latency-cli.rb
```

### Method 2: Installing from a Custom Tap (Recommended for Users)
If you publish this repository as a Homebrew Tap, users can install it via:

```bash
brew tap themorgantown/dns-latency-cli
brew install dns-latency-cli
```
*(Note: requires the repo to be set up as a Tap)*

---

## 🛠️ Maintainer Guide: Releasing a New Version

To update the Homebrew formula for a new version of `dns-latency-cli`:

### 1. Create a GitHub Release
1. Go to the **Releases** section of the GitHub repository.
2. Draft a new release (e.g., `v1.0.1`).
3. Publish the release.

### 2. Get the SHA256 Checksum
The formula requires the SHA256 hash of the source code tarball to verify integrity.

**Automated Way:**
Check the **Actions** tab in GitHub after publishing a release. The `Calculate Release SHA256` workflow will run and output the hash in its logs.

**Manual Way:**
```bash
# Download the tarball (replace v1.0.0 with your version)
wget https://github.com/themorgantown/DNS-Latency-CLI/archive/refs/tags/v1.0.0.tar.gz
# Calculate hash
shasum -a 256 v1.0.0.tar.gz
```

### 3. Update the Formula
Edit `Formula/dns-latency-cli.rb`:

- Update the `url` to the new version tag.
- Update the `sha256` with the hash you calculated.

```ruby
  url "https://github.com/themorgantown/DNS-Latency-CLI/archive/refs/tags/v1.0.1.tar.gz"
  sha256 "NEW_HASH_HERE"
```

### 4. Verify the Formula
Test that the new formula works locally:
```bash
brew audit --new-formula Formula/dns-latency-cli.rb
brew install --build-from-source ./Formula/dns-latency-cli.rb
dnstest --help
```
