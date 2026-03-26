// src/components/layouts/AppLayout.tsx
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { path: "/app/dashboard", icon: "📊", label: "Dashboard" },
  { path: "/app/live-radar", icon: "📡", label: "Live Radar" },
  { path: "/app/threats", icon: "⚠️", label: "Threats" },
  { path: "/app/logs", icon: "📋", label: "Logs" },
  { path: "/app/users", icon: "👤", label: "Users" },
  { divider: true },
  { path: "/app/api-keys", icon: "🔑", label: "API Keys" },
  { path: "/app/webhooks", icon: "🔗", label: "Webhooks" },
  { path: "/app/usage", icon: "💰", label: "Usage" },
  { path: "/app/settings", icon: "⚙️", label: "Settings" },
  { divider: true },
  { path: "/app/playground", icon: "🧪", label: "Playground" },
];

export default function AppLayout() {
  const { tenant, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const currentPageLabel = navItems.find(
    (item) => !("divider" in item && item.divider) && "path" in item && item.path === location.pathname
  );

  return (
    <TooltipProvider delayDuration={0}>
      <div className="min-h-screen bg-background flex">
        {/* SIDEBAR */}
        <aside
          className={`${
            collapsed ? "w-16" : "w-60"
          } bg-card border-r border-border flex flex-col transition-all duration-300 shrink-0`}
        >
          {/* Logo */}
          <div className="h-16 flex items-center px-4 border-b border-border gap-2">
            <div className="w-8 h-8 rounded-full bg-teal-600 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            {!collapsed && (
              <span className="text-lg font-bold text-foreground">AuthDNA</span>
            )}
          </div>

          {/* Navigation */}
          <ScrollArea className="flex-1 py-2">
            <nav className="space-y-1 px-2">
              {navItems.map((item, idx) => {
                if ("divider" in item && item.divider) {
                  return <Separator key={idx} className="my-3" />;
                }

                const navItem = item as { path: string; icon: string; label: string };
                const isActive = location.pathname.startsWith((navItem as any).path) && 
                                 ((navItem as any).path !== "/app" || location.pathname === "/app");

                const linkContent = (
                  <NavLink
                    key={navItem.path}
                    to={navItem.path}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                      isActive
                        ? "bg-teal-600/10 text-teal-600 font-medium"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    }`}
                  >
                    <span className="text-lg shrink-0">{navItem.icon}</span>
                    {!collapsed && <span>{navItem.label}</span>}
                  </NavLink>
                );

                if (collapsed) {
                  return (
                    <Tooltip key={navItem.path}>
                      <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                      <TooltipContent side="right">{navItem.label}</TooltipContent>
                    </Tooltip>
                  );
                }

                return linkContent;
              })}
            </nav>
          </ScrollArea>

          {/* Tenant Info */}
          {!collapsed && (
            <div className="p-4 border-t border-border">
              <p className="text-sm font-medium text-foreground truncate">{tenant?.company_name}</p>
              <Badge variant="secondary" className="mt-1 capitalize text-xs">
                {tenant?.tier}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                className="w-full mt-3 text-destructive hover:text-destructive"
                onClick={logout}
              >
                Logout
              </Button>
            </div>
          )}

          {/* Collapse Toggle */}
          <Button
            variant="ghost"
            size="sm"
            className="m-2"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? "▶" : "◀"}
          </Button>
        </aside>

        {/* MAIN */}
        <main className="flex-1 overflow-auto">
          {/* Top Bar */}
          <header className="h-16 bg-card border-b border-border px-6 flex items-center justify-between shrink-0">
            <h1 className="text-lg font-semibold text-foreground">
              {currentPageLabel && "label" in currentPageLabel
                ? currentPageLabel.label
                : "Dashboard"}
            </h1>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-teal-600 flex items-center justify-center text-white text-sm font-bold">
                {tenant?.company_name?.[0]?.toUpperCase() || "?"}
              </div>
            </div>
          </header>

          {/* Page Content */}
          <div className="p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}