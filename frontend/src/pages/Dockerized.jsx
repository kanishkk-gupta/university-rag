import React from 'react';
import { Box, Server, Database, BrainCircuit, Network, HardDrive } from 'lucide-react';

const Dockerized = () => {
  return (
    <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', width: '100%' }}>
      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>Docker Deployment Architecture</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Exercise 5: Containerizing the Application. This illustrates the final docker-compose stack.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', alignItems: 'center' }}>
        
        {/* FRONTEND CONTAINER */}
        <div style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '1.5rem', width: '100%', maxWidth: '600px', background: 'var(--panel-bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', color: 'var(--text-primary)', fontWeight: 600 }}>
            <Box /> Frontend Container (Containerized)
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Serves the compiled React SPA.
          </div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <span style={{ border: '1px solid var(--border-color)', padding: '0.25rem 0.75rem', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Port: 5173</span>
            <span style={{ border: '1px solid var(--border-color)', padding: '0.25rem 0.75rem', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Image: node:20-alpine</span>
          </div>
        </div>

        <Network color="var(--text-secondary)" />

        {/* API CONTAINER */}
        <div style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '1.5rem', width: '100%', maxWidth: '600px', background: 'var(--panel-bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', color: 'var(--text-primary)', fontWeight: 600 }}>
            <Server /> API / Application Container (Containerized)
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
            FastAPI server running Uvicorn. Houses the RAG Pipeline logic.
          </div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <span style={{ border: '1px solid var(--border-color)', padding: '0.25rem 0.75rem', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Port: 8000</span>
            <span style={{ border: '1px solid var(--border-color)', padding: '0.25rem 0.75rem', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Image: python:3.11-slim</span>
          </div>

          <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px dashed var(--border-color)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            
            {/* EMBEDDED CHROMA */}
            <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                <Database size={16} /> Embedded Vector Store
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Local ChromaDB instance.</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                <HardDrive size={14} /> Volume: ./data/chroma
              </div>
            </div>

            {/* OLLAMA HOST */}
            <div style={{ background: 'var(--bg-color)', padding: '1rem', borderRadius: '4px', border: '1px dashed var(--text-secondary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                <BrainCircuit size={16} /> Ollama Host (External)
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Runs outside Docker natively on host to utilize local GPU/CPU hardware.
              </div>
              <div style={{ marginTop: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Via http://host.docker.internal:11434
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
};

export default Dockerized;
