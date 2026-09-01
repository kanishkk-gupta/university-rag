import React from 'react';
import { CheckCircle2, CircleDashed } from 'lucide-react';

const PipelineVisualizer = ({ status }) => {
  // status can be: 'idle', 'retrieving', 'generating', 'complete', 'error'
  
  const steps = [
    { id: 'retrieving', label: 'Retrieving Context' },
    { id: 'generating', label: 'Generating Answer' },
    { id: 'complete', label: 'Done' }
  ];

  const getStepState = (stepId) => {
    if (status === 'error') return 'error';
    if (status === 'complete') return 'done';
    if (status === 'generating' && stepId === 'retrieving') return 'done';
    if (status === stepId) return 'active';
    return 'pending';
  };

  if (status === 'idle') return null;

  return (
    <div style={{ display: 'flex', gap: '2rem', padding: '1rem', background: 'var(--panel-bg)', borderRadius: '6px', marginBottom: '2rem', border: '1px solid var(--border-color)' }}>
      {steps.map((step, i) => {
        const state = getStepState(step.id);
        const color = state === 'done' ? 'var(--text-primary)' : state === 'active' ? 'var(--accent-color)' : 'var(--text-secondary)';
        
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color, fontSize: '0.85rem', fontWeight: 500 }}>
            {state === 'done' ? <CheckCircle2 size={16} /> : <CircleDashed size={16} className={state === 'active' ? 'spin' : ''} />}
            <span>{step.label}</span>
          </div>
        );
      })}
    </div>
  );
};

export default PipelineVisualizer;
