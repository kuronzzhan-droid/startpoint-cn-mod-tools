// Character over-limit extension ("超限"): selected 5* characters may uncap
// past the retail cap with a dedicated item, up to level 120.
//
// The patched client mirrors these rules: a tagged character reports the
// extended cap only after the retail uncaps are used, offers only the
// extension item for the extra steps, and never offers duplicates for them.

import overLimitJson from "../../assets/character_overlimit.json"
import { characterExpCaps } from "./character"

interface OverLimitExtension {
    item_id: number
    // Items consumed together with item_id by every extended uncap step.
    extra_costs: { item_id: number, amount: number }[]
    rarity: number
    max_over_limit: number
    // Cumulative EXP at the level cap reached by each extra uncap step
    // (step base+1, base+2, ...), matching the client's bundled level table.
    extra_exp_caps: number[]
    characters: number[]
    // Awake mission ID -> character level that completes it.
    level_missions: Record<string, number>
    // Characters whose retail uncaps (1..retail max) also use the extension item
    // plus extra_costs and never duplicates ("全程超限"); client key wfx_overlimit_full_<id>.
    full_route_characters?: number[]
}

const extension = overLimitJson as OverLimitExtension
const extendedCharacters = new Set(extension.characters)
const fullRouteCharacters = new Set(extension.full_route_characters ?? [])

export const OVER_LIMIT_EXTENSION_ITEM_ID = extension.item_id

export const retailMaxOverLimits: Record<number, number> = {
    [1]: 12,
    [2]: 10,
    [3]: 8,
    [4]: 6,
    [5]: 4,
}

export function isOverLimitExtendedCharacter(characterId: number, rarity: number): boolean {
    return rarity === extension.rarity && extendedCharacters.has(characterId)
}

export function isOverLimitFullRouteCharacter(characterId: number, rarity: number): boolean {
    return isOverLimitExtendedCharacter(characterId, rarity) && fullRouteCharacters.has(characterId)
}

export function getRetailMaxOverLimit(rarity: number): number | undefined {
    return retailMaxOverLimits[rarity]
}

export function getCharacterMaxOverLimit(characterId: number, rarity: number): number | undefined {
    if (isOverLimitExtendedCharacter(characterId, rarity)) return extension.max_over_limit
    return retailMaxOverLimits[rarity]
}

function getCharacterExpCapList(characterId: number, rarity: number): number[] | undefined {
    const caps = characterExpCaps[rarity]
    if (!caps) return undefined
    return isOverLimitExtendedCharacter(characterId, rarity)
        ? [...caps, ...extension.extra_exp_caps]
        : caps
}

export function getCharacterExpCap(characterId: number, rarity: number, overLimitStep: number): number | undefined {
    return getCharacterExpCapList(characterId, rarity)?.[overLimitStep]
}

export function estimateExtendedCharacterLevel(characterId: number, rarity: number, exp: number): number {
    const caps = getCharacterExpCapList(characterId, rarity)
    if (!caps || caps.length === 0) return 0
    const baseLevel = 40 + (rarity - 1) * 10
    let level = 0
    for (let index = 0; index < caps.length; index++) {
        if (exp < caps[index]) break
        level = baseLevel + index * 5
    }
    return level
}

export function getExtendedOverLimitExtraCosts(
    characterId: number,
    rarity: number,
    currentStep: number,
    count: number,
): { itemId: number, amount: number }[] {
    const retailMax = retailMaxOverLimits[rarity]
    if (!isOverLimitExtendedCharacter(characterId, rarity) || retailMax === undefined) return []
    if (currentStep < retailMax && !isOverLimitFullRouteCharacter(characterId, rarity)) return []
    return extension.extra_costs.map(cost => ({ itemId: cost.item_id, amount: cost.amount * count }))
}

export function getAwakeLevelMissionTarget(missionId: number): number | undefined {
    return extension.level_missions[String(missionId)]
}

/**
 * Validates one over_limit request against the retail and extended caps.
 * Returns an error message, or null when the request is allowed.
 */
export function validateOverLimitRequest(
    characterId: number,
    rarity: number,
    currentStep: number,
    count: number,
    useStack: boolean,
    itemId: number | undefined,
): string | null {
    const retailMax = retailMaxOverLimits[rarity]
    const maxOver = getCharacterMaxOverLimit(characterId, rarity)
    if (retailMax === undefined || maxOver === undefined) return "Unknown rarity."
    const newStep = currentStep + count
    if (newStep > maxOver) return "Character cannot be uncapped further."
    if (isOverLimitFullRouteCharacter(characterId, rarity)) {
        if (useStack) return "Duplicates cannot uncap this character."
        if (itemId !== extension.item_id) return "Attempted to use invalid item."
        return null
    }
    if (currentStep < retailMax) {
        if (newStep > retailMax) return "Retail and extended uncaps must be requested separately."
        if (useStack) return null
        // Matches the client item table: 10003 is 5* only, 10002 covers 4* and below,
        // 10001 covers 3* and below.
        if ((rarity === 5 && itemId !== 10003)
            || (rarity === 4 && itemId !== 10002)
            || (rarity <= 3 && itemId !== 10002 && itemId !== 10001)) {
            return "Attempted to use invalid item."
        }
        return null
    }
    if (useStack) return "Duplicates cannot uncap past the retail cap."
    if (itemId !== extension.item_id) return "Attempted to use invalid item."
    return null
}
