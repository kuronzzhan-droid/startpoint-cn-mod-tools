// Read-only: 123123 state + state-changing activity since 2026-10-16 23:10 Beijing (15:10Z).
const Database = require('better-sqlite3');
const fs = require('fs');
const CUT = Date.parse('2026-10-16T15:10:00Z');
const open = p => new Database(p, { readonly: true, fileMustExist: true });
const cols = (db, t) => { try { return db.prepare(`pragma table_info(${t})`).all().map(c => c.name); } catch { return []; } };
const asMs = v => (typeof v === 'number' ? (v < 1e12 ? v * 1000 : v) : Date.parse(v));
function dump(dbPath) {
  const db = open(dbPath);
  const acc = db.prepare("select id, username, last_login_time from accounts where username='123123'").get();
  const pc = cols(db, 'players');
  const accCol = pc.find(c => /^account_?id$/.test(c));
  const p = accCol ? db.prepare(`select * from players where ${accCol}=?`).get(acc.id) : db.prepare('select * from players where id=?').get(acc.id);
  const pid = p.id;
  const out = { account: acc, player_id: pid };
  out.player = Object.fromEntries(pc.filter(c => /party|deck|select|current|vmoney|stone|exp_pool|stamina|last_login/i.test(c)).map(c => [c, p[c]]));
  const ic = cols(db,'players_items'); const ik = ic.find(c=>/item/.test(c)&&c!=='player_id') ; out.itemCols = ic; out.items = db.prepare(`select * from players_items where player_id=?`).all(pid).filter(r => Object.values(r).some(v => v === 10000320 || v === 10000302 || v === '10000320' || v === '10000302'));
  out.parties = db.prepare('select * from players_parties where player_id=?').all(pid);
  out.groups = db.prepare('select * from players_party_groups where player_id=?').all(pid);
  const ch = cols(db, 'players_characters');
  const chKey = ch.find(c => /^character_?id$/.test(c)) || 'character_id';
  out.charCols = ch; out.c111183 = db.prepare(`select * from players_characters where player_id=?`).all(pid).find(r => Object.values(r).some(v => v === 111183 || v === '111183'));
  // every player-scoped table with a timestamp column: rows at/after cutoff
  const tables = db.prepare("select name from sqlite_master where type='table'").all().map(r => r.name);
  out.since = {};
  for (const t of tables) {
    const cs = cols(db, t);
    if (!cs.includes('player_id')) continue;
    for (const c of cs.filter(c => /(_at|_time|time)$/.test(c))) {
      const rows = db.prepare(`select ${c} v from ${t} where player_id=?`).all(pid).map(r => asMs(r.v)).filter(v => v >= CUT);
      if (rows.length) out.since[`${t}.${c}`] = { n: rows.length, latest: new Date(Math.max(...rows)).toISOString() };
    }
  }
  out.receipts_since = db.prepare('select operation, request_key, created_at from player_operation_receipts where player_id=? order by created_at desc limit 20').all(pid)
    .filter(r => asMs(r.created_at) >= CUT).map(r => ({ op: r.operation, at: new Date(asMs(r.created_at)).toISOString() }));
  db.close();
  return out;
}
const live = dump('C:/startpoint-test/.database/wdfp_data.db');
console.log(JSON.stringify({ ...live, parties: live.parties.length, groups: live.groups.length }, null, 1));
// compare against newest backup copy of the db
const bks = [];
for (const base of ['C:/startpoint-test-upload']) {
  for (const d of fs.readdirSync(base)) {
    for (const f of [`${base}/${d}/wdfp_data.db`, `${base}/${d}/db/wdfp_data.db`, `${base}/${d}/db-stopped/wdfp_data.db`, `${base}/${d}/.database/wdfp_data.db`]) {
      if (fs.existsSync(f)) bks.push([f, fs.statSync(f).mtimeMs]);
    }
  }
}
bks.sort((a, b) => b[1] - a[1]);
console.log('newest backups:', bks.slice(0, 3).map(b => `${b[0]} ${new Date(b[1]).toISOString()}`));
if (bks[0]) {
  const b = dump(bks[0][0]);
  console.log('vs backup: parties equal', JSON.stringify(b.parties) === JSON.stringify(live.parties),
    '| groups equal', JSON.stringify(b.groups) === JSON.stringify(live.groups),
    '| items backup', JSON.stringify(b.items), '| 111183 equal', JSON.stringify(b.c111183) === JSON.stringify(live.c111183));
}
