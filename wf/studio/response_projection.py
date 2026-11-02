"""Opt-in presentation projections; full evidence remains the default API."""


def wiki_card(value):
    card = value["card"]
    fields = ("id", "name", "title", "profile", "element", "rarity", "type", "role",
              "warnings", "origin")
    result = {key: card[key] for key in fields if key in card}
    for key, allowed in {
        "portraits": ("url", "label"),
        "abilities": ("name", "description", "translation"),
        "skills": ("label", "name", "description", "translation", "gauge"),
    }.items():
        result[key] = [{name: item[name] for name in allowed if name in item}
                       for item in card.get(key, [])]
    result["leader"] = {key: card["leader"][key] for key in ("name", "description", "translation")
                        if key in card.get("leader", {})}
    result["stats"] = {key: card["stats"][key] for key in ("levels", "note")
                       if key in card.get("stats", {})}
    return {**value, "card": result}
