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

export const chatWithRAG = async (query, use_rag = true) => {
  const response = await api.post('/chat', { query, use_rag });
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

export default api;
