// 测试服:给每个已有存档补发新角色(满级同模板★5),只增不减;已有的行跳过。
// 用法(停服后,在服务端根目录跑,放 tmp\ 下才 require 得到 better-sqlite3):
//   node tmp\grant-chars.cjs tmp\grant-vyrn.json [.database\wdfp_data.db]
const fs = require('node:fs'), D = require('better-sqlite3')
const g = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const db = new D(process.argv[3] || '.database/wdfp_data.db')
const players = db.prepare('SELECT id FROM players').all().map(r => r.id)
const ins = (t, o) => db.prepare(`INSERT INTO ${t} (${Object.keys(o).join(',')}) VALUES (${Object.keys(o).map(() => '?').join(',')})`).run(...Object.values(o))
const out = {}
db.transaction(() => {
  for (const pid of players) {
    let c = 0, n = 0, b = 0
    for (const r of g.characters) { if (db.prepare('SELECT 1 FROM players_characters WHERE player_id=? AND id=?').get(pid, r.id)) continue; ins('players_characters', { ...r, player_id: pid }); c++ }
    for (const r of g.mana_nodes) { if (db.prepare('SELECT 1 FROM players_characters_mana_nodes WHERE player_id=? AND character_id=? AND value=?').get(pid, r.character_id, r.value)) continue; ins('players_characters_mana_nodes', { ...r, player_id: pid }); n++ }
    for (const r of g.bond_tokens) { if (db.prepare('SELECT 1 FROM players_characters_bond_tokens WHERE player_id=? AND character_id=? AND mana_board_index=?').get(pid, r.character_id, r.mana_board_index)) continue; ins('players_characters_bond_tokens', { ...r, player_id: pid }); b++ }
    out[pid] = { chars: c, nodes: n, bonds: b }
  }
})()
db.pragma('wal_checkpoint(TRUNCATE)'); db.close(); console.log(JSON.stringify(out))
