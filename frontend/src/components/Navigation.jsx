import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import { getHealth } from '../services/api';

const Navigation = () => {
  const [ragReady, setRagReady] = useState(null);

  useEffect(() => {
    const checkHealth = () => {
      getHealth()
        .then(data => setRagReady(data.rag_ready === true))
        .catch(() => setRagReady(false));
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const linkStyle = ({ isActive }) => ({
    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
    transition: 'color 0.15s ease',
  });

  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0.875rem 2rem',
      borderBottom: '1px solid var(--border-color)',
      backgroundColor: 'var(--bg-color)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontWeight: 700, letterSpacing: '0.06em', flexShrink: 0, fontSize: '0.9rem' }}>
        <BookOpen size={18} />
        <span>BMU RAG</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginLeft: '0.25rem' }}>
          <div
            className={`status-dot ${ragReady === null ? '' : ragReady ? 'online' : 'offline'}`}
            style={ragReady === null ? { background: '#555', width: '7px', height: '7px', borderRadius: '50%', animation: 'pulse 1.2s ease infinite' } : {}}
            title={ragReady === null ? 'Checking...' : ragReady ? 'RAG + Ollama: Online' : 'RAG/Ollama: Offline'}
          />
          <span style={{ fontSize: '0.65rem', color: ragReady ? '#22c55e' : ragReady === false ? '#ef4444' : '#555', letterSpacing: '0.04em', fontWeight: 600 }}>
            {ragReady === null ? '...' : ragReady ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '0.6rem', fontSize: '0.78rem', fontWeight: 600, alignItems: 'center', flexWrap: 'wrap' }}>
        <NavLink to="/llm-app" style={linkStyle}>1. LLM APP</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/knowledge-base" style={linkStyle}>2. KNOWLEDGE BASE</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/rag" style={linkStyle}>3. RAG</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/orchestration" style={linkStyle}>4. ORCHESTRATION</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/docker" style={linkStyle}>5. DOCKER</NavLink>
        <span style={{ color: 'var(--border-color)', margin: '0 0.1rem' }}>|</span>
        <NavLink to="/evaluation" style={linkStyle}>6. EVALUATION</NavLink>
        <span style={{ color: 'var(--border-color)' }}>|</span>
        <NavLink to="/codebase" style={linkStyle}>7. CODEBASE</NavLink>
        <span style={{ color: 'var(--border-color)' }}>|</span>
        <NavLink to="/guardrails" style={linkStyle}>8. GUARDRAILS</NavLink>
      </div>
    </nav>
  );
};

export default Navigation;
