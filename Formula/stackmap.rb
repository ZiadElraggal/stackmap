class Stackmap < Formula
  desc "Architecture diagrams that generate themselves from infrastructure code"
  homepage "https://github.com/ziadelraggal/stackmap"
  license "MIT"
  head "https://github.com/ziadelraggal/stackmap.git", branch: "main"

  depends_on "python@3.12"

  def install
    python = Formula["python@3.12"].opt_bin/"python3.12"
    system python, "-m", "venv", libexec
    system libexec/"bin/pip", "install", "--upgrade", "pip"
    system libexec/"bin/pip", "install", buildpath
    bin.install_symlink libexec/"bin/stackmap"
  end

  test do
    output = shell_output("#{bin}/stackmap version")
    assert_match "stackmap", output
  end
end
