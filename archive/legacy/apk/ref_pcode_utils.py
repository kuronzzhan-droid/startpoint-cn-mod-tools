"""Locate FFDec method evidence while preserving original P-code line numbers."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HEADER = re.compile(r'\b(?:public|private|protected|internal)\s+(?:static\s+)?function\s+(?:(get|set)\s+)?([\w$§]+)\s*\(')


def evidence_path(relative):
    for directory in ('out/evidence_pcode/scripts', 'pcode/scripts'):
        path = ROOT / directory / Path(relative).with_suffix('.pcode')
        if path.exists():
            return path
    raise FileNotFoundError(relative)


def method_evidence(relative, name):
    path = evidence_path(relative)
    text = path.read_text(encoding='utf-8-sig')
    headers = list(HEADER.finditer(text))
    for index, match in enumerate(headers):
        current = ((match[1] + ' ') if match[1] else '') + match[2]
        if current == name:
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            return path, text.count('\n', 0, match.start()) + 1, text[match.start():end]
    raise ValueError(f'{relative}: no P-code method {name}')


def compact(relative, name):
    path, line, text = method_evidence(relative, name)
    return '\n'.join(f'{line + i}: {v.strip()}' for i, v in enumerate(text.splitlines()))
