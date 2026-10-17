"""限定角色身份的隔离修订包；不会写 live。"""
from pathlib import Path

from wf_character_revision import RevisionCandidate, digest, encode_tree
from wf_enhancement_policy import OfficialBaseline

CID = "119989"
CODE = "lady_summoner_campus"


class Candidate(RevisionCandidate):
    def __init__(self, repo_root: Path, candidate_root: Path):
        super().__init__(
            repo_root, candidate_root, character_id=CID, code_name=CODE,
            package_version="0.2.6", snapshot_key="campus_bianca_dragon",
            evidence_name="dragon-revision.json", baseline_factory=OfficialBaseline,
        )
