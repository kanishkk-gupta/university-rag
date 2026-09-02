import React, { useState } from 'react';
import { chatWithRAG, embedQuery, retrieveChunks } from '../services/api';
import { Search, Loader2, ArrowDown, Database, Cpu, FileText } from 'lucide-react';

const RAG = () => {
  const [query, setQuery] = useState('What is the deadline for Odd Semester fee payment for existing students?');
  const [isProcessing, setIsProcessing] = useState(false);
  const [pipelineState, setPipelineState] = useState('idle'); // idle, embedding, retrieval, generating, complete
  
  const [queryVector, setQueryVector] = useState(null);
  const [retrievedChunks, setRetrievedChunks] = useState([]);
  const [finalResult, setFinalResult] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsProcessing(true);
    setPipelineState('embedding');
    setQueryVector(null);
    setRetrievedChunks([]);
    setFinalResult(null);
    setError(null);
    
    try {
      // Step 2: Query Embedding
      const embedData = await embedQuery(query);
      setQueryVector(embedData.embedding);
      
      setPipelineState('retrieval');
      
      // Step 3: Retrieval
      const retrieveData = await retrieveChunks(query, 3); // top 3 for UI
      setRetrievedChunks(retrieveData.chunks);
      
      setPipelineState('generating');
      
      // Step 4-7: LLM & Final Output (We use the main chat endpoint which does retrieval again, but it's fine for demo consistency)
      const chatData = await chatWithRAG(query, true);
      setFinalResult(chatData);
      
      setPipelineState('complete');
    } catch (err) {
      console.error(err);
      setError(`Pipeline failed: ${err.message || 'Unknown error occurred.'}`);
      setPipelineState('complete');
    } finally {
      setIsProcessing(false);
    }
  };

  const StepBox = ({ number, title, children, active, done }) => {
    const isActive = active || done;
    return (
      <div className="card" style={{ 
        opacity: isActive ? 1 : 0.4,
        borderColor: active ? 'var(--accent-color)' : 'var(--border-color)',
        transition: 'all 0.3s ease',
        position: 'relative'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: children ? '1rem' : 0 }}>
          <div style={{ 
            width: '24px', height: '24px', borderRadius: '12px', 
            background: active ? 'var(--accent-color)' : (done ? 'var(--text-primary)' : 'var(--border-color)'),
            color: active ? '#fff' : (done ? '#000' : 'var(--text-secondary)'),
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.75rem', fontWeight: 'bold'
          }}>
            {number}
          </div>
          <h3 style={{ margin: 0, fontSize: '1rem', color: active ? 'var(--accent-color)' : (done ? 'var(--text-primary)' : 'var(--text-secondary)') }}>
            {title}
          </h3>
        </div>
        {children && isActive && (
          <div style={{ paddingLeft: '2.25rem' }}>
            {children}
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', width: '100%' }}>
      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>RAG Pipeline</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Exercise 3: Observe the complete "Live Pipeline Mode" from query vectorization to grounded LLM generation.
        </p>
      </div>

      <form onSubmit={handleRun} style={{ position: 'relative', marginBottom: '3rem' }}>
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="input"
          style={{ paddingLeft: '3rem', paddingRight: '8rem', paddingTop: '1rem', paddingBottom: '1rem', fontSize: '1.1rem' }}
          disabled={isProcessing}
        />
        <div style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }}>
          <Search size={20} />
        </div>
        <button 
          type="submit" 
          className="btn"
          style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)' }}
          disabled={isProcessing}
        >
          {isProcessing ? <Loader2 size={18} className="spin" /> : 'Run Pipeline'}
        </button>
      </form>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        
        <StepBox 
          number="01" 
          title="QUESTION" 
          active={pipelineState === 'embedding'} 
          done={pipelineState !== 'idle'}
        >
          <div style={{ fontSize: '1.1rem' }}>"{query}"</div>
        </StepBox>

        <StepBox 
          number="02" 
          title="QUERY EMBEDDING" 
          active={pipelineState === 'embedding'} 
          done={['retrieval', 'generating', 'complete'].includes(pipelineState)}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
            Model: all-MiniLM-L6-v2 | Dimension: 384
          </div>
          {queryVector ? (
            <div style={{ fontFamily: 'monospace', fontSize: '0.75rem', background: '#000', padding: '1rem', borderRadius: '4px', wordBreak: 'break-all' }}>
              [{queryVector.slice(0, 8).map(v => v.toFixed(4)).join(', ')}, ... {queryVector.length - 8} more dimensions]
            </div>
          ) : error ? (
            <div style={{ color: '#ef4444', fontSize: '0.85rem' }}>Embedding failed — see error below.</div>
          ) : <Loader2 size={16} className="spin" />}
        </StepBox>

        <StepBox 
          number="03" 
          title="VECTOR SIMILARITY" 
          active={pipelineState === 'retrieval'} 
          done={['generating', 'complete'].includes(pipelineState)}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            The query vector is compared with stored chunk vectors to identify semantically relevant information.
          </div>
          {retrievedChunks.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
              {retrievedChunks.map((chunk, i) => (
                <div key={i} style={{ border: '1px solid var(--border-color)', padding: '0.75rem', fontSize: '0.8rem' }}>
                  <div style={{ fontWeight: 'bold', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    Rank: #{i+1} | Cosine Distance: {chunk.distance.toFixed(4)}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.25rem', color: 'var(--text-secondary)' }}>
                    <div>Document: {chunk.document_name}</div>
                    <div>Page: {chunk.page_start}</div>
                    <div>Chunk ID: {chunk.chunk_id}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div style={{ color: '#ef4444', fontSize: '0.85rem' }}>Retrieval failed — see error below.</div>
          ) : <Loader2 size={16} className="spin" />}
        </StepBox>

        <StepBox 
          number="04" 
          title="RETRIEVAL" 
          active={pipelineState === 'retrieval'} 
          done={['generating', 'complete'].includes(pipelineState)}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Selected top-{retrievedChunks.length} chunks based on lowest vector distance.
          </div>
        </StepBox>

        <StepBox 
          number="05" 
          title="CONTEXT AUGMENTATION" 
          active={pipelineState === 'generating'} 
          done={pipelineState === 'complete'}
        >
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Retrieved BMU information is supplied to Code Llama as context before generation.
          </div>
          {retrievedChunks.length > 0 && (
            <div>
              <div style={{ fontSize: '0.75rem', color: '#666', marginBottom: '0.5rem', fontFamily: 'monospace' }}>
                SYSTEM PROMPT HEADER (from rag/prompt.py):
              </div>
              <div style={{ background: '#060606', border: '1px solid #222', padding: '0.75rem', fontSize: '0.78rem', color: '#666', fontFamily: 'monospace', marginBottom: '0.75rem', lineHeight: 1.5 }}>
                You are a highly reliable and factual AI assistant for BMU University.{'\n'}
                Your ONLY goal is to answer the user's question based strictly on the provided context.{'\n'}
                [Rules: cite sources, no hallucinations, exact values, respond in context only]{'\n'}
                {'\n'}CONTEXT:{'\n'}
                [retrieved chunks below ↓]
              </div>
              <div style={{ background: '#0a0a0a', border: '1px solid var(--border-color)', padding: '1rem', fontSize: '0.85rem', maxHeight: '250px', overflowY: 'auto' }}>
                {retrievedChunks.map((c, i) => (
                  <div key={i} style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>
                    <div style={{ color: 'var(--text-primary)', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                      --- SOURCE {i+1}: {c.document_name} (Page {c.page_start}) ---
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', fontFamily: c.content_type === 'table' ? 'monospace' : 'inherit' }}>
                      {c.text}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </StepBox>

        <StepBox 
          number="06" 
          title="OLLAMA" 
          active={pipelineState === 'generating'} 
          done={pipelineState === 'complete'}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: 'var(--text-secondary)' }}>
            <Cpu size={24} />
            <div>
              <div style={{ fontWeight: 500 }}>Code Llama 7B (Instruct)</div>
              <div style={{ fontSize: '0.85rem' }}>
                {pipelineState === 'generating' ? 'Generating response...' : 'Generation complete'}
              </div>
            </div>
            {pipelineState === 'generating' && <Loader2 size={16} className="spin" style={{ marginLeft: 'auto' }} />}
          </div>
        </StepBox>

        <StepBox 
          number="07" 
          title="RESPONSE" 
          active={false} 
          done={pipelineState === 'complete'}
        >
          {error ? (
            <div style={{ fontSize: '1.1rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
              {error}
            </div>
          ) : finalResult && (
            <div style={{ fontSize: '1.1rem', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
              {finalResult.answer}
            </div>
          )}
        </StepBox>

        <StepBox 
          number="08" 
          title="SOURCES" 
          active={false} 
          done={pipelineState === 'complete'}
        >
          {finalResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {finalResult.sources.map((src, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--panel-bg)', padding: '0.75rem 1rem', border: '1px solid var(--border-color)', fontSize: '0.85rem' }}>
                  <FileText size={14} />
                  <span>Document: {src.document} | Page: {src.page} | Section: {src.section} | Chunk ID: {src.chunk_id}</span>
                </div>
              ))}
            </div>
          )}
        </StepBox>

      </div>
    </div>
  );
};

export default RAG;
