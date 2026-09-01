import React from 'react';

const Hero = ({ onSuggest }) => {
  const suggestions = [
    "What is the fee payment deadline?",
    "When is Mahavir Jayanti?",
    "What is the anti-ragging policy?",
    "What is the library timing?",
  ];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      textAlign: 'center',
      padding: '4rem 1rem',
      maxWidth: '600px',
      margin: '0 auto',
      marginTop: '4rem'
    }}>
      <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem', fontWeight: 600 }}>BMU UNIVERSITY RAG</h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '1.2rem', marginBottom: '3rem' }}>
        Ask the university. Search the knowledge.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', justifyContent: 'center' }}>
        {suggestions.map((q, i) => (
          <button 
            key={i} 
            className="btn btn-secondary" 
            style={{ fontSize: '0.9rem', padding: '0.5rem 1rem', borderRadius: '20px' }}
            onClick={() => onSuggest(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Hero;
