import React, { useState } from 'react';
import { Search, Send } from 'lucide-react';
import { chatWithRAG } from '../services/api';
import PipelineVisualizer from './PipelineVisualizer';
import SourcePanel from './SourcePanel';
import RetrievalInspector from './RetrievalInspector';

const ChatInterface = ({ initialQuery = '' }) => {
  const [query, setQuery] = useState(initialQuery);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);

  // Trigger search if initialQuery is passed
  React.useEffect(() => {
    if (initialQuery) {
      handleSearch(initialQuery);
    }
  }, [initialQuery]);

  const handleSearch = async (searchQuery) => {
    if (!searchQuery.trim()) return;
    
    setQuery(searchQuery);
    setStatus('retrieving');
    setError(null);
    setResult(null);

    try {
      // Fake delay to show 'generating' step since our API does it in one shot
      setTimeout(() => setStatus('generating'), 1000); 
      
      const data = await chatWithRAG(searchQuery);
      setResult(data);
      setStatus('complete');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to connect to the RAG backend.');
      setStatus('error');
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', width: '100%' }}>
      <form 
        onSubmit={(e) => { e.preventDefault(); handleSearch(query); }}
        style={{ position: 'relative', marginBottom: '2rem' }}
      >
        <div style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }}>
          <Search size={20} />
        </div>
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask anything about BMU policies, deadlines, or rules..."
          className="input"
          style={{ paddingLeft: '3rem', paddingRight: '4rem', paddingTop: '1rem', paddingBottom: '1rem', fontSize: '1.1rem' }}
        />
        <button 
          type="submit" 
          style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)', background: 'transparent', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '0.5rem' }}
          disabled={status === 'retrieving' || status === 'generating'}
        >
          <Send size={20} />
        </button>
      </form>

      <PipelineVisualizer status={status} />

      {error && (
        <div style={{ color: '#ef4444', padding: '1rem', border: '1px solid #ef4444', borderRadius: '6px', marginBottom: '2rem' }}>
          {error}
        </div>
      )}

      {result && (
        <div className="card" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>
            Answer
          </h2>
          <div style={{ fontSize: '1.1rem', whiteSpace: 'pre-wrap', lineHeight: '1.7' }}>
            {result.answer}
          </div>
          
          <SourcePanel sources={result.sources} />
          <RetrievalInspector results={result.retrieval_results} />
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
