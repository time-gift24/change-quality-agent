export function createSseEventSource(url: string): EventSource {
  return new EventSource(url);
}

export function createRunEventSource(url: string): EventSource {
  return createSseEventSource(url);
}
