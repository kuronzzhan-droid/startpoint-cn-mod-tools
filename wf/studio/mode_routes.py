"""Mode workshop HTTP surface, inheriting the existing delivery guards."""
import re
from types import SimpleNamespace

from wf.view.safety import local_output
from .deliver_routes import DeliverRoutes, DELIVERIES
from .drafts import DraftError, sha256
from .freshness import freshness
from .mode_store import MODES, ModeStore, ViewInputs
from .mode_checks import delivery_checks, saved_preview


class ModeDeliveries(DeliverRoutes):
    kind = "boss"
    name_pattern = re.compile(r"^(five|rogue)-[0-9.]+-to-[0-9.]+-[0-9]{8}-[0-9]{6}$")

    def __init__(self, owner, app, server_dir, default_provides):
        self.owner = owner
        super().__init__(app, server_dir, DELIVERIES / "modes", default_provides)

    def output_identity(self, cid):
        self.app.ops.store.directory(cid)
        return cid

    def compile_delivery(self, cid, **kwargs):
        from wf.caps.profiles import resolve_client
        from .deliver_bridge import deliver_compiled, open_baseline, _step
        from .delivery_safety import resolve_apks
        draft = self.app.ops.store.load(cid)
        if not draft or draft["baseView"] != self.app.source.version:
            raise DraftError("请先在当前视图预览并保存模式草稿")
        if kwargs["from_version"] != self.app.source.version:
            raise DraftError("来源版本必须是当前视图链尾")
        _step(kwargs.get("progress"), kwargs.get("cancel"), "media")
        result, inputs = self.owner.compute(cid, draft["payload"])
        if not result["canGenerate"]:
            raise DraftError("；".join(result["blockers"]))
        if inputs.inputs != draft["inputs"]:
            raise DraftError("草稿读取输入已变化，请重新预览并保存")
        if result.get("outputSha256") != draft["preview"].get("outputSha256"):
            raise DraftError("构建结果与已保存预览不一致（规格、规则或代码已变化），请重新预览并保存")
        files = result.pop("files")
        checks = delivery_checks(cid, result)
        compiled = ({("common", logical): raw for logical, raw in files.items()}, {}, {}, [], checks)
        options = self.baseline_options()
        if "baseline_view" not in options:
            raise DraftError("模式交付要求经过完整 manifest 核验的当前视图")
        baseline = open_baseline(kwargs["from_version"], kwargs["to_version"], **options)
        provides, selected = resolve_client(kwargs.get("provides"), kwargs.get("client_profile"))
        apks = resolve_apks(selected, kwargs.get("apk"))
        out = local_output(kwargs["out"])
        if out.exists() and any(out.iterdir()):
            raise DraftError("交付输出目录必须为空")
        inputs.verify()
        return deliver_compiled(draft, compiled, source=self.app.source, baseline=baseline,
            from_version=kwargs["from_version"], to_version=kwargs["to_version"], out=out,
            provides=provides, selected_profile=selected, apks=apks,
            progress=kwargs.get("progress"), cancel=kwargs.get("cancel"), **options)

    def routes(self):
        return [(verb, re.compile(pattern.pattern.replace("/api/", "/api/modes/")
                                 .replace(r"(?P<cid>\d+)", r"(?P<cid>five|rogue)")), handler)
                for verb, pattern, handler in super().routes()]


class ModeRoutes:
    def __init__(self, app, server_dir=None, default_provides=None):
        self.app = app
        self.store = ModeStore(app.ops.store.root / "modes")
        proxy = SimpleNamespace(source=app.source, ops=SimpleNamespace(store=self.store),
                                screenshots=getattr(app, "screenshots", None))
        self.deliveries = ModeDeliveries(self, proxy, server_dir, default_provides)

    def compute(self, mode, payload):
        from . import mode_five, mode_rogue
        if mode not in MODES:
            raise DraftError("未知模式")
        inputs = ViewInputs(self.app.source)
        if mode == "five":
            result = mode_five.preview(inputs.read, payload)
        else:
            if not isinstance(payload, dict) or set(payload) != {"seed"}:
                raise DraftError("深渊请求只接受 seed")
            result = mode_rogue.preview(inputs.read, payload["seed"])
        inputs.verify()
        fresh = freshness(self.app.source)
        if fresh.get("error") or fresh["latest"] != self.app.source.version:
            result["canGenerate"] = False
            result["blockers"].append("当前视图不是已确认的新鲜链尾：" + (fresh.get("error") or str(fresh)))
        result["freshness"] = fresh
        result["version"] = self.app.source.version
        result["runtime"] = "未执行"
        result["outputSha256"] = {logical: sha256(raw) for logical, raw in result["files"].items()}
        return result, inputs

    def read(self, query, mode):
        from . import mode_five, mode_rogue
        from .server import json_response
        draft = self.store.load(mode)
        result = {"mode": mode, "version": self.app.source.version, "draft": draft}
        if mode == "five":
            spec = mode_five.document()
            result["spec"] = spec
            result["payload"] = draft["payload"] if draft else spec
            try:
                preview, _ = self.compute(mode, result["payload"])
            except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
                preview = {"ok": False, "canGenerate": False, "blockers": [str(exc)],
                           "diff": mode_five.differences(spec, result["payload"])}
            preview.pop("files", None)
            result["preview"] = preview
        else:
            inputs = ViewInputs(self.app.source)
            current = mode_rogue.current(inputs.read)
            current.pop("_digest")
            inputs.verify()
            result["current"] = current
            result["payload"] = draft["payload"] if draft else {"seed": 0}
            if draft:
                result["preview"] = saved_preview(self.app.source, draft)
        return json_response(result)

    def edit(self, query, body, mode, action):
        from .server import json_response
        if set(body) - {"payload", "revision"} or "payload" not in body:
            raise DraftError("请求只接受 payload 与 revision")
        try:
            result, inputs = self.compute(mode, body["payload"])
            result.pop("files", None)
            if action == "save":
                if not result["ok"]:
                    raise DraftError("预览存在构建错误，未保存")
                revision = body.get("revision")
                if type(revision) is not int or revision < 0:
                    raise DraftError("保存需要非负整数 revision")
                result["draft"] = self.store.save(mode, self.app.source.version, body["payload"],
                                                  inputs.inputs, result.copy(), revision)
            return json_response(result)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            raise DraftError(str(exc)) from exc

    def routes(self):
        return [*self.deliveries.routes(),
                ("GET", re.compile(r"^/api/modes/(?P<mode>five|rogue)$"), self.read),
                ("POST", re.compile(r"^/api/modes/(?P<mode>five|rogue)/(?P<action>preview|save)$"), self.edit)]
