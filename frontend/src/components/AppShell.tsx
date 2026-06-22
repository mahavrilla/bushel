import type { ComponentType } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { BasketIcon, BookIcon, CartIcon, type IconProps } from "./ui/icons";

const tabs: { to: string; label: string; icon: ComponentType<IconProps>; end: boolean }[] = [
  { to: "/", label: "Recipes", icon: BookIcon, end: true },
  { to: "/list", label: "List", icon: BasketIcon, end: false },
  { to: "/kroger", label: "Kroger", icon: CartIcon, end: false },
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <span className="text-lg font-bold tracking-tight text-heading">Bushel</span>
        <nav className="ml-auto hidden gap-1 sm:flex">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-semibold ${
                  isActive ? "bg-primary text-white" : "text-heading hover:bg-canvas"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-6 pb-28 sm:pb-6">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 flex border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] sm:hidden">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${
                  isActive ? "text-primary" : "text-muted"
                }`
              }
            >
              <Icon size={22} />
              {t.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
