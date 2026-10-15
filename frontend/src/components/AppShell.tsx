import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { FlaskConical, GitBranch, History, LayoutDashboard, Menu, PlusCircle, ShieldCheck, Undo2, X } from "lucide-react";
import { cx } from "./ui";

export const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/new", label: "New Return", icon: PlusCircle },
  { to: "/workflow", label: "Agent Workflow", icon: GitBranch },
  { to: "/resolution", label: "Resolution Center", icon: ShieldCheck },
  { to: "/requests", label: "Request History", icon: History },
  { to: "/lab", label: "Testing Lab", icon: FlaskConical },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-5 py-5">
      <div className="grid size-8 place-items-center rounded-lg bg-navy-800 text-teal-400"><Undo2 className="size-4.5" aria-hidden /></div>
      <div>
        <p className="text-base font-semibold leading-none text-white">ReturnWise</p>
        <p className="mt-1 text-xs text-navy-300">Return resolution control</p>
      </div>
    </div>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Primary" className="flex-1 space-y-0.5 px-3">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => cx(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-navy-700 text-white" : "text-navy-300 hover:bg-navy-800 hover:text-white")}>
          <Icon className="size-4.5 shrink-0" aria-hidden />{label}
        </NavLink>
      ))}
    </nav>
  );
}

function SidebarFoot() {
  return (
    <p className="px-5 py-4 text-xs leading-relaxed text-navy-300">
      Recommendations only. No payments are made and no customers are notified. Fictional store policies.
    </p>
  );
}

export default function AppShell() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2">Skip to content</a>

      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-navy-900 lg:flex" data-testid="sidebar">
        <Brand /><NavList /><SidebarFoot />
      </aside>

      {open && <div className="fixed inset-0 z-40 bg-navy-950/60 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}
      <aside id="mobile-nav" aria-label="Navigation drawer" hidden={!open}
        className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-navy-900 shadow-pop lg:hidden" data-testid="drawer">
        <div className="flex items-center justify-between pr-3"><Brand />
          <button onClick={() => setOpen(false)} aria-label="Close navigation" className="rounded-lg p-2 text-navy-300 hover:bg-navy-800 hover:text-white"><X className="size-5" aria-hidden /></button>
        </div>
        <NavList onNavigate={() => setOpen(false)} /><SidebarFoot />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-paper/95 px-4 backdrop-blur lg:px-8">
          <button onClick={() => setOpen(true)} aria-label="Open navigation" aria-expanded={open} aria-controls="mobile-nav"
            className="rounded-lg p-2 text-ink hover:bg-idle-bg lg:hidden"><Menu className="size-5" aria-hidden /></button>
          <p className="text-sm font-medium text-ink lg:hidden">ReturnWise</p>
          <p className="ml-auto hidden text-xs text-muted sm:block">Policy reference date is fixed at 15 Feb 2025 for reproducible results</p>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 lg:px-8 lg:py-8"><Outlet /></main>
      </div>
    </div>
  );
}
