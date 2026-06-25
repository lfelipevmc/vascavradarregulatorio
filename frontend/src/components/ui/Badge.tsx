import { type ReactNode } from "react";
import { clsx } from "clsx";
import type { FonteNormativo, SetorNormativo, TipoNormativo } from "@/lib/api";

type BadgeVariant = "default" | "fonte" | "setor" | "tipo" | "impacto";

const FONTE_COLORS: Record<FonteNormativo, string> = {
  DOU: "bg-blue-100 text-blue-800 border-blue-200",
  ANEEL: "bg-yellow-100 text-yellow-800 border-yellow-200",
  ANTT: "bg-orange-100 text-orange-800 border-orange-200",
  ANAC: "bg-sky-100 text-sky-800 border-sky-200",
  ANATEL: "bg-purple-100 text-purple-800 border-purple-200",
  ANM: "bg-stone-100 text-stone-800 border-stone-200",
  TCU: "bg-red-100 text-red-800 border-red-200",
  CAMARA: "bg-green-100 text-green-800 border-green-200",
  SENADO: "bg-emerald-100 text-emerald-800 border-emerald-200",
  STJ: "bg-indigo-100 text-indigo-800 border-indigo-200",
  STF: "bg-violet-100 text-violet-800 border-violet-200",
  TRF: "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200",
};

const SETOR_COLORS: Record<SetorNormativo, string> = {
  ENERGIA: "bg-amber-100 text-amber-800 border-amber-200",
  TRANSPORTE: "bg-blue-100 text-blue-800 border-blue-200",
  AVIACAO: "bg-sky-100 text-sky-800 border-sky-200",
  MINERACAO: "bg-stone-100 text-stone-800 border-stone-200",
  TELECOMUNICACOES: "bg-purple-100 text-purple-800 border-purple-200",
  ESPORTE: "bg-green-100 text-green-800 border-green-200",
  SANEAMENTO: "bg-teal-100 text-teal-800 border-teal-200",
  GERAL: "bg-gray-100 text-gray-700 border-gray-200",
};

const TIPO_LABELS: Record<TipoNormativo, string> = {
  LEI: "Lei",
  DECRETO: "Decreto",
  PORTARIA: "Portaria",
  RESOLUCAO: "Resolução",
  INSTRUCAO_NORMATIVA: "IN",
  MEDIDA_PROVISORIA: "MP",
  ACORDAO_TCU: "Acórdão TCU",
  PROJETO_LEI: "PL",
  PRECEDENTE_JUDICIAL: "Precedente",
};

const SETOR_LABELS: Record<SetorNormativo, string> = {
  ENERGIA: "Energia",
  TRANSPORTE: "Transporte",
  AVIACAO: "Aviação",
  MINERACAO: "Mineração",
  TELECOMUNICACOES: "Telecom",
  ESPORTE: "Esporte",
  SANEAMENTO: "Saneamento",
  GERAL: "Geral",
};

interface BadgeProps {
  children?: ReactNode;
  variant?: BadgeVariant;
  fonte?: FonteNormativo;
  setor?: SetorNormativo;
  tipo?: TipoNormativo;
  className?: string;
}

export function Badge({ children, variant = "default", fonte, setor, tipo, className }: BadgeProps) {
  let colorClasses = "bg-gray-100 text-gray-700 border-gray-200";
  let label = children;

  if (fonte) {
    colorClasses = FONTE_COLORS[fonte] || colorClasses;
    label = label ?? fonte;
  } else if (setor) {
    colorClasses = SETOR_COLORS[setor] || colorClasses;
    label = label ?? SETOR_LABELS[setor];
  } else if (tipo) {
    label = label ?? TIPO_LABELS[tipo];
  }

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        colorClasses,
        className
      )}
    >
      {label}
    </span>
  );
}

export function ImpactoBadge({ impacto }: { impacto: string | null }) {
  if (!impacto) return null;
  const nivel = impacto.startsWith("ALTO")
    ? "ALTO"
    : impacto.startsWith("MEDIO")
    ? "MEDIO"
    : "BAIXO";

  const colors = {
    ALTO: "bg-red-100 text-red-800 border-red-200",
    MEDIO: "bg-orange-100 text-orange-800 border-orange-200",
    BAIXO: "bg-green-100 text-green-800 border-green-200",
  };

  const labels = { ALTO: "Alto Impacto", MEDIO: "Médio Impacto", BAIXO: "Baixo Impacto" };

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        colors[nivel]
      )}
    >
      {labels[nivel]}
    </span>
  );
}
