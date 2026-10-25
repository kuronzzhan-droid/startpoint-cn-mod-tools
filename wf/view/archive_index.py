"""Find named ZIP inputs within explicit roots, without following directory links."""
from pathlib import Path
import os


def index_zip_names(directories, wanted):
    found, seen = {}, set()
    for directory in directories:
        root = Path(directory)
        if not root.is_dir():
            continue
        for current, children, names in os.walk(root, followlinks=False):
            location = Path(current).resolve()
            if location in seen:
                children[:] = []
                continue
            seen.add(location)
            children[:] = sorted(name for name in children
                                 if name not in {".git", "node_modules", "__pycache__"}
                                 and not (Path(current) / name).is_symlink()
                                 and not getattr(os.path, "isjunction", lambda _: False)(Path(current) / name))
            for name in sorted(set(names) & wanted):
                candidate = (Path(current) / name).resolve()
                if candidate.is_file():
                    found.setdefault(name, []).append(candidate)
    return found
