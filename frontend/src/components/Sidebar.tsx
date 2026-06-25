"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Zap,
  Truck,
  Plane,
  Radio,
  Mountain,
  Droplets,
  Scale,
  Settings,
} from "lucide-react";
import { clsx } from "clsx";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Normativos", href: "/normativos", icon: FileText },
];

const setores = [
  { name: "Energia", href: "/normativos?setor=ENERGIA", icon: Zap },
  { name: "Transporte", href: "/normativos?setor=TRANSPORTE", icon: Truck },
  { name: "Aviação", href: "/normativos?setor=AVIACAO", icon: Plane },
  { name: "Telecom", href: "/normativos?setor=TELECOMUNICACOES", icon: Radio },
  { name: "Mineração", href: "/normativos?setor=MINERACAO", icon: Mountain },
  { name: "Saneamento", href: "/normativos?setor=SANEAMENTO", icon: Droplets },
  { name: "Judicial", href: "/normativos?tipo=PRECEDENTE_JUDICIAL", icon: Scale },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-shrink-0 flex-col bg-navy-900">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-navy-700 px-6 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-500">
          <span className="text-sm font-bold text-navy-900">RR</span>
        </div>
        <div>
          <p className="text-sm font-bold text-white">Radar Regulatório</p>
          <p className="text-xs text-navy-300">Vascav</p>
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
        <div className="space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={clsx(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-navy-700 text-white"
                    : "text-navy-300 hover:bg-navy-800 hover:text-white"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            );
          })}
        </div>

        <div className="mt-6">
          <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-navy-400">
            Setores
          </p>
          <div className="space-y-1">
            {setores.map((item) => {
              const isActive = pathname + (typeof window !== "undefined" ? window.location.search : "") === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={clsx(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-navy-700 text-white"
                      : "text-navy-300 hover:bg-navy-800 hover:text-white"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Settings footer */}
      <div className="border-t border-navy-700 px-3 py-4">
        <Link
          href="/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-navy-300 hover:bg-navy-800 hover:text-white"
        >
          <Settings className="h-4 w-4" />
          Configurações
        </Link>
      </div>
    </aside>
  );
}
