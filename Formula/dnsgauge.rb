class Dnsgauge < Formula
  desc "DNS response testing tool (UDP + DoH) with live status and ETA"
  homepage "https://github.com/themorgantown/DNS-Latency-CLI"
  url "https://github.com/themorgantown/DNS-Latency-CLI/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "3b0e0d96f73d6b3a5e2f9e4b847350ff9a1550710a0069b073dd09f1fd04ef05"  # Calculate after creating the tarball
  license "MIT"

  depends_on "python@3.11"

  def install
    # Install the package into the prefix
    # We use --prefix=#{prefix} to ensure it goes into the Homebrew cell
    system "python3", "-m", "pip", "install", "--no-deps", "--prefix=#{prefix}", "."

    # The executable 'dnstest' will be created in bin/ by pip due to pyproject.toml
  end

  def caveats
    <<~EOS
      You may need to add your Python bin directory to your PATH:
        export PATH="/opt/homebrew/lib/python3.11/bin:$PATH"  # Apple Silicon
        export PATH="/usr/local/lib/python3.11/bin:$PATH"   # Intel
    EOS
  end

  test do
    system "dnsgauge", "--help"
  end
end
