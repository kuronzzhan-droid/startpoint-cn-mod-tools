import sys; sys.path.insert(0, r"D:/WF/out/平衡1016")
from fw import *
F = Framework()
print(F.describe(AB, "1599973")[6])
print(F.cas_text("desc_override_guildknight_leader_tavern_3")[-60:])
print(list(F.table(AS)["guildknight_leader_tavern"]))
print(source(AB))
