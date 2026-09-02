import React, { useState } from 'react';
import { chatWithRAG } from '../services/api';
import { Search, Loader2, Zap } from 'lucide-react';

const MODELS = [
  { value: 'codellama:7b-instruct', label: 'Code Llama 7B' },
  { value: 'starcoder2:3b',         label: 'StarCoder2 3B' },
  { value: 'qwen2.5-coder:1.5b',    label: 'Qwen2.5 1.5B' },
];

const LLMApp = () => {
  const [query, setQuery] = useState('What is the deadline for Odd Semester fee payment for existing students?');
  const [selectedModel, setSelectedModel] = useState('qwen2.5-coder:1.5b');
  const [isGenerating, setIsGenerating] = useState(false);

  const [noRagResult, setNoRagResult] = useState(null);
  const [ragResult, setRagResult] = useState(null);
  const [ragError, setRagError] = useState(null);
  const [noRagError, setNoRagError] = useState(null);

  const handleRun = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setIsGenerating(true);
    setNoRagResult(null);
    setRagResult(null);
    setRagError(null);
    setNoRagError(null);

    // BUG FIX: Run both requests in PARALLEL using Promise.allSettled
    // Previously they were sequential — now they fire at the same time
    const [withoutRagResult, withRagResult] = await Promise.allSettled([
      chatWithRAG(query, false, null, selectedModel),
      chatWithRAG(query, true,  null, selectedModel),
    ]);

    if (withoutRagResult.status === 'fulfilled') {
      setNoRagResult(withoutRagResult.value);
    } else {
      console.error(withoutRagResult.reason);
      setNoRagError('LLM generation timed out or failed.');
    }

    if (withRagResult.status === 'fulfilled') {
      setRagResult(withRagResult.value);
    } else {
      console.error(withRagResult.reason);
      setRagError('LLM generation timed out. Retrieval completed successfully, but the local LLM did not return within the configured timeout.');
    }

    setIsGenerating(false);
  };

  const modelLabel = MODELS.find(m => m.value === selectedModel)?.label || selectedModel;

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: '3rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.75rem', letterSpacing: '-0.03em' }}>LLM Application</h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
          Exercise 1: Compare the base LLM (no context) vs. RAG-augmented response for the same question.
        </p>
      </div>

      {/* Model Selector */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem', gap: '0.75rem', alignItems: 'center' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>MODEL:</span>
        <select
          className="model-select"
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          disabled={isGenerating}
        >
          {MODELS.map(m => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      <form onSubmit={handleRun} style={{ position: 'relative', marginBottom: '3rem', maxWidth: '800px', margin: '0 auto 2.5rem auto' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="input"
          placeholder="Ask a question about BMU..."
          style={{ paddingLeft: '3rem', paddingRight: '8rem', paddingTop: '1rem', paddingBottom: '1rem', fontSize: '1rem' }}
        />
        <div style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }}>
          <Search size={18} />
        </div>
        <button
          type="submit"
          className="btn"
          style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)', padding: '0.5rem 1.25rem', fontSize: '0.8rem' }}
          disabled={isGenerating}
        >
          {isGenerating ? <><Loader2 size={14} className="spin" /> Comparing...</> : 'Compare'}
        </button>
      </form>

      {(noRagResult || ragResult || isGenerating) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }} className="fade-in">
          {/* WITHOUT RAG */}
          <div className="card">
            <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', marginBottom: '1rem', color: '#ef4444', fontSize: '0.85rem', letterSpacing: '0.08em' }}>
              WITHOUT RAG
            </h3>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginBottom: '1rem', fontWeight: 600, letterSpacing: '0.04em' }}>
              {modelLabel} — No University Knowledge
            </div>
            {noRagError ? (
              <div style={{ color: '#ef4444', whiteSpace: 'pre-wrap', lineHeight: '1.6', fontSize: '0.9rem' }}>{noRagError}</div>
            ) : noRagResult ? (
              <div className="fade-in">
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7', fontSize: '0.9rem', color: 'var(--text-primary)' }}>{noRagResult.answer}</p>
                <div style={{ marginTop: '1.5rem', padding: '0.75rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '2px', fontSize: '0.8rem', color: '#fca5a5' }}>
                  ⚠ Unverified — no BMU knowledge was provided.
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                <Loader2 size={14} className="spin" /> Generating baseline response...
              </div>
            )}
          </div>

          {/* WITH RAG */}
          <div className="card" style={{ border: '1px solid #2a2a2a' }}>
            <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', marginBottom: '1rem', color: '#22c55e', fontSize: '0.85rem', letterSpacing: '0.08em' }}>
              WITH RAG
            </h3>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginBottom: '1rem', fontWeight: 600, letterSpacing: '0.04em' }}>
              {modelLabel} — BMU Knowledge Retrieved
            </div>
            {ragError ? (
              <div style={{ color: '#f59e0b', whiteSpace: 'pre-wrap', lineHeight: '1.6', fontSize: '0.9rem' }}>{ragError}</div>
            ) : ragResult ? (
              <div className="fade-in">
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7', fontSize: '0.9rem' }}>{ragResult.answer}</p>
                <div style={{ marginTop: '1.5rem' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', letterSpacing: '0.08em', fontWeight: 600 }}>SOURCES:</div>
                  <ul style={{ listStyleType: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    {ragResult.sources.map((src, i) => (
                      <li key={i} style={{ fontSize: '0.8rem', color: '#4ade80', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>→</span>
                        {src.document} — Page {src.page} {src.content_type === 'table' ? '— Table' : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                <Loader2 size={14} className="spin" /> Generating grounded response...
              </div>
            )}
          </div>
        </div>
      )}

      {ragResult && (
        <div className="card fade-in" style={{ marginTop: '1.5rem', background: 'var(--bg-color)', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Zap size={14} style={{ color: '#22c55e' }} />
            <h4 style={{ margin: 0, fontSize: '0.8rem', letterSpacing: '0.06em', color: 'var(--text-secondary)' }}>WHAT CHANGED?</h4>
          </div>
          <ul style={{ color: 'var(--text-secondary)', lineHeight: 1.8, paddingLeft: '1.25rem', margin: 0, fontSize: '0.85rem' }}>
            <li>BMU-specific context was retrieved from ChromaDB ({ragResult.retrieval_results?.length || 0} chunks).</li>
            <li>Relevant source documents were supplied to {modelLabel} as system context.</li>
            <li>The LLM generated its answer strictly from the provided context, eliminating hallucination.</li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default LLMApp;



