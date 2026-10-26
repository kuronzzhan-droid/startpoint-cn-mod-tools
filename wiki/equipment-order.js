/* The exported catalogue is in native equipment order, not verified release-date order. */
((root) => {
  'use strict';
  function createCompare(equipment) {
    // Capture the full catalogue before filtering; opaque public IDs have no ordering meaning.
    const positions = new Map(equipment.map((entry, index) => [entry.id, index]));
    const rarity = (entry) => Number.isFinite(Number(entry.rarity)) ? Number(entry.rarity) : 0;
    return (a, b) => rarity(b) - rarity(a)
      || (positions.get(b.id) ?? -1) - (positions.get(a.id) ?? -1);
  }
  const api = {createCompare};
  root.WFEquipmentOrder = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
