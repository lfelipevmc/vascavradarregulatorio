"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { ExternalLink, Filter, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, useCallback, Suspense } from "react";
import {
  api,
  type FonteNormativo,
  type SetorNormativo,
  type TipoNormativo,
  type NormativoListItem,
} from "@/lib/api";
import { Badge, ImpactoBadge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { SearchBar } from "@/components/ui/SearchBar";

const FONTES: { value: FonteNormativo; label: string }[] = [
  { value: "DOU", label: "DOU" },
  { value: "ANEEL", label: "ANEEL" },
  { value: "ANTT", label: "ANTT" },
  { value: "ANAC", label: "ANAC" },
  { value: "ANATEL", label: "ANATEL" },
  { value: "ANM", label: "ANM" },
  { value: "TCU", label: "TCU" },
  { value: "CAMARA", label: "Câmara" },
  { value: "SENADO", label: "Senado" },
  { value: "STJ", label: "STJ" },
  { value: "STF", label: "STF" },
];

const SETORES: { value: SetorNormativo; label: string }[] = [
  { value: "ENERGIA", label: "Energia" },
  { value: "TRANSPORTE", label: "Transporte" },
  { value: "AVIACAO", label: "Aviação" },
  { value: "MINERACAO", label: "Mineração" },
  { value: "TELECOMUNICACOES", label: "Telecomunicações" },
  { value: "SANEAMENTO", label: "Saneamento" },
  { value: "ESPORTE", label: "Esporte" },
  { value: "GERAL", label: "Geral" },
];

const TIPOS: { value: TipoNormativo; label: string }[] = [
  { value: "LEI", label: "Lei" },
  { value: "DECRETO", label: "Decreto" },
  { value: "PORTARIA", label: "Portaria" },
  { value: "RESOLUCAO", label: "Resolução" },
  { value: "INSTRUCAO_NORMATIVA", label: "Instrução Normativa" },
  { value: "MEDIDA_PROVISORIA", label: "Medida Provisória" },
  { value: "ACORDAO_TCU", label: "Acórdão TCU" },
  { value: "PROJETO_LEI", label: "Projeto de Lei" },
  { value: "PRECEDENTE_JUDICIAL", label: "Precedente Judicial" },
];

function NormativosContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState({
    fonte: (searchParams.get("fonte") as FonteNormativo) || undefined,
    setor: (searchParams.get("setor") as SetorNormativo) || undefined,
    tipo: (searchParams.get("tipo") as TipoNormativo) || undefined,
    q: searchParams.get("q") || "",
    page: Number(searchParams.get("page") || "1"),
    page_size: 20,
  });

  const updateFilter = useCallback(
    (key: string, value: string | undefined) => {
      setFilters((prev) => ({ ...prev, [key]: value || undefined, page: 1 }));
    },
    []
  );

  const { data, isLoading } = useQuery({
    queryKey: ["normativos", filters],
    queryFn: () => api.listNormativos(filters),
    keepPreviousData: true,
  } as Parameters<typeof useQuery>[0]);

  return (
    <div className="flex gap-0">
      {/* Filters sidebar */}
      <aside className="w-56 flex-shrink-0 border-r border-gray-200 bg-white p-4">
        <div className="mb-4 flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-500" />
          <h2 className="text-sm font-semibold text-gray-900">Filtros</h2>
        </div>

        {/* Fonte filter */}
        <div className="mb-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Fonte
          </p>
          <div className="space-y-1">
            <button
              onClick={() => updateFilter("fonte", undefined)}
              className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                !filters.fonte
                  ? "bg-navy-700 text-white"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              Todas
            </button>
            {FONTES.map((f) => (
              <button
                key={f.value}
                onClick={() => updateFilter("fonte", f.value)}
                className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                  filters.fonte === f.value
                    ? "bg-navy-700 text-white"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Setor filter */}
        <div className="mb-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Setor
          </p>
          <div className="space-y-1">
            <button
              onClick={() => updateFilter("setor", undefined)}
              className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                !filters.setor
                  ? "bg-navy-700 text-white"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              Todos
            </button>
            {SETORES.map((s) => (
              <button
                key={s.value}
                onClick={() => updateFilter("setor", s.value)}
                className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                  filters.setor === s.value
                    ? "bg-navy-700 text-white"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tipo filter */}
        <div className="mb-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Tipo
          </p>
          <div className="space-y-1">
            <button
              onClick={() => updateFilter("tipo", undefined)}
              className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                !filters.tipo
                  ? "bg-navy-700 text-white"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              Todos
            </button>
            {TIPOS.map((t) => (
              <button
                key={t.value}
                onClick={() => updateFilter("tipo", t.value)}
                className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                  filters.tipo === t.value
                    ? "bg-navy-700 text-white"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 overflow-hidden p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Normativos</h1>
            {data && (
              <p className="mt-0.5 text-sm text-gray-500">
                {data.total.toLocaleString()} resultado{data.total !== 1 ? "s" : ""}
              </p>
            )}
          </div>
          <SearchBar
            value={filters.q}
            onChange={(q) => updateFilter("q", q)}
            placeholder="Buscar título, ementa..."
            className="w-72"
          />
        </div>

        {isLoading ? (
          <LoadingState />
        ) : (
          <>
            <Card>
              <div className="divide-y divide-gray-50">
                {data?.items.length === 0 ? (
                  <div className="px-6 py-16 text-center text-sm text-gray-500">
                    Nenhum normativo encontrado com os filtros selecionados.
                  </div>
                ) : (
                  data?.items.map((item: NormativoListItem) => (
                    <div
                      key={item.id}
                      className="flex cursor-pointer items-start gap-4 px-6 py-4 transition-colors hover:bg-gray-50"
                      onClick={() => router.push(`/normativos/${item.id}`)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="mb-2 flex flex-wrap items-center gap-1.5">
                          <Badge fonte={item.fonte} />
                          <Badge tipo={item.tipo} />
                          <Badge setor={item.setor} />
                          {item.impacto && <ImpactoBadge impacto={item.impacto} />}
                          {!item.processado_ia && (
                            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                              Pendente IA
                            </span>
                          )}
                        </div>
                        <p className="text-sm font-medium text-gray-900 line-clamp-2">
                          {item.titulo}
                        </p>
                        {(item.resumo_ia || item.ementa) && (
                          <p className="mt-1 text-xs text-gray-500 line-clamp-2">
                            {item.resumo_ia || item.ementa}
                          </p>
                        )}
                        {item.tags && item.tags.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {item.tags.slice(0, 5).map((tag) => (
                              <span
                                key={tag}
                                className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                        {item.data_publicacao && (
                          <p className="mt-1 text-xs text-gray-400">
                            {format(new Date(item.data_publicacao), "d MMM yyyy", { locale: ptBR })}
                          </p>
                        )}
                      </div>
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex-shrink-0 text-gray-400 hover:text-navy-700"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  ))
                )}
              </div>
            </Card>

            {/* Pagination */}
            {data && data.pages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-gray-500">
                  Página {data.page} de {data.pages}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setFilters((p) => ({ ...p, page: p.page - 1 }))}
                    disabled={data.page <= 1}
                    className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Anterior
                  </button>
                  <button
                    onClick={() => setFilters((p) => ({ ...p, page: p.page + 1 }))}
                    disabled={data.page >= data.pages}
                    className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Próxima
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function NormativosPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <NormativosContent />
    </Suspense>
  );
}
