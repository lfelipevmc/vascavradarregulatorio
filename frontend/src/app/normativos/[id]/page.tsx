"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  ArrowLeft,
  ExternalLink,
  Calendar,
  Tag,
  Zap,
  FileText,
  Brain,
} from "lucide-react";
import { api } from "@/lib/api";
import { Badge, ImpactoBadge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";

export default function NormativoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data: normativo, isLoading, isError } = useQuery({
    queryKey: ["normativo", id],
    queryFn: () => api.getNormativo(Number(id)),
    enabled: !!id,
  });

  if (isLoading) return <LoadingState message="Carregando normativo..." />;

  if (isError || !normativo) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Normativo não encontrado.</p>
        <button
          onClick={() => router.back()}
          className="mt-4 text-sm text-navy-700 hover:underline"
        >
          Voltar
        </button>
      </div>
    );
  }

  const impactoNivel = normativo.impacto?.split(":")[0] || "";
  const impactoDescricao = normativo.impacto?.split(":").slice(1).join(":").trim() || "";

  return (
    <div className="mx-auto max-w-4xl p-6">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="mb-6 flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </button>

      {/* Header card */}
      <Card className="mb-6">
        <div className="p-6">
          {/* Badges row */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Badge fonte={normativo.fonte} />
            <Badge tipo={normativo.tipo} />
            <Badge setor={normativo.setor} />
            {normativo.impacto && <ImpactoBadge impacto={normativo.impacto} />}
            {normativo.processado_ia && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                <Brain className="h-3 w-3" />
                Processado por IA
              </span>
            )}
          </div>

          {/* Title */}
          <h1 className="text-xl font-bold text-gray-900">{normativo.titulo}</h1>

          {/* Metadata row */}
          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-gray-500">
            {normativo.numero && (
              <div className="flex items-center gap-1">
                <FileText className="h-3.5 w-3.5" />
                <span>{normativo.numero}</span>
              </div>
            )}
            {normativo.data_publicacao && (
              <div className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                <span>
                  {format(new Date(normativo.data_publicacao), "d 'de' MMMM 'de' yyyy", {
                    locale: ptBR,
                  })}
                </span>
              </div>
            )}
            {normativo.url && (
              <a
                href={normativo.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-navy-700 hover:text-navy-900"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Documento original
              </a>
            )}
          </div>
        </div>
      </Card>

      {/* AI Summary */}
      {normativo.resumo_ia && (
        <Card className="mb-6">
          <div className="border-b border-gray-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-navy-700" />
              <h2 className="text-sm font-semibold text-gray-900">Resumo por IA</h2>
            </div>
          </div>
          <div className="px-6 py-4">
            <p className="text-sm leading-relaxed text-gray-700">{normativo.resumo_ia}</p>
          </div>
        </Card>
      )}

      {/* Ementa */}
      {normativo.ementa && (
        <Card className="mb-6">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2 className="text-sm font-semibold text-gray-900">Ementa</h2>
          </div>
          <div className="px-6 py-4">
            <p className="text-sm leading-relaxed text-gray-700 italic">{normativo.ementa}</p>
          </div>
        </Card>
      )}

      {/* Impact */}
      {normativo.impacto && (
        <Card className="mb-6">
          <div className="border-b border-gray-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-gold-600" />
              <h2 className="text-sm font-semibold text-gray-900">Análise de Impacto</h2>
            </div>
          </div>
          <div className="px-6 py-4">
            <div className="flex items-start gap-3">
              <ImpactoBadge impacto={normativo.impacto} />
              {impactoDescricao && (
                <p className="text-sm leading-relaxed text-gray-700">{impactoDescricao}</p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Tags */}
      {normativo.tags && normativo.tags.length > 0 && (
        <Card className="mb-6">
          <div className="border-b border-gray-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <Tag className="h-4 w-4 text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-900">Tags</h2>
            </div>
          </div>
          <div className="px-6 py-4">
            <div className="flex flex-wrap gap-2">
              {normativo.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-lg bg-navy-50 px-3 py-1 text-sm text-navy-700"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Raw content (collapsed) */}
      {normativo.conteudo_bruto && (
        <Card>
          <details className="group">
            <summary className="flex cursor-pointer select-none items-center justify-between border-b border-gray-100 px-6 py-4 group-open:border-b">
              <h2 className="text-sm font-semibold text-gray-900">Conteúdo Bruto</h2>
              <span className="text-xs text-gray-500">Clique para expandir</span>
            </summary>
            <div className="px-6 py-4">
              <pre className="whitespace-pre-wrap text-xs leading-relaxed text-gray-600 font-mono">
                {normativo.conteudo_bruto}
              </pre>
            </div>
          </details>
        </Card>
      )}
    </div>
  );
}
