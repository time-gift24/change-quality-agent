import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost";
type ButtonSize = "sm" | "icon";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

const variantClass: Record<ButtonVariant, string> = {
  primary: "border-transparent bg-primary text-on-primary hover:bg-primary-deep",
  secondary: "border-hairline bg-canvas text-body hover:border-primary/40 hover:text-ink",
  destructive: "border-error/40 bg-canvas text-error-deep hover:bg-error-soft",
  ghost: "border-transparent bg-transparent text-mute hover:bg-canvas-soft hover:text-ink",
};

const sizeClass: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-xs",
  icon: "h-9 w-9 p-0 text-xs",
};

export function Button({
  className,
  size = "sm",
  type = "button",
  variant = "secondary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variantClass[variant],
        sizeClass[size],
        className,
      )}
      type={type}
      {...props}
    />
  );
}
