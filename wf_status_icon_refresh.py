"""替换杰拉尔/秋九尾的三枚48px专属状态图标，仅写候选包。"""
from pathlib import Path
import hashlib
import json
import argparse
import zipfile

from wf_character_revision import RevisionCandidate
from wf_assets import png_encode, png_decode, png_dims

ART = Path(__file__).resolve().parent/'art/status-icons-20260917'
PREVIOUS_CANDIDATES = {
    'gerald_duel': '144115ef0a2f2d52f0d24a19eb70f134dede252cf99c4991ae16538172898612',
    'inaho_foxfire': 'e6906cafcb577054e14c73611848973127e773fbaf7b3cc2028997786eb1aa57',
    'inaho_afterglow': 'ac35945f92b4434b885e32dfd02bb5124625ec1dac98dd514fc9da1a249dccc3',
}
SPECS = {
 'unicorn_lancer_rose': ('129992','0.1.12', [
    ('gerald_duel','unique_unicorn_lancer_rose_duel',
     '8141c9f01e24fc9e8a0d9d6035fbf290d16df4a12957eed0efe0896c5eed7dbb')]),
 'fox_oracle_autumn': ('139995','1.1.2', [
    ('inaho_foxfire','unique_fox_oracle_autumn_foxfire',
     'a5de148f9d4bf385b388329daf25a3eba0a49d1f427f8d9040c6404c9d745183'),
    ('inaho_afterglow','unique_fox_oracle_autumn_fever_growth_v1',
     'a5de148f9d4bf385b388329daf25a3eba0a49d1f427f8d9040c6404c9d745183')]),
}


def prepare(repo, code, backup, *, apply=False):
    cid, version, icons = SPECS[code]
    ws=repo/'work/character_packs'/code
    candidate=RevisionCandidate(repo,ws,character_id=cid,code_name=code,
        package_version=version,snapshot_key='status_icons_20260917',
        evidence_name='status-icons-20260917.json')
    originals={}
    for name, stem, old_sha in icons:
        logical='battle/common/unique_condition/'+stem+'.png'
        before=candidate.read('common',logical)
        standard=(ART/(name+'.png')).read_bytes()
        if png_dims(standard)!=(48,48):raise ValueError('requires native 48px asset')
        after=png_encode(standard)
        if png_decode(after)!=standard:raise ValueError('PNG storage roundtrip')
        if hashlib.sha256(before).hexdigest() not in (old_sha, PREVIOUS_CANDIDATES[name]) and before!=after:
            raise ValueError('existing status icon changed: '+logical)
        originals[logical]=before
        candidate.emit('common',logical,after)
    if apply:
        if backup.exists():raise ValueError('backup must be a new file')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(backup,'x') as archive:
            archive.writestr('manifest.json',candidate.manifest_bytes)
            for logical,raw in originals.items():archive.writestr(logical,raw)
    return candidate.finish(dict(size=[48,48],tool='built-in imagegen',
        prompt_set=str(ART/'prompts.json'),status_effects_unchanged=True),apply=apply)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--character',choices=SPECS,required=True)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare(Path(__file__).resolve().parents[1],args.character,args.backup,
                             apply=args.apply),ensure_ascii=False))
