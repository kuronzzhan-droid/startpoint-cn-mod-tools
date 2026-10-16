const test = require("node:test")
const assert = require("node:assert/strict")

const {
    OVER_LIMIT_EXTENSION_ITEM_ID,
    estimateExtendedCharacterLevel,
    getExtendedOverLimitExtraCosts,
    getAwakeLevelMissionTarget,
    getCharacterExpCap,
    getCharacterMaxOverLimit,
    validateOverLimitRequest,
} = require("../out/lib/character-overlimit")

const WAGNER = 111183
const OTHER_FIVE_STAR = 111001

test("only listed 5* characters get the extended cap", () => {
    assert.equal(getCharacterMaxOverLimit(WAGNER, 5), 8)
    assert.equal(getCharacterMaxOverLimit(OTHER_FIVE_STAR, 5), 4)
    assert.equal(getCharacterMaxOverLimit(WAGNER, 4), 6)
})

test("retail uncaps keep their retail items and duplicates", () => {
    assert.equal(validateOverLimitRequest(WAGNER, 5, 0, 4, false, 10003), null)
    assert.equal(validateOverLimitRequest(WAGNER, 5, 2, 1, true, undefined), null)
    assert.match(validateOverLimitRequest(WAGNER, 5, 0, 1, false, OVER_LIMIT_EXTENSION_ITEM_ID), /invalid item/)
    assert.match(validateOverLimitRequest(WAGNER, 5, 3, 2, false, 10003), /separately/)
})

test("retail crystals follow the client rarity limits", () => {
    const FOUR_STAR = 141008
    const THREE_STAR = 131001
    assert.match(validateOverLimitRequest(FOUR_STAR, 4, 0, 1, false, 10001), /invalid item/)
    assert.equal(validateOverLimitRequest(FOUR_STAR, 4, 0, 1, false, 10002), null)
    assert.match(validateOverLimitRequest(FOUR_STAR, 4, 0, 1, false, 10003), /invalid item/)
    assert.equal(validateOverLimitRequest(THREE_STAR, 3, 0, 1, false, 10001), null)
    assert.equal(validateOverLimitRequest(THREE_STAR, 3, 0, 1, false, 10002), null)
    assert.match(validateOverLimitRequest(WAGNER, 5, 0, 1, false, 10002), /invalid item/)
})

test("extended uncaps take only the extension item", () => {
    assert.equal(validateOverLimitRequest(WAGNER, 5, 4, 4, false, OVER_LIMIT_EXTENSION_ITEM_ID), null)
    assert.match(validateOverLimitRequest(WAGNER, 5, 4, 1, false, 10003), /invalid item/)
    assert.match(validateOverLimitRequest(WAGNER, 5, 4, 1, true, undefined), /Duplicates/)
    assert.match(validateOverLimitRequest(WAGNER, 5, 7, 2, false, OVER_LIMIT_EXTENSION_ITEM_ID), /further/)
    assert.match(validateOverLimitRequest(OTHER_FIVE_STAR, 5, 4, 1, false, OVER_LIMIT_EXTENSION_ITEM_ID), /further/)
})

test("exp caps and level estimate reach 120 only for listed characters", () => {
    assert.equal(getCharacterExpCap(WAGNER, 5, 4), 379988)
    assert.equal(getCharacterExpCap(WAGNER, 5, 8), 679988)
    assert.equal(getCharacterExpCap(OTHER_FIVE_STAR, 5, 8), undefined)
    assert.equal(estimateExtendedCharacterLevel(WAGNER, 5, 379988), 100)
    assert.equal(estimateExtendedCharacterLevel(WAGNER, 5, 679987), 115)
    assert.equal(estimateExtendedCharacterLevel(WAGNER, 5, 679988), 120)
    assert.equal(estimateExtendedCharacterLevel(OTHER_FIVE_STAR, 5, 679988), 100)
})

test("the level-120 awake mission is configured", () => {
    assert.equal(getAwakeLevelMissionTarget(1111831), 120)
    assert.equal(getAwakeLevelMissionTarget(1111832), undefined)
})

test("extended uncaps also cost paradox cores, retail ones do not", () => {
    assert.deepEqual(getExtendedOverLimitExtraCosts(WAGNER, 5, 4, 2), [{ itemId: 10000302, amount: 2 }])
    assert.deepEqual(getExtendedOverLimitExtraCosts(WAGNER, 5, 2, 1), [])
    assert.deepEqual(getExtendedOverLimitExtraCosts(OTHER_FIVE_STAR, 5, 4, 1), [])
})
