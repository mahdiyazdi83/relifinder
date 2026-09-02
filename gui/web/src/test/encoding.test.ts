import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourceFiles = [
  "src/features/exports/exports-page.tsx",
  "src/features/exports/dbml-code-viewer.tsx",
];

describe("source encoding", () => {
  it.each(sourceFiles)("contains no Unicode replacement character: %s", (file) => {
    expect(readFileSync(resolve(file), "utf8")).not.toContain("\uFFFD");
  });
});
