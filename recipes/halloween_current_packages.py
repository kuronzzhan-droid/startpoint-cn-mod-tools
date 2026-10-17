"""Diagnostic: repack current read-only packages, including post-221 source drift."""
from wf.view.safety import restrict_writes
restrict_writes()
from wf.view.character_pack import main
from wf.paths import path

if __name__ == "__main__":
    main(["1.4.220", "1.4.221", "--out", str(path("output", "halloween221"))])
