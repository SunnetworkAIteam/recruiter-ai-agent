import { Search, Bell, HelpCircle } from "lucide-react";
import type { ReactNode } from "react";
import { ThemeToggle } from "./ThemeToggle";

interface TopbarProps {
  title: string;
  actions?: ReactNode;
}

export function Topbar({ title, actions }: TopbarProps) {
  return (
    <header className="h-16 shrink-0 border-b border-border flex items-center gap-4 px-6">
      <h1 className="text-lg font-bold text-ink shrink-0">{title}</h1>
      <div className="flex-1 max-w-md relative">
        <Search className="w-4 h-4 text-ink-3 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          placeholder="Search anything…"
          className="w-full bg-surface-2 border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent transition-colors"
        />
      </div>
      <button
        aria-label="Notifications"
        className="relative w-9 h-9 rounded-lg flex items-center justify-center text-ink-2 hover:bg-surface-2 hover:text-ink transition-colors"
      >
        <Bell className="w-4 h-4" />
        <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-danger" />
      </button>

      <button
        aria-label="Help"
        className="w-9 h-9 rounded-lg flex items-center justify-center text-ink-2 hover:bg-surface-2 hover:text-ink transition-colors"
      >
        <HelpCircle className="w-4 h-4" />
      </button>
      <ThemeToggle />
      {actions}

      
    </header>
  );
}
