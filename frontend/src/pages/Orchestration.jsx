import React, { useState } from 'react';
import { chatWithRAG } from '../services/api';
import { ArrowDown, Box, Server, Database, BrainCircuit, Activity } from 'lucide-react';

const Orchestration = () => {
  const [trace, setTrace] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeService, setActiveService] = useState(null);

  const handleTest = async () => {
    setIsProcessing(true);
    setTrace([]);
    const startTime = Date.now();
    
    const addTimeTrace = (msg) => {
      const timeMs = Date.now() - startTime;
      const formatted = `+${timeMs}ms`;
      setTrace(prev => [...prev, { time: formatted, msg }]);
    };
    
    addTimeTrace("Request received by Frontend");
    addTimeTrace("Frontend → POST /api/chat");
    
    try {
      setTimeout(() => addTimeTrace("API Service → RAG Service: Query received"), 100);
      setTimeout(() => addTimeTrace("RAG Service → embed_query()"), 300);
      setTimeout(() => addTimeTrace("Embedding Service → Vector (384-D)"), 1500);
      setTimeout(() => addTimeTrace("RAG Service → ChromaDB: similarity search"), 1600);
      setTimeout(() => addTimeTrace("ChromaDB → Top 3 chunks retrieved"), 1700);
      setTimeout(() => addTimeTrace("RAG Service: Context construction complete"), 1800);
      setTimeout(() => addTimeTrace("RAG Service → Ollama: POST /api/generate"), 1900);
      setTimeout(() => addTimeTrace("Ollama (Code Llama): Generating tokens..."), 2000);
      
      await chatWithRAG("What is the deadline for Odd Semester fee payment for existing students?", true);
      
      addTimeTrace("Ollama → RAG Service: Generation complete");
      addTimeTrace("API Service → Frontend: 200 OK");
    } catch (e) {
      addTimeTrace("Error: " + e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const services = [
    { id: 'frontend', name: 'Frontend Application', desc: 'React/Vite SPA serving the UI.', icon: <Box /> },
    { id: 'api', name: 'FastAPI Service', desc: 'Main entrypoint /api/chat. Handles CORS and validation.', icon: <Server /> },
    { id: 'rag', name: 'RAG Pipeline Service', desc: 'Orchestrates retrieval and context building.', icon: <Activity /> },
    { id: 'vector', name: 'ChromaDB', desc: 'Stores and searches 384-d chunk embeddings.', icon: <Database /> },
    { id: 'llm', name: 'Ollama Engine', desc: 'Local host for Code Llama 7B.', icon: <BrainCircuit /> },
  ];

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%', display: 'flex', gap: '3rem' }}>
      
      {/* LEFT: ARCHITECTURE MAP */}
      <div style={{ flex: 1 }}>
        <h1 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Orchestration</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
          Exercise 4: System Architecture and Service Communication.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ padding: '1rem', border: '1px dashed var(--text-secondary)', borderRadius: '4px' }}>USER</div>
          <ArrowDown size={20} color="var(--text-secondary)" />
          
          {services.map((srv, i) => (
            <React.Fragment key={srv.id}>
              <div 
                className="card" 
                style={{ 
                  width: '100%', 
                  textAlign: 'center', 
                  cursor: 'pointer',
                  borderColor: activeService === srv.id ? 'var(--accent-color)' : 'var(--border-color)',
                  background: activeService === srv.id ? '#1e293b' : 'var(--panel-bg)'
                }}
                onClick={() => setActiveService(srv.id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontWeight: 500 }}>
                  {srv.icon} {srv.name}
                </div>
              </div>
              {i < services.length - 1 && <ArrowDown size={20} color="var(--text-secondary)" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* RIGHT: DETAILS & TRACE */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        
        {/* SERVICE DETAILS */}
        <div className="card" style={{ minHeight: '150px' }}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
            Service Details
          </h2>
          {activeService ? (
            <div>
              <h3 style={{ margin: '0 0 0.5rem 0' }}>{services.find(s => s.id === activeService).name}</h3>
              <p style={{ color: 'var(--text-secondary)' }}>{services.find(s => s.id === activeService).desc}</p>
            </div>
          ) : (
            <div style={{ color: 'var(--text-secondary)' }}>Click a service on the left to view details.</div>
          )}
        </div>

        {/* REQUEST TRACE */}
        <div className="card" style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.25rem 0' }}>Request Trace</h2>
              <div style={{ fontSize: '0.75rem', color: '#666' }}>
                Real: Frontend dispatch time + E2E response time · Intermediate steps: estimated from typical latencies
              </div>
            </div>
            <button className="btn" onClick={handleTest} disabled={isProcessing} style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
              Send Test Query
            </button>
          </div>
          
          <div style={{ fontFamily: 'monospace', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            {trace.length === 0 ? (
              <div>Awaiting request...</div>
            ) : (
              trace.map((t, i) => (
                <div key={i} style={{ marginBottom: '0.5rem' }}>
                  <span style={{ color: 'var(--text-secondary)', marginRight: '1rem', display: 'inline-block', width: '80px' }}>[{t.time}]</span>
                  <span style={{ color: 'var(--text-primary)' }}>{t.msg}</span>
                </div>
              ))
            )}
            {isProcessing && <div style={{ color: 'var(--text-primary)', marginTop: '1rem' }}>... processing API request ...</div>}
          </div>
        </div>

      </div>
    </div>
  );
};

export default Orchestration;
