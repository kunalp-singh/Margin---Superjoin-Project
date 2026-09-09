export interface DocumentItem {
  id: string;
  filename: string;
  uploaded_at: string;
  page_count: number;
  status: 'queued' | 'processing' | 'done' | 'failed';
  error_message?: string | null;
  fact_count: number;
  pipeline_version?: string;
  current_stage?: string | null;
  stage_status?: Record<string, { status: string; detail?: string; attempts?: number }>;
  retry_count?: number;
  pipeline_started_at?: string | null;
  pipeline_completed_at?: string | null;
}

export interface PipelineStage {
  name: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  attempts: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  detail?: Record<string, any>;
}

export interface PipelineStatus {
  document_id: string;
  pipeline_version: string;
  status: string;
  current_stage?: string | null;
  retry_count: number;
  error_message?: string | null;
  stages: PipelineStage[];
}

export interface FactItem {
  id: string;
  document_id: string;
  document_filename?: string;
  page_number: number;
  source_quote: string;
  char_start: number;
  char_end: number;
  attributes: Record<string, any>;
  normalized_signature: string;
  status: 'normal' | 'uncertain';
  uncertainty_reason?: string | null;
  created_at: string;
  pipeline_version?: string;
}

export interface ReasoningTrace {
  same_entity?: boolean;
  same_metric?: boolean;
  same_period?: boolean;
  same_unit?: boolean;
  same_scope?: boolean;
  same_qualifier?: boolean;
  reconciliation_dimension?: string | null;
  reasoning_steps?: string[];
  summary?: string;
  checklist?: {
    entity: boolean;
    metric: boolean;
    period: boolean;
    unit: boolean;
    scope: boolean;
    qualifier: boolean;
  };
  evidence_confidence?: number;
}

export interface RelationshipItem {
  id: string;
  fact_a_id: string;
  fact_b_id: string;
  type: 'corroborated' | 'contradicted' | 'reconciled' | 'uncertain';
  confidence: number;
  reasoning: ReasoningTrace;
  created_at: string;
  fact_a?: FactItem;
  fact_b?: FactItem;
  pipeline_version?: string;
}

export interface ReviewCase {
  relationship_id?: string | null;
  type: 'corroborated' | 'contradicted' | 'reconciled' | 'uncertain';
  confidence: number;
  reasoning: ReasoningTrace;
  fact_a?: FactItem;
  fact_b?: FactItem;
}

export interface ReviewCasesResponse {
  cases: {
    corroborated?: ReviewCase | null;
    contradicted?: ReviewCase | null;
    reconciled?: ReviewCase | null;
    uncertain?: ReviewCase | null;
  };
  available_counts: {
    corroborated: number;
    contradicted: number;
    reconciled: number;
    uncertain: number;
  };
}
