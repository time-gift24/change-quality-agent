import type { SelectHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export function Select({ className, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "h-9 appearance-none rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors hover:border-hairline-strong focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:bg-canvas-soft disabled:text-body",
        className,
      )}
      {...props}
    />
  );
}
