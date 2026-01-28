class Dnsgauge < Formula
  desc "DNS response testing tool (UDP + DoH) with live status and ETA"
  homepage "https://github.com/themorgantown/homebrew-dnsgauge"
  url "https://github.com/themorgantown/homebrew-dnsgauge/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "84cc389b3b039c04c272d98ef5eae950c1228439396cb2ddde10a7eabc171db4"  # Calculate after creating the tarball
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
