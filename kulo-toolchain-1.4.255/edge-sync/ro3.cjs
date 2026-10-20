const D=require('better-sqlite3');
for (const f of ['C:/startpoint-test/.database/wdfp_data.db','C:/startpoint-test-upload/b221-backup-20261017-075403/db-stopped/wdfp_data.db','C:/startpoint-test-upload/b39-backup-20261016-165725/db-stopped/wdfp_data.db']) {
  const db=new D(f,{readonly:true,fileMustExist:true});
  const p=db.prepare('select exp_pool,vmoney,free_vmoney,stamina,party_slot from players where id=2').get();
  const m=db.prepare("select count(*) n from players_mails where player_id=2").get();
  const c=db.prepare("select count(*) n, sum(exp) e from players_characters where player_id=2").get();
  console.log(f.split('/').slice(-3).join('/'), JSON.stringify(p), 'mails', m.n, 'chars', c.n, 'sumexp', c.e);
  db.close();
}
