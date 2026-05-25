export function createRunEventSource(url: string): EventSource {
  return new EventSource(url);
}
