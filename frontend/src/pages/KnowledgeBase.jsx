import React, { useState, useEffect } from 'react';
import { getDocuments, getDocumentChunks, getChunkEmbedding, getStats } from '../services/api';
import { FileText, ArrowRight, Layers, Table as TableIcon } from 'lucide-react';

const KnowledgeBase = () => {
  const [docs, setDocs] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [selectedChunk, setSelectedChunk] = useState(null);
  const [embedding, setEmbedding] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    getDocuments().then(data => setDocs(data.documents));
    getStats().then(setStats);
  }, []);

  const handleSelectDoc = async (docName) => {
    setSelectedDoc(docName);
    setSelectedChunk(null);
    setEmbedding(null);
    const data = await getDocumentChunks(docName);
    setChunks(data.chunks);
  };

  const handleSelectChunk = async (chunk) => {
    setSelectedChunk(chunk);
    const data = await getChunkEmbedding(chunk.chunk_id);
    setEmbedding(data.embedding);
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>Knowledge Base</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Exercise 2: Observe how documents are transformed into machine-readable knowledge.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
        
        {/* DOCUMENT EXPLORER */}
        <div>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
            1. Documents
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {docs.map(doc => (
              <div 
                key={doc.filename} 
                className="card"
                onClick={() => handleSelectDoc(doc.filename)}
                style={{ 
                  cursor: 'pointer', 
                  padding: '1rem',
                  borderColor: selectedDoc === doc.filename ? 'var(--text-primary)' : 'var(--border-color)',
                  background: selectedDoc === doc.filename ? '#1a1a1a' : 'var(--panel-bg)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500, marginBottom: '0.5rem' }}>
                  <FileText size={16} />
                  {doc.filename}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem' }}>
                  <div>Type: {doc.type}</div>
                  <div>Pages: {doc.page_count}</div>
                  <div>Extraction: {doc.extraction_method.toUpperCase()}</div>
                  <div>Tables: {doc.table_count}</div>
                  <div>Chunks: {doc.chunk_count}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CHUNKS & EMBEDDINGS */}
        <div>
          {selectedDoc ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              
              <div>
                <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                  2. Document Chunks ({chunks.length})
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto', paddingRight: '1rem' }}>
                  {chunks.map(chunk => (
                    <div 
                      key={chunk.chunk_id} 
                      className="card"
                      onClick={() => handleSelectChunk(chunk)}
                      style={{ 
                        cursor: 'pointer',
                        padding: '0.75rem',
                        fontSize: '0.85rem',
                        borderColor: selectedChunk?.chunk_id === chunk.chunk_id ? 'var(--text-primary)' : 'var(--border-color)',
                        background: selectedChunk?.chunk_id === chunk.chunk_id ? '#262626' : 'var(--panel-bg)'
                      }}
                    >
                      <div style={{ color: 'var(--text-secondary)', marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                        {chunk.chunk_id}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        {chunk.content_type === 'table' ? <TableIcon size={14} /> : <Layers size={14} />}
                        Page {chunk.page_start}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {selectedChunk && (
                <div>
                  <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                    3. Chunk Detail & Embedding
                  </h2>
                  <div className="card" style={{ marginBottom: '1rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                      <div><strong>Document:</strong> {selectedChunk.document_name}</div>
                      <div><strong>Page:</strong> {selectedChunk.page_start}</div>
                      <div><strong>Section:</strong> {selectedChunk.section}</div>
                      <div><strong>ID:</strong> {selectedChunk.chunk_id}</div>
                      <div><strong>Type:</strong> {selectedChunk.content_type.toUpperCase()}</div>
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', lineHeight: 1.6, maxHeight: '200px', overflowY: 'auto', fontFamily: selectedChunk.content_type === 'table' ? 'monospace' : 'inherit' }}>
                      {selectedChunk.text}
                    </div>
                  </div>

                  {embedding ? (
                    <div className="card" style={{ background: '#0a0a0a', border: '1px solid #333' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <div style={{ fontSize: '0.9rem', fontWeight: 500 }}>Vector Embedding</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          Model: {stats?.embedding_model || 'all-MiniLM-L6-v2'} | Dim: {embedding.length}
                        </div>
                      </div>
                      <div style={{ 
                        fontFamily: 'monospace', 
                        fontSize: '0.75rem', 
                        color: 'var(--text-secondary)', 
                        background: '#000', 
                        padding: '1rem', 
                        borderRadius: '4px',
                        wordBreak: 'break-all',
                        lineHeight: 1.8
                      }}>
                        <details>
                          <summary style={{ cursor: 'pointer', outline: 'none', color: 'var(--text-primary)' }}>
                            [{embedding.slice(0, 8).map(v => v.toFixed(4)).join(', ')}, ... click to expand 384 dimensions]
                          </summary>
                          <div style={{ marginTop: '0.5rem', color: '#666' }}>
                            [{embedding.map(v => v.toFixed(4)).join(', ')}]
                          </div>
                        </details>
                      </div>

                      <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginBottom: '0.25rem', fontWeight: 'bold' }}>
                          Coordinate scatter of embedding dimensions 0–49
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#666', marginBottom: '0.5rem' }}>
                          Note: This is NOT a PCA or t-SNE projection. Each point = (dim[i], dim[i+1]) for i=0..48.
                          It shows the distribution of values across early dimensions, not a true 2D semantic space.
                        </div>
                        <div style={{ position: 'relative', width: '100%', height: '150px', border: '1px solid #333', borderRadius: '4px', background: 'radial-gradient(circle, #111 0%, #000 100%)', overflow: 'hidden' }}>
                           {/* A pseudo-random plot of vector elements simulating a latent space projection */}
                           {embedding.slice(0, 50).map((val, idx) => {
                             const x = 50 + (val * 200); // Scale typical -0.2 to 0.2 to percentage
                             const y = 50 + (embedding[idx+1] * 200 || 0);
                             return (
                               <div key={idx} style={{
                                 position: 'absolute',
                                 left: `${Math.max(5, Math.min(95, x))}%`,
                                 top: `${Math.max(5, Math.min(95, y))}%`,
                                 width: idx === 0 ? '8px' : '4px',
                                 height: idx === 0 ? '8px' : '4px',
                                 background: idx === 0 ? 'var(--accent-color)' : '#444',
                                 borderRadius: '50%',
                                 transform: 'translate(-50%, -50%)',
                                 boxShadow: idx === 0 ? '0 0 10px var(--accent-color)' : 'none'
                               }} />
                             );
                           })}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Loading embedding...</div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>
              Select a document to inspect its chunks
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBase;
