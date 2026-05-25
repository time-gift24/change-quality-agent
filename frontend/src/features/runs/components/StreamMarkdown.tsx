import { Streamdown } from "streamdown";

export function StreamMarkdown({
  children,
  isStreaming,
}: {
  children: string;
  isStreaming?: boolean;
}) {
  return (
    <Streamdown animated isAnimating={Boolean(isStreaming)}>
      {children}
    </Streamdown>
  );
}
