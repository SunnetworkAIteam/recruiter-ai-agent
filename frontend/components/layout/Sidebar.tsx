"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, OrganizationSwitcher, useOrganization, useUser } from "@clerk/nextjs";
import { LayoutGrid, Users, Briefcase, Mic, BarChart3, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_SECTIONS = [
  {
    label: "Workspace",
    items: [
      { href: "/candidates", label: "Candidates", icon: Users },
      { href: "/jobs", label: "Jobs", icon: Briefcase },
      { href: "/interviews", label: "Interviews", icon: Mic },
    ],
  },
  {
    label: "Insights",
    items: [{ href: "/analytics", label: "Analytics", icon: BarChart3 }],
  },
  {
    label: "Config",
    items: [{ href: "/settings", label: "Settings", icon: Settings }],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { organization } = useOrganization();
  const { user } = useUser();

  return (
    <aside className="w-56 shrink-0 bg-surface border-r border-border h-screen flex flex-col">
      <div className="px-4 py-5 border-b border-border flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-teal flex items-center justify-center shrink-0 shadow-glow">
          <LayoutGrid className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        <span className="text-sm font-bold tracking-tight text-ink">RecruiterAI</span>
      </div>

      <nav className="flex-1 px-2.5 py-3 overflow-y-auto">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-1">
            <div className="text-[10px] font-semibold text-ink-3 uppercase tracking-widest px-2.5 py-2.5 pb-1.5">
              {section.label}
            </div>
            {section.items.map((item) => {
              const active = pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "relative flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm mb-0.5 transition-colors",
                    active ? "bg-accent-dim text-accent-light font-medium" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                  )}
                >
                  {active && (
                    <span className="absolute -left-2.5 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-accent rounded-full" />
                  )}
                  <Icon className="w-4 h-4 shrink-0" strokeWidth={2} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="p-3 border-t border-border space-y-2">
        <OrganizationSwitcher
          hidePersonal
          appearance={{
            elements: {
              rootBox: "w-full",
              organizationSwitcherTrigger: "w-full justify-between text-ink text-xs px-2 py-1.5 rounded-lg hover:bg-surface-2",
            },
          }}
        />
        <div className="flex items-center gap-2.5 px-1 py-1.5">
          <UserButton
            appearance={{ elements: { avatarBox: "w-8 h-8" } }}
          />
          <div className="min-w-0">
            <div className="text-xs font-medium text-ink truncate">{user?.fullName ?? "Recruiter"}</div>
            <div className="text-[11px] text-ink-2 truncate">
              {organization?.name ?? "No organization"}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
