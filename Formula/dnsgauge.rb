class Dnsgauge < Formula
  desc "DNS response testing tool (UDP + DoH) with live status and ETA"
  homepage "https://github.com/themorgantown/homebrew-dnsgauge"
  url "https://github.com/themorgantown/homebrew-dnsgauge/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "5bba0b8467ed323d2661bf2ef1cf2e29c56c6ab2b7cb79fe95efa03f9f8c5da4"  # Calculate after creating the tarball
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
