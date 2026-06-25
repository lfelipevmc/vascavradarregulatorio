"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { FileText, TrendingUp, CheckCircle, Clock, ExternalLink } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { api, type NormativoListItem } from "@/lib/api";
import { Badge, ImpactoBadge } from "@/components/ui/Badge";
import { Card, StatCard } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { SearchBar } from "@/components/ui/SearchBar";
import { useState } from "react";

const SETOR_COLORS: Record<string, string> = {
  ENERGIA: "#d4a017",
  TRANSPORTE: "#3b82f6",
  AVIACAO: "#0ea5e9",
  MINERACAO: "#92400e",
  TELECOMUNICACOES: "#7c3aed",
  SANEAMENTO: "#0d9488",
  ESPORTE: "#16a34a",
  GERAL: "#6b7280",
};

export default function DashboardPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: api.getStats,
    refetchInterval: 60_000,
  });

  const { data: recentes, isLoading: recentesLoading } = useQuery({
    queryKey: ["normativos", "recentes", search],
    queryFn: () =>
      api.listNormativos({
        q: search || undefined,
        page_size: 10,
      }),
    refetchInterval: 60_000,
  });

  const setorChartData = stats
    ? Object.entries(stats.por_setor)
        .map(([setor, count]) => ({ setor, count }))
        .sort((a, b) => b.count - a.count)
    : [];

  const fonteChartData = stats
    ? Object.entries(stats.por_fonte)
        .map(([fonte, count]) => ({ fonte, count }))
        .sort((a, b) => b.count - a.count)
    : [];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Monitoramento regulatório em tempo real
        </p>
      </div>

      {/* Stats cards */}
      {statsLoading ? (
        <LoadingState message="Carregando estatísticas..." />
      ) : stats ? (
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total de Normativos"
            value={stats.total}
            subtitle="na base de dados"
            icon={<FileText className="h-8 w-8" />}
            color="blue"
          />
          <StatCard
            title="Novos Hoje"
            value={stats.novos_hoje}
            subtitle="publicados nas últimas 24h"
            icon={<TrendingUp className="h-8 w-8" />}
            color="gold"
          />
          <StatCard
            title="Processados por IA"
            value={stats.processados_ia}
            subtitle="com resumo e classificação"
            icon={<CheckCircle className="h-8 w-8" />}
            color="green"
          />
          <StatCard
            title="Pendentes IA"
            value={stats.pendentes_ia}
            subtitle="aguardando processamento"
            icon={<Clock className="h-8 w-8" />}
            color="red"
          />
        </div>
      ) : null}

      {/* Charts row */}
      {stats && (
        <div className="mb-8 grid gap-6 lg:grid-cols-2">
          <Card>
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-sm font-semibold text-gray-900">Por Setor</h2>
            </div>
            <div className="px-6 py-4">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={setorChartData} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="setor" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {setorChartData.map((entry) => (
                      <Cell
                        key={entry.setor}
                        fill={SETOR_COLORS[entry.setor] || "#6b7280"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-sm font-semibold text-gray-900">Por Fonte</h2>
            </div>
            <div className="px-6 py-4">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={fonteChartData} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="fonte" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0f1f4a" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      {/* Recent normativos */}
      <Card>
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 className="text-sm font-semibold text-gray-900">Normativos Recentes</h2>
          <SearchBar
            value={search}
            onChange={setSearch}
            placeholder="Buscar..."
            className="w-64"
          />
        </div>

        {recentesLoading ? (
          <LoadingState />
        ) : (
          <div className="divide-y divide-gray-50">
            {recentes?.items.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-gray-500">
                Nenhum normativo encontrado
              </div>
            ) : (
              recentes?.items.map((item: NormativoListItem) => (
                <div
                  key={item.id}
                  className="flex cursor-pointer items-start gap-4 px-6 py-4 transition-colors hover:bg-gray-50"
                  onClick={() => router.push(`/normativos/${item.id}`)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge fonte={item.fonte} />
                      <Badge tipo={item.tipo} />
                      <Badge setor={item.setor} />
                      {item.impacto && <ImpactoBadge impacto={item.impacto} />}
                    </div>
                    <p className="text-sm font-medium text-gray-900 line-clamp-2">{item.titulo}</p>
                    {item.ementa && (
                      <p className="mt-1 text-xs text-gray-500 line-clamp-2">{item.ementa}</p>
                    )}
                    {item.data_publicacao && (
                      <p className="mt-1 text-xs text-gray-400">
                        {format(new Date(item.data_publicacao), "d 'de' MMMM 'de' yyyy", {
                          locale: ptBR,
                        })}
                      </p>
                    )}
                  </div>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="ml-2 flex-shrink-0 text-gray-400 hover:text-navy-700"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {recentes && recentes.total > 10 && (
          <div className="border-t border-gray-100 px-6 py-3 text-center">
            <button
              onClick={() => router.push("/normativos")}
              className="text-sm font-medium text-navy-700 hover:text-navy-900"
            >
              Ver todos os {recentes.total.toLocaleString()} normativos →
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}
