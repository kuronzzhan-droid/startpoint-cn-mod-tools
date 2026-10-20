// read-only schema probe
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');
const dir = 'C:/startpoint-test/.database';
const files = fs.readdirSync(dir).filter(f => /\.(db|sqlite|sqlite3)$/.test(f));
console.log('files', files);
for (const f of files) {
  const db = new Database(path.join(dir, f), { readonly: true, fileMustExist: true });
  const t = db.prepare("select name, sql from sqlite_master where type='table'").all();
  console.log('==', f, t.map(x => x.name).join(','));
  for (const x of t) if (/player|account|item|part|receipt|character|user/i.test(x.name)) console.log(x.sql.slice(0, 400));
  db.close();
}
