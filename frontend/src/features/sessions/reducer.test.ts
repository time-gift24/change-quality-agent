import { describe, expect, it } from "vitest";

import {
  createInitialSessionViewState,
  hydrateSessionViewState,
  projectSessionMessagesByStep,
  reduceSessionStreamEvent,
} from "./reducer";

describe("session reducer", () => {
  it("persisted message events update latestSequence", () => {
    const state = reduceSessionStreamEvent(
      createInitialSessionViewState(),
      {
        type: "message",
        session_id: 1,
        sequence: 5,
        role: "assistant",
        content: "hello",
        additional_kwargs: {},
      },
    );

    expect(state.latestSequence).toBe(5);
    expect(state.messages).toHaveLength(1);
  });

  it("message_delta events do not update latestSequence", () => {
    const initial = createInitialSessionViewState();
    initial.latestSequence = 3;

    const state = reduceSessionStreamEvent(initial, {
      type: "message_delta",
      session_id: 1,
      sequence: null,
      role: "assistant",
      content: "chunk",
      additional_kwargs: { step: "review_sop" },
    });

    expect(state.latestSequence).toBe(3);
  });

  it("live assistant delta is buffered by step key", () => {
    let state = reduceSessionStreamEvent(
      createInitialSessionViewState(),
      {
        type: "message_delta",
        session_id: 1,
        sequence: null,
        role: "assistant",
        content: "Hello ",
        additional_kwargs: { step: "review_sop" },
      },
    );

    state = reduceSessionStreamEvent(state, {
      type: "message_delta",
      session_id: 1,
      sequence: null,
      role: "assistant",
      content: "world",
      additional_kwargs: { step: "review_sop" },
    });

    expect(state.liveBuffers["step:review_sop"]).toBe("Hello world");
  });

  it("persisted message clears the matching live buffer", () => {
    let state = reduceSessionStreamEvent(
      createInitialSessionViewState(),
      {
        type: "message_delta",
        session_id: 1,
        sequence: null,
        role: "assistant",
        content: "streaming...",
        additional_kwargs: { step: "review_sop" },
      },
    );

    state = reduceSessionStreamEvent(state, {
      type: "message",
      session_id: 1,
      sequence: 10,
      role: "assistant",
      content: "final text",
      additional_kwargs: { step: "review_sop" },
    });

    expect(state.liveBuffers["step:review_sop"]).toBeUndefined();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].content).toBe("final text");
  });

  it("duplicate sequence message is ignored", () => {
    const event = {
      type: "message" as const,
      session_id: 1,
      sequence: 7,
      role: "assistant" as const,
      content: "once",
      additional_kwargs: {},
    };

    const first = reduceSessionStreamEvent(
      createInitialSessionViewState(),
      event,
    );
    const second = reduceSessionStreamEvent(first, event);

    expect(second.messages).toHaveLength(1);
  });

  it("thinking live event sets thinking state without showing text", () => {
    const state = reduceSessionStreamEvent(
      createInitialSessionViewState(),
      {
        type: "message_delta",
        session_id: 1,
        sequence: null,
        role: "assistant",
        content: "reasoning...",
        additional_kwargs: { step: "review_sop", channel: "thinking" },
      },
    );

    expect(state.thinking["step:review_sop"]).toBe(true);
    expect(state.liveBuffers["step:review_sop"]).toBeUndefined();
  });

  it("hydrates initial state from persisted messages", () => {
    const messages = [
      {
        id: "msg-1",
        session_id: 1,
        sequence: 1,
        role: "user" as const,
        content: "hi",
        additional_kwargs: { step: "load_sop" },
        created_at: "",
      },
      {
        id: "msg-2",
        session_id: 1,
        sequence: 3,
        role: "assistant" as const,
        content: "done",
        additional_kwargs: { step: "load_sop" },
        created_at: "",
      },
    ];

    const state = hydrateSessionViewState(messages);

    expect(state.latestSequence).toBe(3);
    expect(state.messages).toHaveLength(2);
    expect(state.liveBuffers).toEqual({});
  });
});

describe("projectSessionMessagesByStep", () => {
  it("groups messages by additional_kwargs.step", () => {
    const state = createInitialSessionViewState();
    state.messages = [
      {
        id: "msg-1",
        session_id: 1,
        sequence: 1,
        role: "assistant",
        content: "已读取",
        additional_kwargs: { step: "load_sop" },
        created_at: "",
      },
      {
        id: "msg-2",
        session_id: 1,
        sequence: 2,
        role: "assistant",
        content: "reviewed",
        additional_kwargs: { step: "review_sop" },
        created_at: "",
      },
      {
        id: "msg-3",
        session_id: 1,
        sequence: 3,
        role: "assistant",
        content: "继续读取",
        additional_kwargs: { step: "load_sop" },
        created_at: "",
      },
    ];

    const grouped = projectSessionMessagesByStep(state);

    expect(grouped.load_sop).toHaveLength(2);
    expect(grouped.review_sop).toHaveLength(1);
  });

  it("puts messages without step into unknown", () => {
    const state = createInitialSessionViewState();
    state.messages = [
      {
        id: "msg-1",
        session_id: 1,
        sequence: 1,
        role: "user",
        content: "orphan",
        additional_kwargs: {},
        created_at: "",
      },
    ];

    const grouped = projectSessionMessagesByStep(state);

    expect(grouped.unknown).toHaveLength(1);
  });
});
