import { type ReactNode } from "react";
import { clsx } from "clsx";

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export function Card({ children, className, hover = false }: CardProps) {
  return (
    <div
      className={clsx(
        "rounded-lg border border-gray-200 bg-white shadow-card",
        hover && "transition-shadow duration-200 hover:shadow-card-hover",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx("border-b border-gray-100 px-6 py-4", className)}>{children}</div>
  );
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("px-6 py-4", className)}>{children}</div>;
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: { value: number; label: string };
  color?: "blue" | "gold" | "green" | "red";
}

export function StatCard({ title, value, subtitle, icon, color = "blue" }: StatCardProps) {
  const colorMap = {
    blue: "from-navy-700 to-navy-900",
    gold: "from-gold-500 to-gold-700",
    green: "from-emerald-500 to-emerald-700",
    red: "from-red-500 to-red-700",
  };

  return (
    <Card className="overflow-hidden">
      <div className={clsx("bg-gradient-to-br p-6 text-white", colorMap[color])}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-white/80">{title}</p>
            <p className="mt-1 text-3xl font-bold">{value.toLocaleString()}</p>
            {subtitle && <p className="mt-1 text-sm text-white/70">{subtitle}</p>}
          </div>
          {icon && <div className="text-white/60">{icon}</div>}
        </div>
      </div>
    </Card>
  );
}
