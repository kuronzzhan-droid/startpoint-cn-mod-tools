"""奈芙提姆隔离修订包身份与版本约束。"""
from pathlib import Path

from wf_character_revision import RevisionCandidate, digest
from wf_mod_tool import sha1_path
from wf_nephtim_fever_powerflip import with_bundle_fallback

CID, CODE = "169989", "ruin_girl_campus"


class Candidate(RevisionCandidate):
    def __init__(self, repo_root: Path, candidate_root: Path):
        super().__init__(repo_root, candidate_root, character_id=CID, code_name=CODE,
                         package_version="0.2.2", snapshot_key="campus_nephtim_fever",
                         evidence_name="dark-fever-revision.json")

    def native_assets(self, bundle: Path):
        """官方 CDN 缺省返回 None，才能按约定回退到只读原生 bundle。"""
        def optional(logical):
            hashed = sha1_path(logical)
            return self.baseline.get("common", hashed[:2] + "/" + hashed[2:])
        fallback = with_bundle_fallback(optional, bundle)

        def read(logical):
            raw = fallback(logical)
            self.sources["common", logical] = digest(raw)
            return raw
        return read
