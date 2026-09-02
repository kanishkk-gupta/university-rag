import React, { useState, useEffect } from 'react';
import { codebaseQuery, codebaseStats } from '../services/api';
import { Loader2 } from 'lucide-react';

const Codebase = () => {
  const [query, setQuery] = useState('What is the complete flow from the React chat interface to Code Llama?');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [selectedChunk, setSelectedChunk] = useState(null);

  const PRESET_QUERIES = [
    'Which files are responsible for the RAG pipeline?',
    'What happens after a user submits a question?',
    'Which component calls Ollama?',
    'Where are embeddings generated?',
    'Which files participate in the chat API request?',
    'What is the complete flow from the React chat interface to Code Llama?',
  ];

  useEffect(() => {
    codebaseStats().then(setStats).catch(() => {});
  }, []);

  const handleQuery = async (q) => {
    const queryText = q || query;
    if (!queryText.trim()) return;
    setLoading(true);
    setResult(null);
    setSelectedChunk(null);
    try {
      const res = await codebaseQuery(queryText, 5);
      setResult(res);
    } catch (e) {
      setResult({ answer: `Error: ${e.message}`, sources: [], retrieved_chunks: [] });
    }
    setLoading(false);
  };

  const langColor = { py: '#3b82f6', js: '#f59e0b', jsx: '#06b6d4' };

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ marginBottom: '0.5rem' }}>Codebase Understanding</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Exercise 7: RAG applied to the application's own source code. The same pipeline used for BMU documents
          is applied to the repository itself, enabling multi-file reasoning about the codebase.
        </p>
      </div>

      {/* Two collections comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ padding: '1rem', border: '1px solid var(--border-color)', background: 'var(--panel-bg)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>UNIVERSITY KNOWLEDGE BASE</div>
          <div style={{ fontWeight: 600 }}>Collection: <code style={{ color: '#4ade80' }}>bmu_documents</code></div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>BMU policy PDFs · OCR/native text · 1,800-char chunks</div>
        </div>
        <div style={{ padding: '1rem', border: '1px solid #3b82f6', background: '#0a0f1e' }}>
          <div style={{ fontSize: '0.75rem', color: '#60a5fa', marginBottom: '0.25rem' }}>CODEBASE KNOWLEDGE BASE</div>
          <div style={{ fontWeight: 600 }}>Collection: <code style={{ color: '#60a5fa' }}>bmu_codebase</code></div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            {stats ? `${stats.indexed_chunks} chunks · ` : ''}Python + JSX source · 50-line chunks · same embedder
          </div>
        </div>
      </div>

      {/* Indexed directories */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', fontWeight: 600 }}>INDEXED DIRECTORIES</div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', fontSize: '0.8rem' }}>
          {['api/', 'rag/', 'retrieval/', 'embeddings/', 'vectorstore/', 'ingestion/', 'frontend/src/'].map(d => (
            <code key={d} style={{ background: '#111', padding: '0.25rem 0.6rem', border: '1px solid #333' }}>{d}</code>
          ))}
        </div>
        <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: '#666' }}>
          Excluded: node_modules, venv, .git, __pycache__, dist, build · File types: .py .js .jsx
        </div>
      </div>

      {/* Query section */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', fontWeight: 600 }}>PRESET QUERIES</div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
          {PRESET_QUERIES.map(q => (
            <button
              key={q}
              onClick={() => { setQuery(q); handleQuery(q); }}
              style={{
                padding: '0.4rem 0.75rem',
                fontSize: '0.78rem',
                background: 'var(--panel-bg)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-color)',
                cursor: 'pointer',
                textAlign: 'left',
                maxWidth: '300px',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = '#555'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
            >
              {q}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleQuery()}
            placeholder="Ask a question about the repository..."
            className="input"
            style={{ flex: 1 }}
          />
          <button className="btn" onClick={() => handleQuery()} disabled={loading}>
            {loading ? <><Loader2 size={14} className="spin" /> Searching...</> : 'Search Codebase'}
          </button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }} className="fade-in">
          {/* LEFT: LLM Answer */}
          <div>
            <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              LLM Answer
            </h2>
            <div className="card" style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6', fontSize: '0.9rem' }}>
              {result.answer}
            </div>

            {/* File citations */}
            {result.sources && result.sources.length > 0 && (
              <div style={{ marginTop: '1.5rem' }}>
                <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                  FILE CITATIONS ({result.sources.length} files retrieved)
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {result.sources.map((s, i) => (
                    <div
                      key={i}
                      onClick={() => setSelectedChunk(result.retrieved_chunks?.[i])}
                      style={{
                        padding: '0.6rem 0.8rem',
                        border: `1px solid ${selectedChunk === result.retrieved_chunks?.[i] ? 'var(--text-primary)' : 'var(--border-color)'}`,
                        background: selectedChunk === result.retrieved_chunks?.[i] ? '#1a1a1a' : 'var(--panel-bg)',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontFamily: 'monospace',
                        transition: 'all 0.15s',
                      }}
                    >
                      <span style={{ color: langColor[s.file_path?.split('.').pop()] || '#888', marginRight: '0.5rem' }}>
                        [{s.file_path?.split('.').pop()?.toUpperCase()}]
                      </span>
                      <strong>{s.file_path}</strong>
                      <span style={{ color: 'var(--text-secondary)', marginLeft: '0.5rem' }}>
                        Lines {s.start_line}–{s.end_line}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* RIGHT: Retrieved Code Chunks */}
          <div>
            <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              Retrieved Code Chunks ({result.retrieved_chunks?.length || 0})
            </h2>

            {selectedChunk ? (
              <div>
                <button
                  onClick={() => setSelectedChunk(null)}
                  style={{ marginBottom: '1rem', background: 'none', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.3rem 0.6rem', cursor: 'pointer', fontSize: '0.8rem' }}
                >
                  ← Back to all chunks
                </button>
                <div style={{ border: '1px solid var(--border-color)', padding: '1rem', background: '#050505' }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', display: 'flex', gap: '1.5rem' }}>
                    <span>File: <strong style={{ color: 'var(--text-primary)' }}>{selectedChunk.metadata?.file_path}</strong></span>
                    <span>Lines: {selectedChunk.metadata?.start_line}–{selectedChunk.metadata?.end_line}</span>
                    <span>Language: {selectedChunk.metadata?.language?.toUpperCase()}</span>
                    <span>Distance: {selectedChunk.distance?.toFixed(4)}</span>
                  </div>
                  <pre style={{ margin: 0, fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'pre-wrap', color: '#c9d1d9', lineHeight: 1.5, maxHeight: '500px', overflowY: 'auto' }}>
                    {selectedChunk.text}
                  </pre>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {(result.retrieved_chunks || []).map((chunk, i) => (
                  <div
                    key={i}
                    onClick={() => setSelectedChunk(chunk)}
                    style={{
                      border: '1px solid var(--border-color)',
                      padding: '0.75rem',
                      cursor: 'pointer',
                      background: 'var(--panel-bg)',
                      transition: 'border-color 0.15s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--text-primary)'}
                    onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>#{i + 1}</span>
                      <span style={{ fontSize: '0.78rem', fontFamily: 'monospace', fontWeight: 600, color: langColor[chunk.metadata?.language] || 'var(--text-primary)' }}>
                        {chunk.metadata?.file_path}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                        Lines {chunk.metadata?.start_line}–{chunk.metadata?.end_line} · dist {chunk.distance?.toFixed(4)}
                      </span>
                    </div>
                    <pre style={{ margin: 0, fontSize: '0.72rem', color: '#888', whiteSpace: 'pre-wrap', maxHeight: '80px', overflow: 'hidden', lineHeight: 1.4 }}>
                      {chunk.text?.slice(0, 200)}{chunk.text?.length > 200 ? '...' : ''}
                    </pre>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: '#555' }}>Click to inspect full chunk</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Codebase;
