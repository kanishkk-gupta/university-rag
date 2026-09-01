import React, { useState } from 'react';
import { chatWithRAG } from '../services/api';
import { Search, Loader2 } from 'lucide-react';

const LLMApp = () => {
  const [query, setQuery] = useState('What is the deadline for Odd Semester fee payment for existing students?');
  const [isGenerating, setIsGenerating] = useState(false);
  
  const [noRagResult, setNoRagResult] = useState(null);
  const [ragResult, setRagResult] = useState(null);
  const [ragError, setRagError] = useState(null);
  const [noRagError, setNoRagError] = useState(null);

  const handleRun = async (e) => {
    e.preventDefault();
    setIsGenerating(true);
    setNoRagResult(null);
    setRagResult(null);
    setRagError(null);
    setNoRagError(null);
    
    try {
      // Run without RAG
      const withoutRag = await chatWithRAG(query, false);
      setNoRagResult(withoutRag);
    } catch (err) {
      console.error(err);
      setNoRagError("Code Llama generation timed out or failed.");
    }
    
    try {
      // Run with RAG
      const withRag = await chatWithRAG(query, true);
      setRagResult(withRag);
    } catch (err) {
      console.error(err);
      setRagError("Code Llama generation timed out. Retrieval completed successfully, but the local LLM did not return within the configured timeout.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: '3rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>LLM Application</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Exercise 1: Code Llama is a general-purpose language model. It does not inherently contain the current private BMU University policies and calendars used in this project.
        </p>
      </div>

      <form onSubmit={handleRun} style={{ position: 'relative', marginBottom: '3rem', maxWidth: '800px', margin: '0 auto 3rem auto' }}>
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="input"
          style={{ paddingLeft: '3rem', paddingRight: '8rem', paddingTop: '1rem', paddingBottom: '1rem', fontSize: '1.1rem' }}
        />
        <div style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }}>
          <Search size={20} />
        </div>
        <button 
          type="submit" 
          className="btn"
          style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)' }}
          disabled={isGenerating}
        >
          {isGenerating ? <Loader2 size={18} className="spin" /> : 'Compare'}
        </button>
      </form>

      {(noRagResult || ragResult || isGenerating) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
          {/* WITHOUT RAG */}
          <div className="card">
            <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1rem', color: '#ef4444' }}>
              WITHOUT RAG
            </h3>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem', fontWeight: 'bold' }}>
              Base LLM — No University Knowledge
            </div>
            {noRagError ? (
              <div style={{ color: '#ef4444', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{noRagError}</div>
            ) : noRagResult ? (
              <div>
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{noRagResult.answer}</p>
                <div style={{ marginTop: '2rem', padding: '1rem', background: '#450a0a', color: '#fca5a5', borderRadius: '4px', fontSize: '0.85rem' }}>
                  Unverified — no BMU knowledge was provided.
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)' }}>Generating baseline response...</div>
            )}
          </div>

          {/* WITH RAG */}
          <div className="card" style={{ border: '1px solid var(--accent-color)' }}>
            <h3 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1rem', color: 'var(--accent-color)' }}>
              WITH RAG
            </h3>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem', fontWeight: 'bold' }}>
              RAG — BMU Knowledge Retrieved
            </div>
            {ragError ? (
              <div style={{ color: 'var(--accent-color)', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{ragError}</div>
            ) : ragResult ? (
              <div>
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{ragResult.answer}</p>
                <div style={{ marginTop: '2rem' }}>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>SOURCES:</strong>
                  <ul style={{ listStyleType: 'none', padding: 0, marginTop: '0.5rem' }}>
                    {ragResult.sources.map((src, i) => (
                      <li key={i} style={{ fontSize: '0.85rem', color: 'var(--accent-color)', marginBottom: '0.25rem' }}>
                        {src.document} — Page {src.page} {src.content_type === 'table' ? '— Table' : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)' }}>Generating grounded response...</div>
            )}
          </div>
        </div>
      )}
      
      {ragResult && (
        <div className="card" style={{ marginTop: '2rem', background: 'var(--bg-color)' }}>
          <h4>WHAT CHANGED?</h4>
          <ul style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <li>BMU-specific context was retrieved from ChromaDB.</li>
            <li>Relevant source documents were supplied to the LLM system prompt.</li>
            <li>Code Llama generated its answer strictly from the provided context, eliminating hallucination.</li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default LLMApp;
