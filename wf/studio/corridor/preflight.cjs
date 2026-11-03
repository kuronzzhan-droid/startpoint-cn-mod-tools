'use strict'
// Offline preflight: load a staged corridor config with the trial server's own module, exactly as
// its loadAll() does at startup (config validation, tier table + v3f overlay, encounters, relics,
// events, soul catalog). No routes, no database, no network.
//   node preflight.cjs <trial out/lib/rogue-corridor.js> <staged rogue_corridor_v1.json>
const [moduleFile, configFile] = process.argv.slice(2)
const logs = []
for (const level of ['log', 'info', 'warn', 'error']) {
  console[level] = (...args) => logs.push({ level, text: args.map(a => (a instanceof Error ? a.message : String(a))).join(' ') })
}
let result
try {
  if (!moduleFile || !configFile) throw new Error('usage: preflight.cjs <module> <config>')
  process.env.ROGUE_CORRIDOR_CONFIG = configFile
  const T = require(moduleFile).__test
  if (T.CONFIG_PATH !== configFile) throw new Error('module did not take the staged config path')
  const all = T.loadAll()
  if (!all) {
    result = { ok: false, reason: 'config/data unavailable (module would be inert)' }
  } else {
    const d = all.data
    result = {
      ok: true,
      host: all.cfg.host,
      active_profile: all.cfg.difficulty.active_profile,
      data_dir: all.cfg.data_dir,
      counts: {
        characters: d.characters.length, weapons: d.weapons.length, relics: d.relics.length, events: d.events.length,
        encounters: d.encounters.length, souls: d.souls.length, boss_playable: d.bossPlayableIds.size,
        tier_overrides_applied: d.tierOverridesApplied.length,
      },
      relic_ids: d.relics.map(r => r.relic_id),
      event_ids: d.events.map(e => e.event_id),
      builtin: d.relics.some(r => r.builtin) || d.events.some(e => e.builtin),
      sources: d.sources,
      issues: d.issues,
    }
  }
} catch (e) {
  result = { ok: false, reason: e && e.message ? e.message : String(e) }
}
process.stdout.write(JSON.stringify({ ...result, logs }))
