/** Shared review decisions, independent of network timing and component rendering. */
export function pruneMapping(mapping: Record<string, string>, headers: string[]): Record<string, string> {
  return Object.fromEntries(Object.entries(mapping).map(([key, value]) => [key, headers.includes(value) ? value : ""]));
}

export function canSaveBatchRow(status: string): boolean {
  return ["可写草稿", "含需人工（仅存草稿，阻断交付）"].includes(status);
}

export function duplicateTarget(targets: { to: string }[], id: string): boolean {
  return !!id && targets.filter(t => t.to === id).length > 1;
}

export function startingId(targets: { to: string }[]): string | undefined {
  return targets[0]?.to || undefined;
}
