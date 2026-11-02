"""Find named ZIP inputs within explicit roots, without following directory links."""
from pathlib import Path
import os


def index_zip_names(directories, wanted):
    found, seen = {}, set()
    for directory in directories:
        root = Path(directory)
        if not root.is_dir():
            continue
        root = root.resolve()
        pending = [str(root)]
        while pending:
            current = pending.pop()
            # Roots are canonical and child links are excluded below. Resolving
            # every directory repeats expensive Windows final-path syscalls.
            location = os.path.normcase(current)
            if location in seen:
                continue
            seen.add(location)
            try:
                with os.scandir(current) as entries:
                    children, matches = [], []
                    for entry in entries:
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                        except OSError:
                            is_dir = False  # os.walk still considers sibling entries.
                        if is_dir:
                            try:
                                linked = entry.is_symlink()
                            except OSError:
                                linked = False
                            if entry.name in {".git", "node_modules", "__pycache__"} or linked:
                                continue
                            junction = getattr(entry, "is_junction", None)
                            try:
                                is_junction = (junction() if junction else
                                    getattr(os.path, "isjunction", lambda _: False)(entry.path))
                            except OSError:
                                is_junction = False
                            if is_junction:
                                continue
                            children.append(entry.path)
                        elif entry.name in wanted:
                            matches.append(entry.name)
            except OSError:
                continue  # Match os.walk's existing inaccessible-directory behavior.
            pending.extend(sorted(children, reverse=True))
            for name in sorted(matches):
                candidate = (Path(current) / name).resolve()
                if candidate.is_file():
                    found.setdefault(name, []).append(candidate)
    return found
