// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("../features/sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP 质检</div>,
}));

describe("App", () => {
  it("renders sop route by default", async () => {
    window.history.pushState({}, "", "/");

    render(<App />);

    expect(await screen.findAllByText(/质量检查|SOP/i)).not.toHaveLength(0);
  });
});
