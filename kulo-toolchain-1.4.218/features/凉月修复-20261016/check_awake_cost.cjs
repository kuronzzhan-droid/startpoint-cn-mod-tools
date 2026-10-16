// 只读:用本地服编译产物查凉月 159992 每个节点的觉醒消耗(修前盒子数据返回 null 即 awake_mana_node 400)
const path = require("path")
const a = require(path.join(process.argv[2], "out/lib/assets"))
const board = require(path.join(process.argv[2], "assets/mana_board.json"))["159992"]
const ids = board ? Object.values(board).flatMap(b => Object.values(b).map(r => r[0][0])) : ["319984201", "319984241"]
let ok = 0, nul = 0
for (const id of ids) { const c = a.getManaNodeAwakeCost(159992, Number(id), 5); c === null ? nul++ : ok++ }
console.log("mana_board rows:", board ? ids.length : 0, "awake cost resolved:", ok, "null:", nul)
console.log("sample", JSON.stringify(a.getManaNodeAwakeCost(159992, Number(ids[0]), 5)))
