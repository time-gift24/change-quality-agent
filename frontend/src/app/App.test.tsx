// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/sop/pages/SopQualityPage", () => ({
  SopQualityPage: () => (
    <section aria-label="SOP quality workspace">SOP quality page</section>
  ),
}));

import { App } from "./App";

afterEach(() => {
  cleanup();
});

describe("App", () => {
  it("renders the SOP quality route inside the workbench shell", () => {
    render(<App />);

    expect(
      screen.getByRole("banner", { name: "Application header" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Change Quality Agent")).toBeInTheDocument();
    expect(
      screen.getByLabelText("SOP quality workspace"),
    ).toHaveTextContent("SOP quality page");
  });
});
