import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/", label: "Recipes", icon: "📖", end: true },
  { to: "/list", label: "List", icon: "🧺", end: false },
  { to: "/kroger", label: "Kroger", icon: "🛒", end: false },
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-cream text-ink">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="font-heading text-lg font-bold text-heading">🧺 Bushel</span>
        <nav className="ml-auto hidden gap-2 sm:flex">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-semibold ${
                  isActive ? "bg-primary text-white" : "text-heading hover:bg-cream"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 pb-24 sm:pb-6">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 flex border-t border-line bg-surface sm:hidden">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `flex-1 py-2 text-center text-xs ${isActive ? "font-bold text-primary" : "text-muted"}`
            }
          >
            <div className="text-base">{t.icon}</div>
            {t.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
