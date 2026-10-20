import json,sys
m=json.load(open('D:/WF/out/kulo-patch-toolkit/oldrepo_modtools/ability_enum_map.json',encoding='utf-8'))['enums']
ab={'p':'AbilityPreconditionMasterValue','it':'InstantAbilityTriggerMasterValue','dt':'DuringAbilityTriggerMasterValue','ic':'InstantAbilityContentMasterValue','cc':'CommonAbilityContentMasterValue','ip':'InstantAbilityTriggerPullerMasterValue','dp':'DuringAbilityTriggerPullerMasterValue'}
for a in sys.argv[1:]:
    t,i=a.split(':'); print(a, m[ab[t]].get(i))
