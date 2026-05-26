import { describe, expect, it } from "vitest";

import css from "./globals.css?raw";

describe("global control typography", () => {
  it("does not reset Tailwind font-size utilities on controls", () => {
    expect(css).not.toContain("font: inherit;");
  });
});
