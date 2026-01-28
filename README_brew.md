# 🍺 Homebrew it Yourself: Distributing DNSgauge

Ever wished you could just share your tool with a simple `brew install`? This guide walking you through how we've packaged **DNSgauge** into a fully functional Homebrew formula.

## What is a Homebrew Tap?

A Homebrew **tap** is simply a GitHub repository that contains custom Homebrew formulae. It allows you to distribute your tools without needing to submit them to the official Homebrew core repository. This is perfect for:
- ⚡ **Rapid Iterations**: Push updates instantly.
- 🛠️ **Custom Utilities**: Share specialized tools like this DNS benchmarker.
- 🚀 **Professional UX**: Users just run `brew install`.

---

## 📦 For Users: Installation

To install **DNSgauge** via our tap:

```bash
# 1. Add the tap
brew tap themorgantown/dnsgauge

# 2. Install the tool
brew install dnsgauge
```

Once installed, you can simply run:
```bash
dnsgauge --help
```

---

## 🛠️ For Maintainers: Releasing v1.0.0+

Turning this Python tool into a "brewable" package involves two repositories and a bit of Ruby.

### Step 1: Finalize the Release
Ensure your code is ready and the version is bumped in `pyproject.toml`.

```bash
# Tag the version
git tag v1.0.0
git push origin v1.0.0
```

### Step 2: Update the Formula
Homebrew needs a stable tarball and a matching SHA256 checksum to verify the download.

1. **Calculate the SHA256:**
   You can find this in your GitHub Actions logs after pushing a tag, or do it manually:
   ```bash
   curl -L -o v1.0.0.tar.gz https://github.com/themorgantown/homebrew-dnsgauge/archive/refs/tags/v1.0.0.tar.gz
   shasum -a 256 v1.0.0.tar.gz
   ```

2. **Update `Formula/dnsgauge.rb`:**
   Update the `url` and `sha256` fields with the new values.

### Step 3: Test Locally (The Tap Way)
Modern Homebrew (4.0+) requires formulae to be in a tap to be audited or installed.

```bash
# 1. Create a local testing tap
brew tap-new local/test

# 2. Copy the formula file
cp Formula/dnsgauge.rb $(brew --repository local/test)/Formula/

# 3. Test installation
brew install local/test/dnsgauge

# 4. Audit for quality
brew audit --formula local/test/dnsgauge
```

---

## 💡 Pro-Tips for Maintainers

- **Naming Matters**: Your tap repository must be named `homebrew-dnsgauge`. Homebrew looks for the `homebrew-` prefix automatically.
- **Keep it Clean**: Ensure `dnsgauge.py` is executable and includes a proper shebang (`#!/usr/bin/env python3`).
- **Automation**: We've included a GitHub Action in `.github/workflows/homebrew-helper.yml` that handles the checksum calculation for you every time you publish a release!

---

### Credits & Inspiration
Inspired by the "Brew It Yourself" guide by Evren Tan. We've taken those principles to make **DNSgauge** a first-class citizen in the Homebrew ecosystem.
