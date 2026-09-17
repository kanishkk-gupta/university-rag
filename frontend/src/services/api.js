import axios from 'axios';

// API base URL configuration
export const API_URL = import.meta.env.VITE_API_URL || '/api';
export const BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getHealth = async () => {
  const response = await axios.get(`${BASE_URL}/health`);
  return response.data;
};

// BUG FIX: Added top_k and model_name parameters that were previously missing
export const chatWithRAG = async (query, use_rag = true, top_k = null, model_name = null) => {
  const payload = { query, use_rag };
  if (top_k) payload.top_k = top_k;
  if (model_name) payload.model_name = model_name;
  const response = await api.post('/chat', payload);
  return response.data;
};

export const retrieveChunks = async (query, top_k = 5) => {
  const response = await api.post('/retrieve', { query, top_k });
  return response.data;
};

export const getDocuments = async () => {
  const response = await api.get('/documents');
  return response.data;
};

export const getStats = async () => {
  const response = await api.get('/stats');
  return response.data;
};

export const getDocumentChunks = async (document_name) => {
  const response = await api.get(`/documents/${document_name}/chunks`);
  return response.data;
};

export const getChunk = async (chunk_id) => {
  const response = await api.get(`/chunks/${chunk_id}`);
  return response.data;
};

export const getChunkEmbedding = async (chunk_id) => {
  const response = await api.get(`/chunks/${chunk_id}/embedding`);
  return response.data;
};

export const embedQuery = async (query) => {
  const response = await api.post('/query-embedding', { query });
  return response.data;
};

// Codebase API functions (previously missing — pages used raw axios with hardcoded paths)
export const codebaseQuery = async (query, top_k = 5, model_name = null) => {
  const payload = { query, top_k };
  if (model_name) payload.model_name = model_name;
  const response = await api.post('/codebase/query', payload);
  return response.data;
};

export const codebaseStats = async () => {
  const response = await api.get('/codebase/stats');
  return response.data;
};

// Evaluation API functions (previously missing — pages used raw axios with hardcoded paths)
export const getEvalDataset = async () => {
  const response = await api.get('/evaluation/dataset');
  return response.data;
};

export const getEvalResults = async () => {
  const response = await api.get('/evaluation/results');
  return response.data;
};

export const getEvalSummary = async () => {
  const response = await api.get('/evaluation/summary');
  return response.data;
};

export const runEvaluation = async () => {
  const response = await api.post('/evaluation/run');
  return response.data;
};

export const getEvalCategorySummary = async () => {
  const response = await api.get('/evaluation/category-summary');
  return response.data;
};

// Guardrail API functions
export const checkGuardrail = async (query) => {
  const response = await api.post('/guardrails/check', { query });
  return response.data;
};

export const runGuardrailTests = async () => {
  const response = await api.get('/guardrails/test');
  return response.data;
};

export default api;
