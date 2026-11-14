import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const exercises = JSON.parse(await readFile(new URL("../static/exercises.json", import.meta.url), "utf8"));
const coreSlugs = [
  "00-start-here", "01-from-room-to-postgres", "02-tables-rows-types", "03-select",
  "04-changing-data", "05-joins", "06-aggregates", "07-indexes-explain",
  "08-transactions-concurrency", "09-fastapi-postgres", "10-event-driven-thinking",
];

test("every core lesson has a complete activity and all four static help levels", () => {
  assert.deepEqual(exercises.map(exercise => exercise.slug), coreSlugs);
  for (const exercise of exercises) {
    assert.ok(exercise.title && exercise.prompt);
    assert.deepEqual(Object.keys(exercise.help).sort(), ["explanation", "hint", "nudge", "solution"]);
    assert.ok(Object.values(exercise.help).every(value => value.length > 0));
    if (exercise.kind === "choice") assert.ok(exercise.choices.some(choice => choice.value === exercise.answer));
    else assert.ok(exercise.check);
  }
});
