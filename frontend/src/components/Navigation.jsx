import React from 'react';
import { NavLink } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

const Navigation = () => {
  const linkStyle = ({ isActive }) => ({
    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
  });

  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '1rem 2rem',
      borderBottom: '1px solid var(--border-color)',
      backgroundColor: 'var(--bg-color)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontWeight: 600, letterSpacing: '0.05em', flexShrink: 0 }}>
        <BookOpen size={20} />
        <span>BMU RAG</span>
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.8rem', fontWeight: 600, alignItems: 'center', flexWrap: 'wrap' }}>
        <NavLink to="/llm-app" style={linkStyle}>1. LLM APPLICATION</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/knowledge-base" style={linkStyle}>2. KNOWLEDGE BASE</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/rag" style={linkStyle}>3. RAG</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/orchestration" style={linkStyle}>4. ORCHESTRATION</NavLink>
        <span style={{ color: 'var(--border-color)' }}>→</span>
        <NavLink to="/docker" style={linkStyle}>5. DOCKERIZED</NavLink>
        <span style={{ color: 'var(--border-color)', margin: '0 0.25rem' }}>|</span>
        <NavLink to="/evaluation" style={linkStyle}>6. EVALUATION</NavLink>
        <span style={{ color: 'var(--border-color)' }}>|</span>
        <NavLink to="/codebase" style={linkStyle}>7. CODEBASE</NavLink>
      </div>
    </nav>
  );
};

export default Navigation;
