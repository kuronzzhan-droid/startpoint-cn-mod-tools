"""Human-readable SLv formulas, following the client's Environment resolver."""
from __future__ import annotations


def number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") if value else "0"


def scalar(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, list) and all(isinstance(t, dict) for t in value):
        if all(set(t) <= {"min", "max"} and t.get("min", 0) == t.get("max", 0) for t in value):
            return sum(t.get("min", 0) for t in value)
    return None


class Formula:
    def __init__(self):
        self.variables = {}

    def variable(self, key):
        return self.variables.setdefault(str(key), f"成长变量{len(self.variables) + 1}")

    def value(self, value, unit="", *, permanent=False) -> str:
        factor = 100 if unit == "%" else 1 / 60 if unit == "秒" else 1

        def val(v):
            return number(float(v) * factor)

        def pair(lo, hi):
            return val(lo) if lo == hi else f"{val(lo)}→{val(hi)}"

        constant = scalar(value)
        if constant is not None:
            if permanent and unit == "秒" and constant >= 99999:
                return "持续至战斗结束"
            return val(constant) + unit
        if not isinstance(value, list) or not all(isinstance(t, dict) for t in value):
            return "动态数值（依赖战斗状态）"
        terms = []
        for term in value:
            parts = []
            lo, hi = term.get("min", 0), term.get("max", term.get("min", 0))
            if lo or hi or not term:
                parts.append(pair(lo, hi))
            for i in range(1, 7):
                prefix = "alv" if i == 1 else f"alv{i}"
                if f"{prefix}_min" in term or f"{prefix}_max" in term:
                    parts.append(f"能力{i}成长({pair(term.get(prefix + '_min', 0), term.get(prefix + '_max', 0))})")
            for growth in term.get("vlv", []):
                low, high = growth.get("min", 0), growth.get("max", 0)
                parts.append(f"({val(low)} + {val(high - low)} × {self.variable(growth.get('vid'))})")
            expression = " + ".join(parts) or "0"
            if term.get("mul") is not None:
                expression = f"({expression}) × {self.variable(term['mul'])}"
            terms.append(expression)
        return " + ".join(terms) + unit


ELEMENTS = {1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗", 254: "全部属性", 255: "自身属性"}


def field(label, value):
    return {"label": label, "value": str(value)}
