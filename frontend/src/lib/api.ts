import { DocumentItem, FactItem, RelationshipItem, ReviewCasesResponse, PipelineStatus } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE
  || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000/api' : '/api');

async function handleResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    let errorMsg = `Server returned status ${res.status}`;
    try {
      const json = JSON.parse(text);
      errorMsg = json.detail || json.message || errorMsg;
    } catch {
      if (text && text.length < 300) {
        errorMsg = text;
      }
    }
    throw new Error(errorMsg);
  }

  try {
    return JSON.parse(text) as T;
  } catch (err) {
    throw new Error('Invalid JSON response received from server.');
  }
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/documents`);
  return handleResponse<DocumentItem[]>(res);
}

export async function fetchFacts(params?: {
  status?: string;
  document_id?: string;
  relationship_type?: string;
}): Promise<FactItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.append('status', params.status);
  if (params?.document_id) query.append('document_id', params.document_id);
  if (params?.relationship_type) query.append('relationship_type', params.relationship_type);

  const res = await fetch(`${API_BASE}/facts?${query.toString()}`);
  return handleResponse<FactItem[]>(res);
}

export async function fetchRelationships(type?: string): Promise<RelationshipItem[]> {
  const url = type ? `${API_BASE}/relationships?type=${type}` : `${API_BASE}/relationships`;
  const res = await fetch(url);
  return handleResponse<RelationshipItem[]>(res);
}

export async function fetchReviewCases(): Promise<ReviewCasesResponse> {
  const res = await fetch(`${API_BASE}/review/cases`);
  return handleResponse<ReviewCasesResponse>(res);
}


export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    body: formData,
  });

  return handleResponse<DocumentItem>(res);
}


export async function deleteDocument(documentId: string): Promise<{
  success: boolean;
  deleted_document_id: string;
  deleted_facts: number;
  deleted_relationships: number;
}> {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, { method: 'DELETE' });
  return handleResponse(res);
}

export async function reprocessDocument(documentId: string): Promise<DocumentItem> {
  const res = await fetch(`${API_BASE}/documents/${documentId}/reprocess`, { method: 'POST' });
  return handleResponse<DocumentItem>(res);
}

export async function fetchPipelineStatus(documentId: string): Promise<PipelineStatus> {
  const res = await fetch(`${API_BASE}/documents/${documentId}/pipeline`);
  return handleResponse<PipelineStatus>(res);
}
