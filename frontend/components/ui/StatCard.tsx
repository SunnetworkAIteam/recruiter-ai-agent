import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  accentClassName: string; // e.g. "border-t-info" — kept as a class rather than an inline style so Tailwind can tree-shake correctly
  accentBgClassName: string; // e.g. "bg-info-dim"
  accentTextClassName: string;
  subtext?: string;
}

export function StatCard({
  label,
  value,
  icon: Icon,
  accentClassName,
  accentBgClassName,
  accentTextClassName,
  subtext,
}: StatCardProps) {
  return (
    <div className={cn("card border-t-2 p-4", accentClassName)}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium text-ink-2">{label}</span>
        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", accentBgClassName)}>
          <Icon className={cn("w-4 h-4", accentTextClassName)} strokeWidth={2} />
        </div>
      </div>
      <div className="text-2xl font-bold tracking-tight text-ink">{value}</div>
      {subtext && <div className="text-xs text-ink-2 mt-1">{subtext}</div>}
    </div>
  );
}
