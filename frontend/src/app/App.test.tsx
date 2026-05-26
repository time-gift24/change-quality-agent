// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("../features/sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP 质检</div>,
}));

describe("App", () => {
  it("renders sop route by default", async () => {
    window.history.pushState({}, "", "/");

    render(<App />);

    const main = screen.getByRole("main");
    expect(
      await within(main).findByText(/质量检查|SOP/i),
    ).toBeInTheDocument();
  });
});
