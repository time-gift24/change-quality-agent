// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StreamMarkdown } from "./StreamMarkdown";

describe("StreamMarkdown", () => {
  it("renders markdown content while streaming", () => {
    render(<StreamMarkdown isStreaming>**checking** steps</StreamMarkdown>);

    expect(screen.getByText("checking")).toBeInTheDocument();
  });
});
