class DnsLatencyCli < Formula
  desc "DNS response tester (UDP + DoH) with live status and ETA"
  homepage "https://github.com/themorgantown/DNS-Latency-CLI"
  url "https://github.com/themorgantown/DNS-Latency-CLI/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "YOUR_SHA256_HASH"  # Calculate after creating the tarball
  license "MIT"

  depends_on "python@3.11"

  def install
    # Install the package
    system "python3", "-m", "pip", "install", "--no-deps", "--prefix=", "."

    # Make the CLI accessible
    bin.install_symlink "dnstest" => "dnstest"
  end

  def caveats
    <<~EOS
      You may need to add your Python bin directory to your PATH:
        export PATH="/opt/homebrew/lib/python3.11/bin:$PATH"  # Apple Silicon
        export PATH="/usr/local/lib/python3.11/bin:$PATH"   # Intel
    EOS
  end

  test do
    system "dnstest", "--help"
  end
end
