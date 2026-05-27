import type { ButtonHTMLAttributes, HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export function Sidebar({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <aside className={cn("h-screen overflow-hidden", className)} {...props} />;
}

export function SidebarHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex h-14 shrink-0 items-center gap-2 px-3", className)} {...props} />;
}

export function SidebarContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("min-h-0 flex-1 overflow-y-auto", className)} {...props} />;
}

export function SidebarMenu({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <nav className={cn("flex flex-col gap-1 px-2 pt-2", className)} {...props} />;
}

type SidebarMenuButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  isActive?: boolean;
  open?: boolean;
};

export function SidebarMenuButton({
  className,
  isActive = false,
  open = true,
  type = "button",
  ...props
}: SidebarMenuButtonProps) {
  return (
    <button
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "flex h-9 items-center gap-2 rounded-xl text-xs font-medium transition-colors",
        open ? "w-full px-2" : "w-10 justify-center px-0",
        isActive
          ? "bg-canvas text-ink shadow-sm ring-1 ring-primary/30"
          : "text-body hover:bg-canvas-soft hover:text-ink",
        className,
      )}
      type={type}
      {...props}
    />
  );
}
