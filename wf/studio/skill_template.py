"""Shared HTTP/CLI editor for official skill template drafts."""
from __future__ import annotations

import copy

from .drafts import DraftError, DraftStore, new_change_id, now, status, validate
from .skill_template_compile import prepare, template_change
from .skill_template_inputs import current_source


class SkillTemplateEditor:
    def __init__(self, source, *, store=None, server_dir=None):
        self.source, self.store, self.server_dir = source, store or DraftStore(), server_dir

    def listing(self, q=""):
        from .skill_template_catalog import list_templates
        return list_templates(self.source, q)

    def detail(self, key):
        from .skill_template_catalog import public_detail, resolve_key
        try:
            resolve_key(self.source, {"key": key})
        except ValueError as exc:
            if str(exc).startswith("官方 action_skill 键不存在"):
                return None
            raise DraftError(str(exc)) from exc
        return public_detail(self.source, key)

    def preview(self, cid, request):
        return self._apply(cid, request, preview=True)

    def apply(self, cid, request):
        return self._apply(cid, request, preview=False)

    def _apply(self, cid, request, *, preview):
        try:
            with self.store._lock:
                request = copy.deepcopy(request)
                validate(request, "skillTemplateRequest")
                draft = self.store.load(cid)
                if draft:
                    validate(draft)
                    if draft["baseView"] != self.source.version or draft.get("subjectKind", "character") != "character":
                        raise DraftError("技能模板草稿基线或主体类型不匹配")
                effective = current_source(self.source, self.store, draft, server_dir=self.server_dir)
                compiled = prepare(effective, self.source, self.store, cid, request,
                                   previous=template_change(draft), server_dir=self.server_dir)
                if draft and draft["code"] != compiled["code"]:
                    raise DraftError("技能模板角色代码名与草稿不一致")
                checks = compiled["checks"]
                result = {"ok": True, "preview": preview, "characterId": cid, "code": compiled["code"],
                          "newKey": request["newKey"], "summary": compiled["summary"], "checks": checks,
                          "reservations": compiled["reservations"], "runtime": "未执行",
                          "buildable": not any(c.get("blocking") or c.get("level") == "error" for c in checks)}
                if preview:
                    return result
                change = {"id": new_change_id(), "kind": "skill_template", "title": "克隆官方技能模板",
                          "createdAt": now(), "target": {"character": cid},
                          "params": {"request": request, "inputs": compiled["inputs"],
                                     "reservations": compiled["reservations"]}, "files": [], "pending": [],
                          "checks": [{"level": "error" if c.get("blocking") else "warn" if c.get("status") in
                                      {"待验证", "未执行"} else "info", "code": c.get("rule", c.get("code")),
                                      "message": c["message"]} for c in checks]}
                stored = self.store.put_change(cid, compiled["code"], self.source.version, change)
                return {**result, "change": change, "changeset": stored, "status": status(stored)}
        except DraftError:
            raise
        except (ValueError, KeyError, OSError, TypeError, IndexError) as exc:
            raise DraftError(str(exc)) from exc
