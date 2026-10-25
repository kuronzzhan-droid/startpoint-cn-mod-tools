"""Expose the selected weapon author's provides declaration without runtime claims."""
import hashlib

from wf.boss.weapon_templates import INVOKE_CAPABILITIES, invoke_declaration
from wf.caps.profiles import read_client, resolve_client
from wf.rules.catalog import result


def capabilities(editor):
    summary = {"supported": False,
               "capabilities": [{"id": cid, "provided": None} for cid in sorted(INVOKE_CAPABILITIES)],
               "patch20": {"linked": None, "recorded": None, "supported": False}}
    evidence = {"status": "unavailable", "sha256": None, "clientProfile": editor.client_profile}
    try:
        if editor.provides is None and editor.client_profile is None:
            raise ValueError("629 template requires explicit target provides or client_profile")
        path, selected = resolve_client(provides=editor.provides, client_profile=editor.client_profile)
        document = read_client(path)
        summary = invoke_declaration(document)
        evidence = {"status": "available", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "clientProfile": selected}
        checks = [result("weapon.invoke-provides", "满足" if summary["supported"] else "问题",
                         "629 模板所需 provides 声明已齐全" if summary["supported"]
                         else "缺少 629、424 能力声明或关联的已记录补丁 20",
                         blocking=not summary["supported"])]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        checks = [result("weapon.invoke-provides", "未执行", str(exc), blocking=True)]
    return {"invoke629": {**summary, "evidence": evidence, "checks": checks},
            "scope": "provides-declaration", "runtime": "未执行",
            "note": "只表示当前 provides 声明；候选生成仍检查实际 SWF 分支和输入哈希，不代表装机实测。"}
