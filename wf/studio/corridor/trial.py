"""Apply releases to the isolated trial server (proto-server/trial, ports 18011/18013) only.

The trial server reads ``assets/rogue_corridor_v1.json`` (fixed path) and the data files from the
config's ``data_dir``; the v3f overlay must sit next to the config. It has no manifest/content
version support, so "apply" is: stage the immutable release under
``assets/rogue-content/<ver12>/`` → offline preflight with the server's own module → stop via
trialctl → swap the two files in ``assets/`` (``data_dir`` mapped to the staged copy) → start via
trialctl → health check from the startup log → automatic restore on failure.

Runs in progress are not version-pinned by the server: applying is refused when an open run
would break (deleted relic/event it holds, changed pending event options, map quests removed,
rules_revision change) and needs an explicit acknowledgement otherwise.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import encounters as enc, jsonio, release
from .layout import MANIFEST_FILE, RUNTIME_FILES, TRIAL_PORTS, CorridorConfig
from .store import ConflictError, CorridorStore, StoreError
from .workspace import now

PREFLIGHT = Path(__file__).with_name("preflight.cjs")
CONTENT_DIR = "rogue-content"
KEEP_DEPLOYED = 6
KEEP_BACKUPS = 20
LOADED = re.compile(r"\[ROGUE-CORRIDOR\] v1 config loaded: .*?chars=(\d+) weapons=(\d+) relics=(\d+) events=(\d+)")
INERT = "[ROGUE-CORRIDOR] config/data unavailable"
_apply_lock = threading.Lock()


class TrialError(StoreError):
    pass


class Trial:
    def __init__(self, cfg: CorridorConfig, store: CorridorStore, forbidden_roots=(), node: str | None = None,
                 runner=None):
        self.cfg = cfg
        self.store = store
        self.forbidden = [Path(p) for p in forbidden_roots if p]
        self.node = node or shutil.which("node") or "node"
        self.runner = runner or self._run_trialctl

    # -- paths --------------------------------------------------------------
    @property
    def tree(self) -> Path:
        return self.cfg.trial_tree

    @property
    def assets(self) -> Path:
        return self.tree / "assets"

    @property
    def content_root(self) -> Path:
        return self.assets / CONTENT_DIR

    @property
    def state_path(self) -> Path:
        return self.store.trial_dir / "state.json"

    # -- guard ---------------------------------------------------------------
    def env_ports(self):
        values = {}
        env = self.tree / ".env"
        if not env.is_file():
            return None
        for line in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            for key in ("CN_LISTEN_PORT", "SESSION_PORT"):
                if line.startswith(key + "="):
                    try:
                        values[key] = int(line.split("=", 1)[1].split("#")[0].strip().strip('"'))
                    except ValueError:
                        pass
        if len(values) != 2:
            return None
        return values["CN_LISTEN_PORT"], values["SESSION_PORT"]

    def guard(self) -> list[str]:
        problems = []
        if not self.cfg.trialctl.is_file():
            problems.append("找不到 trialctl.py（proto_server/tools）")
        if not self.tree.is_dir():
            return problems + ["找不到隔离试验服副本（proto_server/trial/tree）"]
        trial_root = (self.cfg.proto_server / "trial").resolve()
        tree = self.tree.resolve()
        if not tree.is_relative_to(trial_root):
            problems.append("试验服副本不在 proto_server/trial 之下（疑似链接到别处）")
        if not self.assets.resolve().is_relative_to(tree):
            problems.append("试验服 assets 目录链接到了副本之外，拒绝写入")
        ports = self.env_ports()
        if ports != TRIAL_PORTS:
            problems.append(f"试验服端口是 {ports}，只允许 {TRIAL_PORTS[0]}/{TRIAL_PORTS[1]} 的隔离副本")
        for root in self.forbidden:
            try:
                r = root.resolve()
            except OSError:
                continue
            if tree == r or tree.is_relative_to(r) or r.is_relative_to(tree):
                problems.append("目标与 profile 里登记的真实服务端目录重叠，拒绝（只允许隔离试验服）")
        config = self.assets / "rogue_corridor_v1.json"
        if not config.is_file():
            problems.append("试验服还没安装回廊配置（先运行 trialctl patch）")
        if not (self.tree / "out" / "lib" / "rogue-corridor.js").is_file():
            problems.append("试验服还没安装回廊模块（out/lib/rogue-corridor.js）")
        return problems

    # -- trialctl -------------------------------------------------------------
    def _run_trialctl(self, *args, timeout=180) -> tuple[int, str]:
        # Server children must never inherit a pipe we read: capture through temp files (as trialctl does).
        with tempfile.TemporaryFile() as out:
            proc = subprocess.run([sys.executable, str(self.cfg.trialctl), *args], cwd=str(self.cfg.proto_server),
                                  stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, timeout=timeout,
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            out.seek(0)
            return proc.returncode, out.read().decode("utf-8", "replace")

    def status(self) -> dict:
        problems = self.guard()
        info = {"guard": problems, "ports": self.env_ports(), "running": None, "listeners": None, "recorded": None}
        if not self.cfg.trialctl.is_file():
            return info
        code, text = self.runner("status", timeout=60)
        info["trialctl_exit"] = code
        info["trialctl_output"] = text.strip()[-2000:]
        listeners, recorded = None, None
        for line in text.splitlines():
            if line.startswith("env ports:") and "listeners:" in line:
                try:
                    listeners = ast.literal_eval(line.split("listeners:", 1)[1].strip())
                except (ValueError, SyntaxError):
                    pass
        if "recorded:" in text:
            tail = text.split("recorded:", 1)[1].strip()
            if tail and not tail.startswith("None"):
                try:
                    recorded = json.loads(tail)
                except ValueError:
                    recorded = {"raw": tail[:200]}
        info["listeners"] = {str(k): v for k, v in (listeners or {}).items()}
        info["recorded"] = {k: recorded.get(k) for k in ("pid", "entry", "port", "session_port")} if isinstance(recorded, dict) else None
        live = bool(listeners) and all(listeners.values())
        info["running"] = bool(live and recorded)
        info["state"] = "running" if live and recorded else ("stopped" if not recorded and not any((listeners or {}).values()) else "inconsistent")
        return info

    # -- active content ---------------------------------------------------------
    def _sha(self, path: Path):
        return jsonio.sha256(path.read_bytes()) if path.is_file() else None

    def deploy_state(self) -> dict | None:
        return jsonio.read_json(self.state_path) if self.state_path.is_file() else None

    def active(self) -> dict:
        config_sha = self._sha(self.assets / "rogue_corridor_v1.json")
        pool_sha = self._sha(self.assets / "rogue_pool_v3f.json")
        state = self.deploy_state()
        if state and state.get("config_sha256") == config_sha and state.get("pool_sha256") == pool_sha:
            return {"kind": "release", "label": "release:" + state["active_version"], "version": state["active_version"],
                    "deployed_at": state.get("deployed_at"), "content_dir": state.get("content_dir")}
        src_config = self._sha(self.cfg.proto_server / "src" / "rogue_corridor_v1.json")
        src_pool = self._sha(self.cfg.proto_server / "src" / "rogue_pool_v3f.json")
        if config_sha and config_sha == src_config and pool_sha == src_pool:
            return {"kind": "proto-install", "label": "proto-install",
                    "note": "trialctl patch 安装的 proto-server/src 原始配置（data_dir=共享 data 目录）"}
        return {"kind": "external", "label": "external:" + (config_sha or "missing")[:12],
                "note": "试验服文件被编辑台以外的操作改过（例如重新 trialctl patch 或手改）"}

    def _content_of_active(self, active: dict) -> dict | None:
        """Parsed runtime data the trial is currently serving (best effort, for run compatibility)."""
        try:
            if active["kind"] == "release":
                return release.workspace_from_release(release.release_dir(self.store, active["version"]))
            config = jsonio.read_json(self.assets / "rogue_corridor_v1.json")
            data_dir = Path(config.get("data_dir", ""))
            out = {"rules": config}
            for spec in RUNTIME_FILES:
                if spec.key == "rules" or spec.origin != "data":
                    continue
                p = data_dir / spec.source
                if p.is_file():
                    out[spec.key] = jsonio.read_json(p)
            return out
        except (OSError, ValueError, StoreError):
            return None

    # -- open runs ----------------------------------------------------------------
    def open_runs(self) -> list[dict]:
        db = self.tree / ".database" / "wdfp_data.db"
        if not db.is_file():
            return []
        try:
            con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return [{"error": "试验服数据库只读打开失败"}]
        try:
            rows = con.execute("SELECT run_id, player_id, status, revision, run_json, updated_at FROM rogue_corridor_v1_runs "
                               "WHERE status IN ('choosing_start','active')").fetchall()
        except sqlite3.Error as exc:
            if "no such table" in str(exc):
                return []
            return [{"error": f"读取进行中的局失败：{exc}"}]
        finally:
            con.close()
        out = []
        for run_id, player, status, revision, raw, updated in rows:
            try:
                run = json.loads(raw)
            except ValueError:
                run = {}
            out.append({"run_id": run_id, "player_id": player, "status": status, "revision": revision,
                        "updated_at": updated, "run": run})
        return out

    @staticmethod
    def _relic_refs(node, found: set):
        if isinstance(node, dict):
            rid = node.get("relic_id")
            if isinstance(rid, str):
                found.add(rid)
            for v in node.values():
                Trial._relic_refs(v, found)
        elif isinstance(node, list):
            for v in node:
                Trial._relic_refs(v, found)

    def compatibility(self, runs: list[dict], old: dict | None, new: dict) -> list[dict]:
        new_relics = {r.get("relic_id") for r in new.get("relics") or []}
        new_events = {e.get("event_id"): e for e in new.get("events") or []}
        old_events = {e.get("event_id"): e for e in (old or {}).get("events") or []}
        quests = {e["quest_id"] for e in enc.host_encounters(new.get("encounter_pool") or {})
                  if e["round"] not in set(((new.get("rules") or {}).get("encounters") or {}).get("exclude_rounds") or [])}
        out = []
        for item in runs:
            if "error" in item:
                out.append({"run_id": None, "breaking": [item["error"]], "notes": []})
                continue
            run = item["run"]
            breaking, notes = [], []
            refs: set = set()
            self._relic_refs({"relics": run.get("relics"), "pending": run.get("pending")}, refs)
            gone = sorted(r for r in refs if r not in new_relics)
            if gone:
                breaking.append("持有或待选的遗物被删除：" + "、".join(gone))
            pending = run.get("pending") or {}
            if pending.get("kind") == "event":
                eid = pending.get("event_id")
                if eid not in new_events:
                    breaking.append(f"待选事件 {eid} 被删除（服务端会报 UNKNOWN_EVENT）")
                elif eid in old_events and jsonio.canonical([o.get("effects") for o in old_events[eid].get("options") or []]) != \
                        jsonio.canonical([o.get("effects") for o in new_events[eid].get("options") or []]):
                    breaking.append(f"待选事件 {eid} 的选项效果/顺序变了（服务端按位置结算）")
            map_quests = {str(n.get("quest_id")) for layer in ((run.get("map") or {}).get("floors") or [])
                          for n in layer if isinstance(n, dict) and n.get("quest_id")}
            missing = sorted(q for q in map_quests if q not in quests)
            if missing and quests:
                breaking.append("已生成地图里的遭遇被排除：" + "、".join(missing[:6]))
            new_rev = (new.get("rules") or {}).get("rules_revision")
            if run.get("rules_revision") is not None and run.get("rules_revision") != new_rev:
                breaking.append(f"rules_revision {run.get('rules_revision')} → {new_rev}（旧局会被拒绝）")
            if not breaking:
                notes.append("重启后这局的后续操作立即按新数值/新池子进行（服务端没有内容版本锁）；已生成的地图与已领取物品不变")
            out.append({"run_id": item["run_id"], "player_id": item["player_id"], "status": item["status"],
                        "floor": run.get("floor"), "breaking": breaking, "notes": notes})
        return out

    # -- preflight / health -----------------------------------------------------
    def preflight(self, config_path: Path) -> dict:
        module = self.tree / "out" / "lib" / "rogue-corridor.js"
        try:
            proc = subprocess.run([self.node, str(PREFLIGHT), str(module), str(config_path)], cwd=str(config_path.parent),
                                  stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "reason": f"无法运行 node 预检：{exc}"}
        try:
            return json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
        except ValueError:
            return {"ok": False, "reason": "node 预检输出无法解析：" + proc.stderr.decode("utf-8", "replace")[-500:]}

    @staticmethod
    def _log_path(text: str):
        m = re.search(r"logs: (.+?\.out\.log) \|", text)
        return Path(m.group(1).strip()) if m else None

    def health(self, start_output: str, expect: dict, wait: float = 30.0) -> dict:
        log = self._log_path(start_output)
        if log is None:
            return {"ok": False, "reason": "trialctl start 没有给出日志路径"}
        deadline = time.time() + wait
        while time.time() < deadline:
            text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            if INERT in text:
                line = next((l for l in text.splitlines() if INERT in l), INERT)
                return {"ok": False, "reason": "服务端拒绝了回廊配置：" + line[-400:], "log": log.name}
            m = LOADED.search(text)
            if m:
                got = {"characters": int(m.group(1)), "weapons": int(m.group(2)), "relics": int(m.group(3)), "events": int(m.group(4))}
                bad = {k: (got[k], v) for k, v in expect.items() if k in got and got[k] != v}
                warn = [l[-300:] for l in text.splitlines() if "[ROGUE-CORRIDOR] data " in l and "issue" in l]
                return {"ok": not bad, "loaded": got, "mismatch": bad, "data_issues": warn, "log": log.name,
                        "reason": None if not bad else f"启动后数量与预检不同：{bad}"}
            time.sleep(0.5)
        return {"ok": False, "reason": f"{int(wait)} 秒内没有看到回廊配置加载日志", "log": log.name}

    # -- staging ------------------------------------------------------------------
    def _map_config(self, raw: bytes, data_dir: Path) -> bytes:
        value = jsonio.parse(raw)
        old = value.get("data_dir")
        target = data_dir.resolve().as_posix()
        text = raw.decode("utf-8")
        needle = '"data_dir": ' + json.dumps(old, ensure_ascii=False)
        if isinstance(old, str) and text.count(needle) == 1:
            mapped = text.replace(needle, '"data_dir": ' + json.dumps(target, ensure_ascii=False)).encode("utf-8")
        else:
            value["data_dir"] = target
            mapped = jsonio.dumps(value, jsonio.detect_style(raw))
        check = jsonio.parse(mapped)
        if check.get("data_dir") != target or {**check, "data_dir": None} != {**value, "data_dir": None}:
            raise TrialError("映射 data_dir 时配置内容发生了意外变化")
        return mapped

    def stage(self, version: str) -> tuple[Path, dict]:
        src = release.release_dir(self.store, version)
        manifest = release.verify(src)
        name = release.short(manifest["content_version"])
        target = self.content_root / name
        if target.is_dir():
            try:
                release.verify(target)
            except StoreError:
                shutil.rmtree(target)
        if not target.is_dir():
            tmp = self.content_root / f".staging-{name}-{os.getpid()}"
            if tmp.exists():
                shutil.rmtree(tmp)
            shutil.copytree(src, tmp)
            release.verify(tmp)
            os.replace(tmp, target)
        deployed = target / "deployed"
        deployed.mkdir(exist_ok=True)
        jsonio.atomic_write(deployed / "rogue_corridor_v1.json",
                            self._map_config((target / "rogue_corridor_v1.json").read_bytes(), target / "data"))
        shutil.copyfile(target / "rogue_pool_v3f.json", deployed / "rogue_pool_v3f.json")
        return target, manifest

    def _swap(self, config: bytes, pool: bytes):
        jsonio.atomic_write(self.assets / "rogue_corridor_v1.json", config)
        jsonio.atomic_write(self.assets / "rogue_pool_v3f.json", pool)

    def _backup_current(self) -> Path:
        stamp = now().replace("-", "").replace(":", "")[:15]
        backup = self.content_root / "_backup" / stamp
        n = 1
        while backup.exists():
            backup = self.content_root / "_backup" / f"{stamp}-{n}"
            n += 1
        backup.mkdir(parents=True)
        for name in ("rogue_corridor_v1.json", "rogue_pool_v3f.json"):
            if (self.assets / name).is_file():
                shutil.copyfile(self.assets / name, backup / name)
        original = self.content_root / "_original"
        if not original.is_dir() and self.active()["kind"] != "release":
            shutil.copytree(backup, original)
        return backup

    def _restore(self, backup: Path):
        self._swap((backup / "rogue_corridor_v1.json").read_bytes(), (backup / "rogue_pool_v3f.json").read_bytes())

    def _gc(self, keep: set[str]):
        if not self.content_root.is_dir():
            return
        dirs = sorted((p for p in self.content_root.iterdir() if p.is_dir() and len(p.name) == 12),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        for p in dirs[KEEP_DEPLOYED:]:
            if p.name not in keep:
                shutil.rmtree(p, ignore_errors=True)
        backups = self.content_root / "_backup"
        if backups.is_dir():
            for p in sorted(backups.iterdir(), key=lambda x: x.name, reverse=True)[KEEP_BACKUPS:]:
                shutil.rmtree(p, ignore_errors=True)

    def _log(self, entry: dict):
        self.store.trial_dir.mkdir(parents=True, exist_ok=True)
        with open(self.store.trial_dir / "deploys.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), **entry}, ensure_ascii=False) + "\n")

    def deploys(self, limit=50) -> list[dict]:
        path = self.store.trial_dir / "deploys.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in reversed(path.read_text(encoding="utf-8").splitlines()[-limit:]) if line.strip()]

    # -- actions ------------------------------------------------------------------
    def plan(self, version: str) -> dict:
        """Read-only pre-apply report for the confirmation dialog."""
        problems = self.guard()
        manifest = release.verify(release.release_dir(self.store, version))
        active = self.active()
        runs = self.open_runs()
        new = release.workspace_from_release(release.release_dir(self.store, version))
        compat = self.compatibility(runs, self._content_of_active(active), new)
        return {"guard": problems, "active": active, "target": "trial", "ports": self.env_ports(),
                "manifest": {k: manifest.get(k) for k in ("content_version", "workspace_revision", "active_profile", "host",
                                                         "validation_summary", "message", "source_version")},
                "open_runs": compat, "blocked": bool(problems) or any(c["breaking"] for c in compat),
                "needs_ack": bool(runs) and not any(c["breaking"] for c in compat)}

    def apply(self, version: str, expected_active: str, acknowledge_open_runs: bool = False, start: bool = True,
              action: str = "apply") -> dict:
        if not _apply_lock.acquire(blocking=False):
            raise ConflictError("另一个应用/回滚正在进行")
        try:
            return self._apply(version, expected_active, acknowledge_open_runs, start, action)
        finally:
            _apply_lock.release()

    def _apply(self, version, expected_active, acknowledge_open_runs, start, action):
        problems = self.guard()
        if problems:
            raise TrialError("目标不是可写的隔离试验服：" + "；".join(problems))
        plan = self.plan(version)
        if plan["active"]["label"] != expected_active:
            raise ConflictError(f"试验服当前内容是 {plan['active']['label']}，不是确认时的 {expected_active}，请刷新后重新确认")
        host = plan["manifest"]["host"] or {}
        if host.get("event_id") != 700110 or host.get("folder_id") != 1:
            raise TrialError("发布包的宿主不是隔离模式 700110/1")
        breaking = [c for c in plan["open_runs"] if c["breaking"]]
        if breaking:
            raise TrialError("有进行中的局会被这次改动破坏，拒绝应用（先在游戏里放弃/结束这些局，或手动 trialctl reset-db）："
                             + "；".join(f"{c.get('run_id')}：{'、'.join(c['breaking'])}" for c in breaking))
        if plan["open_runs"] and not acknowledge_open_runs:
            raise ConflictError("有进行中的局：服务端没有内容版本锁，重启后它们立即按新内容继续。确认后再应用（acknowledge_open_runs）")
        entry = {"action": action, "from": plan["active"]["label"], "to": "release:" + plan["manifest"]["content_version"],
                 "open_runs": len(plan["open_runs"]), "acknowledged": bool(acknowledge_open_runs)}
        content_dir, manifest = self.stage(version)
        deployed = content_dir / "deployed"
        pre = self.preflight(deployed / "rogue_corridor_v1.json")
        entry["preflight"] = {k: pre.get(k) for k in ("ok", "reason", "counts", "builtin", "issues")}
        expect_relics = len(release.workspace_from_release(content_dir)["relics"])
        new_data = release.workspace_from_release(content_dir)
        if not pre.get("ok") or pre.get("builtin") or pre["counts"]["relics"] != expect_relics \
                or pre["counts"]["events"] != len(new_data["events"]):
            entry["result"] = "preflight_failed"
            self._log(entry)
            raise TrialError("Node 预检未通过，试验服未改动：" + (pre.get("reason") or json.dumps(
                {"counts": pre.get("counts"), "issues": pre.get("issues")}, ensure_ascii=False)[:600]))
        before = self.status()
        was_running = bool(before.get("running"))
        backup = self._backup_current()
        if was_running:
            code, text = self.runner("stop")
            if code:
                entry["result"] = "stop_failed"
                self._log(entry)
                raise TrialError("trialctl stop 失败，试验服未改动：" + text[-400:])
        config_raw, pool_raw = (deployed / "rogue_corridor_v1.json").read_bytes(), (deployed / "rogue_pool_v3f.json").read_bytes()
        self._swap(config_raw, pool_raw)
        state = {"active_version": manifest["content_version"], "config_sha256": jsonio.sha256(config_raw),
                 "pool_sha256": jsonio.sha256(pool_raw), "deployed_at": now(), "content_dir": content_dir.name,
                 "backup": backup.name}
        jsonio.write_json(self.state_path, state)
        jsonio.write_json(self.content_root / "active.json", {"content_version": manifest["content_version"],
                                                               "deployed_at": state["deployed_at"],
                                                               "content_dir": content_dir.name,
                                                               "note": "编辑台指针；当前服务端不读此文件"})
        entry["was_running"] = was_running
        if start or was_running:
            code, text = self.runner("start")
            health = self.health(text, {"relics": pre["counts"]["relics"], "events": pre["counts"]["events"]}) if code == 0 \
                else {"ok": False, "reason": "trialctl start 失败：" + text[-400:]}
            entry["health"] = health
            if not health["ok"]:
                self.runner("stop")
                self._restore(backup)
                state_restored = {"restored_from": backup.name}
                if self.state_path.is_file():
                    self.state_path.unlink()
                if was_running:
                    code2, text2 = self.runner("start")
                    state_restored["restart"] = code2 == 0
                entry["result"] = "failed_restored"
                entry["restore"] = state_restored
                self._log(entry)
                raise TrialError("重启后健康检查失败，已恢复应用前的文件" + ("并重新启动" if was_running else "") + "：" + str(health.get("reason")))
        entry["result"] = "ok"
        self._log(entry)
        self._gc({content_dir.name})
        return {**entry, "active": self.active(), "status": self.status() if (start or was_running) else None}

    def restore_original(self, expected_active: str, start: bool | None = None) -> dict:
        if not _apply_lock.acquire(blocking=False):
            raise ConflictError("另一个应用/回滚正在进行")
        try:
            problems = self.guard()
            if problems:
                raise TrialError("目标不是可写的隔离试验服：" + "；".join(problems))
            active = self.active()
            if active["label"] != expected_active:
                raise ConflictError(f"试验服当前内容是 {active['label']}，请刷新后重新确认")
            original = self.content_root / "_original"
            src = original if original.is_dir() else self.cfg.proto_server / "src"
            before = self.status()
            was_running = bool(before.get("running"))
            if was_running:
                code, text = self.runner("stop")
                if code:
                    raise TrialError("trialctl stop 失败：" + text[-400:])
            self._swap((src / "rogue_corridor_v1.json").read_bytes(), (src / "rogue_pool_v3f.json").read_bytes())
            if self.state_path.is_file():
                self.state_path.unlink()
            pointer = self.content_root / "active.json"
            if pointer.is_file():
                pointer.unlink()
            entry = {"action": "restore_original", "from": active["label"], "to": self.active()["label"], "was_running": was_running}
            if start if start is not None else was_running:
                code, text = self.runner("start")
                entry["health"] = self.health(text, {}) if code == 0 else {"ok": False, "reason": text[-400:]}
            entry["result"] = "ok"
            self._log(entry)
            return {**entry, "active": self.active()}
        finally:
            _apply_lock.release()

    def stop(self) -> dict:
        code, text = self.runner("stop")
        self._log({"action": "stop", "exit": code})
        if code:
            raise TrialError("trialctl stop 失败：" + text[-400:])
        return {"ok": True, "output": text.strip()[-500:]}

    def start(self) -> dict:
        problems = self.guard()
        if problems:
            raise TrialError("目标不是可写的隔离试验服：" + "；".join(problems))
        code, text = self.runner("start")
        health = self.health(text, {}) if code == 0 else {"ok": False, "reason": text[-400:]}
        self._log({"action": "start", "exit": code, "health": health})
        if code:
            raise TrialError("trialctl start 失败：" + text[-400:])
        return {"ok": health["ok"], "health": health, "active": self.active()}
