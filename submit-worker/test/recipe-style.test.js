import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";

import { DRAFT_INSTRUCTIONS, RECIPE_STYLE } from "../src/index.js";

test("the Worker prompt is built from the repository recipe style", () => {
  const file = path.resolve(import.meta.dirname, "../recipe-style.json");
  assert.deepEqual(RECIPE_STYLE, JSON.parse(fs.readFileSync(file, "utf8")));
  assert.match(DRAFT_INSTRUCTIONS, /and\/or/);
  assert.match(DRAFT_INSTRUCTIONS, /only the title, headnote, steps and notes/);
  assert.match(DRAFT_INSTRUCTIONS, /must never be output/);
});
