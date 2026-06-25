import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

export const apiClient = axios.create({
  baseURL: `${API_BASE}${API_PREFIX}`,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Types mirroring backend schemas
export type TipoNormativo =
  | "LEI"
  | "DECRETO"
  | "PORTARIA"
  | "RESOLUCAO"
  | "INSTRUCAO_NORMATIVA"
  | "MEDIDA_PROVISORIA"
  | "ACORDAO_TCU"
  | "PROJETO_LEI"
  | "PRECEDENTE_JUDICIAL";

export type FonteNormativo =
  | "DOU"
  | "ANEEL"
  | "ANTT"
  | "ANAC"
  | "ANATEL"
  | "ANM"
  | "TCU"
  | "CAMARA"
  | "SENADO"
  | "STJ"
  | "STF"
  | "TRF";

export type SetorNormativo =
  | "ENERGIA"
  | "TRANSPORTE"
  | "AVIACAO"
  | "MINERACAO"
  | "TELECOMUNICACOES"
  | "ESPORTE"
  | "SANEAMENTO"
  | "GERAL";

export interface NormativoListItem {
  id: number;
  titulo: string;
  tipo: TipoNormativo;
  numero: string | null;
  data_publicacao: string | null;
  fonte: FonteNormativo;
  setor: SetorNormativo;
  url: string | null;
  ementa: string | null;
  resumo_ia: string | null;
  impacto: string | null;
  tags: string[] | null;
  processado_ia: boolean;
  created_at: string;
}

export interface NormativoDetail extends NormativoListItem {
  conteudo_bruto: string | null;
  embedding: Record<string, unknown> | null;
  updated_at: string;
}

export interface NormativoStats {
  total: number;
  novos_hoje: number;
  por_fonte: Record<string, number>;
  por_setor: Record<string, number>;
  por_tipo: Record<string, number>;
  processados_ia: number;
  pendentes_ia: number;
}

export interface PaginatedResponse {
  items: NormativoListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface NormativoFilters {
  fonte?: FonteNormativo;
  setor?: SetorNormativo;
  tipo?: TipoNormativo;
  data_inicio?: string;
  data_fim?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

// API functions
export const api = {
  async getStats(): Promise<NormativoStats> {
    const { data } = await apiClient.get<NormativoStats>("/normativos/stats");
    return data;
  },

  async listNormativos(filters: NormativoFilters = {}): Promise<PaginatedResponse> {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== undefined && v !== "")
    );
    const { data } = await apiClient.get<PaginatedResponse>("/normativos", { params });
    return data;
  },

  async getNormativo(id: number): Promise<NormativoDetail> {
    const { data } = await apiClient.get<NormativoDetail>(`/normativos/${id}`);
    return data;
  },

  async checkHealth(): Promise<{ status: string; database: string }> {
    const { data } = await axios.get(`${API_BASE}/health`);
    return data;
  },
};
