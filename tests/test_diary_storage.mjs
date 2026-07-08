/**
 * DiaryStorage localStorage round-trip tests (Node, no browser data touched).
 */
import fs from "fs";
import vm from "vm";

function createStorage() {
  const data = {};
  return {
    setItem(k, v) {
      data[k] = String(v);
    },
    getItem(k) {
      return data[k] ?? null;
    },
    removeItem(k) {
      delete data[k];
    },
    clear() {
      for (const k of Object.keys(data)) delete data[k];
    },
  };
}

const sandbox = {
  localStorage: createStorage(),
  sessionStorage: createStorage(),
  console,
};
sandbox.window = sandbox;
sandbox.document = { addEventListener() {} };

const wrapped = `(function() {\n${fs.readFileSync(new URL("../site/js/diary-shared.js", import.meta.url), "utf8")}\nreturn DiaryStorage;\n})()`;
const DS = vm.runInNewContext(wrapped, sandbox);

function assert(cond, msg) {
  if (!cond) throw new Error(`FAIL: ${msg}`);
  console.log(`PASS: ${msg}`);
}

const sample = {
  "2026-07-08": [
    {
      name: "테스트식당",
      rating: 5,
      memo: "맛있음",
      price_min_krw: 10000,
      price_max_krw: 15000,
      createdAt: "2026-07-08T01:00:00.000Z",
    },
  ],
};

const saveResult = DS.saveEntries(sample);
assert(saveResult.ok && saveResult.persistent, "saveEntries succeeds with localStorage");

const loaded = DS.loadEntries();
assert(loaded["2026-07-08"][0].name === "테스트식당", "reload preserves restaurant name");
assert(loaded["2026-07-08"][0].price_min_krw === 10000, "reload preserves price fields");

// Simulate leaving and reopening the page
const reopened = DS.loadEntries();
assert(reopened["2026-07-08"].length === 1, "data survives page navigation");

// Add another day without losing the first
reopened["2026-07-07"] = [
  { name: "어제식당", rating: 4, memo: "", createdAt: "2026-07-07T01:00:00.000Z" },
];
DS.saveEntries(reopened);
const merged = DS.loadEntries();
assert(merged["2026-07-08"].length === 1 && merged["2026-07-07"].length === 1, "new day merge keeps existing days");

// Delete one day
delete merged["2026-07-07"];
DS.saveEntries(merged);
const afterDelete = DS.loadEntries();
assert(!afterDelete["2026-07-07"] && afterDelete["2026-07-08"].length === 1, "delete one day keeps others");

// Invalid keys must not wipe valid data
const withBad = DS.loadEntries();
withBad.invalid = [{ name: "x", rating: 3, memo: "", createdAt: new Date().toISOString() }];
DS.saveEntries(withBad);
const cleaned = DS.loadEntries();
assert(!cleaned.invalid && cleaned["2026-07-08"].length === 1, "invalid date keys filtered safely");

console.log("ALL TESTS PASSED");
