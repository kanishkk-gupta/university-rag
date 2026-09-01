import React from 'react';
import { FileText, Table } from 'lucide-react';

const SourcePanel = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div style={{ marginTop: '2rem' }}>
      <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>
        Sources
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        {sources.map((src, i) => (
          <div key={i} className="card" style={{ padding: '1rem', borderLeft: '3px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              {src.content_type === 'table' ? <Table size={14} /> : <FileText size={14} />}
              <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>SOURCE {src.source_id}</span>
            </div>
            <div style={{ fontWeight: 500, fontSize: '0.95rem', marginBottom: '0.25rem' }}>{src.document}</div>
            {src.page && src.page !== 'Unknown Page' && (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Page {src.page}</div>
            )}
            {src.section && (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>Sec: {src.section}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default SourcePanel;
