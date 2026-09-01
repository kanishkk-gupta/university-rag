import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Search } from 'lucide-react';

const RetrievalInspector = ({ results }) => {
  const [expanded, setExpanded] = useState(false);

  if (!results || results.length === 0) return null;

  return (
    <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border-color)', paddingTop: '2rem' }}>
      <button 
        onClick={() => setExpanded(!expanded)}
        style={{ 
          background: 'transparent', 
          border: 'none', 
          color: 'var(--text-secondary)', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '0.5rem', 
          cursor: 'pointer',
          padding: 0,
          fontSize: '0.9rem'
        }}
      >
        <Search size={16} />
        <span>Retrieval Inspector ({results.length} chunks)</span>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && (
        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {results.map((res, i) => (
            <div key={i} style={{ background: 'var(--bg-color)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                <span>{res.document_name} | Page {res.page_start} | {res.content_type}</span>
                <span>Distance: {res.distance?.toFixed(4)}</span>
              </div>
              <div style={{ fontSize: '0.85rem', whiteSpace: 'pre-wrap', maxHeight: '150px', overflowY: 'auto' }}>
                {res.text}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default RetrievalInspector;
