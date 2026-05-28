export function createSseEventSource(url: string): EventSource {
  return new EventSource(url);
}
