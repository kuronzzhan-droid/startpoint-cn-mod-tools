"""Replace home-directory paths in text files under a folder.

usage: python scrub_home.py <folder>
"""
import os
import re
import sys

root = sys.argv[1]
home = os.path.expanduser("~")
literal = [
    (home.replace("\\", "\\\\"), "%USERPROFILE%"),  # JSON-escaped form
    (home, "%USERPROFILE%"),
    (home.replace("\\", "/"), "%USERPROFILE%"),
]
unix = re.compile(r"/(?:Users|home)/[A-Za-z0-9_]+/")
changed = 0
for dirpath, _, names in os.walk(root):
    for name in names:
        path = os.path.join(dirpath, name)
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        new = text
        for old, rep in literal:
            new = new.replace(old, rep)
        new = unix.sub("<HOME>/", new)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            changed += 1
print("files changed", changed)
