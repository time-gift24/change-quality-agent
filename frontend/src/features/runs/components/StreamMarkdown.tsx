import { Streamdown } from "streamdown";

export function StreamMarkdown({
  children,
  isStreaming,
}: {
  children: string;
  isStreaming?: boolean;
}) {
  return (
    <div data-testid="stream-markdown">
      <Streamdown animated isAnimating={Boolean(isStreaming)}>
        {children}
      </Streamdown>
    </div>
  );
}
