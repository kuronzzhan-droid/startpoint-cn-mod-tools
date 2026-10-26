"""Find an author-relocated resource while keeping repository code portable."""
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]


def asset_path(relative: str | Path) -> Path:
    """Prefer the private mirror; never accept an external or escaping path."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Expected a repository-relative resource: {relative}")
    if relative == Path("."):
        return REPOSITORY
    for candidate in (REPOSITORY / "private-assets" / relative, REPOSITORY / relative):
        if not candidate.resolve().is_relative_to(REPOSITORY):
            raise ValueError(f"Resource leaves the repository: {relative}")
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Resource is not available locally: {relative}")
