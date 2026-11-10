"""Where corridor files live: the source spike, the editor store and the release/deploy layout.

Machine paths come only from ``profiles/local.json``::

    "rogue_corridor": {
      "data_dir": "outputs/work/<spike>/data",            # relics/events/locales/tier_table/...
      "proto_server": "outputs/work/<spike>/proto-server", # src/ + tools/trialctl.py + trial/tree
      "store": "outputs/work/<editor-store>"               # optional; default work/studio-drafts/rogue-corridor
    }

Relative values resolve against ``wf_root``. Nothing here creates files.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SECTION = "rogue_corridor"
CONTENT_ID = "abyss_corridor"


@dataclass(frozen=True)
class RuntimeFile:
    key: str          # workspace data key
    name: str         # basename (source.runtime_files_sha256 key)
    release: str      # path inside a release / deployed content directory
    origin: str       # "proto" (proto-server/src) or "data" (spike data dir)
    source: str       # path below that origin
    server_reads: bool = True


RUNTIME_FILES: tuple[RuntimeFile, ...] = (
    RuntimeFile("rules", "rogue_corridor_v1.json", "rogue_corridor_v1.json", "proto", "src/rogue_corridor_v1.json"),
    RuntimeFile("pool_overlay", "rogue_pool_v3f.json", "rogue_pool_v3f.json", "proto", "src/rogue_pool_v3f.json"),
    RuntimeFile("relics", "relics.json", "data/relics.json", "data", "relics.json"),
    RuntimeFile("events", "events.json", "data/events.json", "data", "events.json"),
    # tier_overrides.json feeds the data-line tier generator, not the server (kept byte-faithful).
    RuntimeFile("tier_overrides", "tier_overrides.json", "data/tier_overrides.json", "data", "tier_overrides.json", False),
    RuntimeFile("encounter_pool", "encounter_pool.json", "data/new-mode/encounter_pool.json", "data",
                "new-mode/encounter_pool.json"),
    # locales_v3.json is compiled into the client (AbyssI18nContentV3); the server only forwards *_key.
    RuntimeFile("locales", "locales_v3.json", "data/locales_v3.json", "data", "locales_v3.json", False),
)
MASTER_FILES: tuple[RuntimeFile, ...] = (
    RuntimeFile("tier_table", "tier_table.json", "data/tier_table.json", "data", "tier_table.json"),
    RuntimeFile("soul_catalog", "rules_v3_metadata.json", "data/rules_v3_metadata.json", "data", "rules_v3_metadata.json"),
)
POLICY_FILE = "rogue_pool_policy.json"
MANIFEST_FILE = "content_manifest.json"
BY_KEY = {f.key: f for f in RUNTIME_FILES + MASTER_FILES}

TRIAL_PORTS = (18011, 18013)


@dataclass(frozen=True)
class CorridorConfig:
    data_dir: Path
    proto_server: Path
    store: Path

    def source_path(self, spec: RuntimeFile) -> Path:
        return (self.proto_server if spec.origin == "proto" else self.data_dir) / spec.source

    @property
    def trial_tree(self) -> Path:
        return self.proto_server / "trial" / "tree"

    @property
    def trialctl(self) -> Path:
        return self.proto_server / "tools" / "trialctl.py"

    def public(self) -> dict:
        """What the UI may show: whether things exist, never the machine paths themselves."""
        return {"configured": True,
                "sources": {spec.key: self.source_path(spec).is_file() for spec in RUNTIME_FILES + MASTER_FILES},
                "trialctl": self.trialctl.is_file(), "trial": self.trial_tree.is_dir()}


def load_config(default_store: Path) -> CorridorConfig | None:
    """None when the profile has no ``rogue_corridor`` section (page shows a setup hint)."""
    from wf.paths import profile_data, root_path
    data, _ = profile_data()
    section = data.get(SECTION)
    if not section:
        return None
    if not isinstance(section, dict):
        raise ValueError("profiles/local.json rogue_corridor 必须是对象")

    def resolve(name, required=True):
        raw = section.get(name)
        if raw is None:
            if required:
                raise ValueError(f"profiles/local.json rogue_corridor.{name} 未配置")
            return None
        value = Path(str(raw)).expanduser()
        return (value if value.is_absolute() else root_path() / value).resolve()

    store = resolve("store", required=False) or default_store
    return CorridorConfig(resolve("data_dir"), resolve("proto_server"), store)
