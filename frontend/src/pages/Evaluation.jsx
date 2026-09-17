import React, { useState, useEffect } from 'react';
import { Loader2, Play, RefreshCw } from 'lucide-react';
import { getEvalResults, getEvalSummary, getEvalDataset, runEvaluation } from '../services/api';


// ─── Metric Definitions (New LLM & Semantic Metrics) ─────────────────────
const METRIC_DEFS = [
  {
    name: 'LLM Judge Score',
    label: 'LLM Judge Score (0.0 – 1.0)',
    formula: 'A powerful judge LLM (e.g., Llama 3) evaluates the model answer against the reference answer based on Accuracy, Completeness, and Grounding.',
    note: 'Score is normalized to a 0-1 scale. A score of 1.0 means perfect alignment with the reference.'
  },
  {
    name: 'Semantic Similarity',
    label: 'Semantic Similarity (0.0 – 1.0)',
    formula: 'Cosine similarity between the embeddings of the model answer and the reference answer using a sentence-transformers model (all-MiniLM-L6-v2).',
    note: 'Captures meaning rather than exact word matching. Higher is better.'
  },
  {
    name: 'Latency',
    label: 'Generation Latency (seconds)',
    formula: 'time.time() after generate() call — time.time() before generate() call',
    note: 'Real wall-clock timer. Includes network overhead and inference time.'
  }
];

// ─── Summary Table ───────────────────────────────────────────────────────────
const SummaryTable = ({ categorySummary }) => {
  if (!categorySummary || !categorySummary.overall) {
    return <p style={{ color: 'var(--text-secondary)' }}>No category evaluation results available. Run the evaluation first.</p>;
  }

  const models = Object.keys(categorySummary.overall);
  const categories = Object.keys(categorySummary.categories || {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Overall Score */}
      <div>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Overall Performance</h2>
        <div style={{ overflowX: 'auto', background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem', textAlign: 'right' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', background: 'rgba(255,255,255,0.02)' }}>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600 }}>Metric</th>
                {models.map(m => (
                  <th key={m} style={{ padding: '0.8rem 1rem', color: 'var(--text-primary)', fontWeight: 600 }}>{m}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {['Judge Score', 'Semantic Similarity', 'Average Latency'].map(metric => (
                <tr key={metric} style={{ borderBottom: '1px solid #222' }}>
                  <td style={{ padding: '0.8rem 1rem', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)' }}>{metric}</td>
                  {models.map(m => {
                    const stats = categorySummary.overall[m];
                    let val = '';
                    if (metric === 'Judge Score') val = (stats.judge_score || 0).toFixed(2);
                    else if (metric === 'Semantic Similarity') val = (stats.semantic_similarity || 0).toFixed(2);
                    else if (metric === 'Average Latency') val = (stats.avg_latency || 0).toFixed(2) + 's';
                    return <td key={m} style={{ padding: '0.8rem 1rem', fontFamily: 'monospace' }}>{val}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Category Breakdown */}
      <div>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Category Breakdown (Judge Score)</h2>
        <div style={{ overflowX: 'auto', background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'right' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', background: 'rgba(255,255,255,0.02)' }}>
                <th style={{ padding: '0.8rem 1rem', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600 }}>Category</th>
                {models.map(m => (
                  <th key={m} style={{ padding: '0.8rem 1rem', color: 'var(--text-primary)', fontWeight: 600 }}>{m}</th>
                ))}
                <th style={{ padding: '0.8rem 1rem', color: 'var(--accent-color)', fontWeight: 600 }}>Winner</th>
              </tr>
            </thead>
            <tbody>
              {categories.map(cat => (
                <tr key={cat} style={{ borderBottom: '1px solid #222' }}>
                  <td style={{ padding: '0.8rem 1rem', textAlign: 'left', fontWeight: 600, color: 'var(--text-primary)' }}>{cat}</td>
                  {models.map(m => (
                    <td key={m} style={{ padding: '0.8rem 1rem', fontFamily: 'monospace' }}>
                      {(categorySummary.categories[cat][m]?.judge_score || 0).toFixed(2)}
                    </td>
                  ))}
                  <td style={{ padding: '0.8rem 1rem', fontWeight: 600, color: 'var(--accent-color)' }}>
                    {categorySummary.winners?.[cat] || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ─── Question-Level Comparison ───────────────────────────────────────────────
const QuestionComparison = ({ results, dataset }) => {
  const [selectedQ, setSelectedQ] = useState(null);

  if (!results || results.length === 0) return null;

  const questions = [...new Set(results.map(r => r.question_id))];
  const models = [...new Set(results.map(r => r.model))];

  const qRecs = selectedQ ? results.filter(r => r.question_id === selectedQ) : [];
  const qDataset = dataset?.find(q => q.id === selectedQ);

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        {questions.map(qid => (
          <button
            key={qid}
            onClick={() => setSelectedQ(qid)}
            style={{
              padding: '0.3rem 0.6rem',
              fontSize: '0.75rem',
              background: selectedQ === qid ? 'var(--text-primary)' : 'var(--panel-bg)',
              color: selectedQ === qid ? '#000' : 'var(--text-secondary)',
              border: '1px solid var(--border-color)',
              cursor: 'pointer',
              fontFamily: 'monospace'
            }}
          >
            {qid}
          </button>
        ))}
      </div>

      {selectedQ && (
        <div>
          <div style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid var(--border-color)', background: '#0a0a0a' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              QUESTION {selectedQ} · Category: {qDataset?.category || '—'} · Answerable: {qDataset?.answerable ? 'YES' : 'NO (negative test)'}
            </div>
            <div style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>"{qDataset?.question || qRecs[0]?.question}"</div>
            {qDataset?.expected_source?.length > 0 && (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Expected sources: {qDataset.expected_source.join(', ')}
              </div>
            )}
            {qDataset?.reference_answer && (
              <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '0.5rem' }}>
                Reference answer: {qDataset.reference_answer}
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${models.length}, 1fr)`, gap: '1rem' }}>
            {models.map(model => {
              const rec = qRecs.find(r => r.model === model);
              const failed = rec?.answer?.startsWith('Error:');
              const shortName = model.replace('codellama:7b-instruct', 'Code Llama 7B').replace('starcoder2:3b', 'StarCoder2 3B').replace('qwen2.5-coder:1.5b', 'Qwen2.5 1.5B');
              return (
                <div key={model} style={{ border: `1px solid ${failed ? '#5a1a1a' : 'var(--border-color)'}`, padding: '1rem', background: failed ? '#1a0808' : 'var(--panel-bg)' }}>
                  <div style={{ fontWeight: 600, marginBottom: '0.75rem', fontSize: '0.9rem' }}>{shortName}</div>
                  {rec ? (
                    <>
                      <div style={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', lineHeight: 1.5, marginBottom: '1rem', color: failed ? '#ef4444' : 'var(--text-primary)', maxHeight: '150px', overflowY: 'auto' }}>
                        {rec.answer}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem', fontFamily: 'monospace' }}>
                        <div style={{ color: '#22c55e', fontWeight: 600 }}>Judge Score: {rec.metrics?.judge_score?.toFixed(2) ?? '—'}</div>
                        <div style={{ color: '#3b82f6', fontWeight: 600 }}>Semantic Sim: {rec.metrics?.semantic_similarity?.toFixed(2) ?? '—'}</div>
                        <div>Gen Lat: {rec.generation_latency?.toFixed(2)}s</div>
                        <div>Retr Lat: {rec.retrieval_latency?.toFixed(2)}s</div>
                        <div>Prompt Tok: {rec.tokens?.prompt_tokens ?? 'N/A'}</div>
                        <div>Compl Tok: {rec.tokens?.completion_tokens ?? 'N/A'}</div>
                      </div>
                      <div style={{ marginTop: '0.75rem', fontSize: '0.7rem', color: '#555' }}>
                        Mode: {rec.mode} | Same context → 3 models ✓
                      </div>
                    </>
                  ) : (
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No record found</div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Controlled Generation Note */}
          <div style={{ marginTop: '1rem', padding: '0.75rem', border: '1px solid #333', background: '#0d1117', fontSize: '0.8rem', color: '#888' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Controlled Generation:</strong> Retrieval was performed once per question.
            The SAME context was passed to all three models. Retrieval latency is shared (identical across models for this question).
            This isolates the effect of the LLM from the effect of retrieval quality.
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Metric Definitions Panel ────────────────────────────────────────────────
const MetricDefinitions = () => (
  <div>
    {METRIC_DEFS.map(m => (
      <div key={m.name} style={{ marginBottom: '1.25rem', paddingBottom: '1.25rem', borderBottom: '1px solid #222' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{m.label}</div>
        <pre style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', fontFamily: 'monospace', background: '#0a0a0a', padding: '0.5rem' }}>
          {m.formula}
        </pre>
        <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: '#ef8f30' }}>⚠ {m.note}</div>
      </div>
    ))}
  </div>
);

// ─── Main Evaluation Page ─────────────────────────────────────────────────────
const Evaluation = () => {
  const [results, setResults] = useState([]);
  const [dataset, setDataset] = useState([]);
  const [categorySummary, setCategorySummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('summary');
  const [runningEval, setRunningEval] = useState(false);
  const [runStatus, setRunStatus] = useState(null);

  const fetchData = () => {
    setLoading(true);
    // Dynamic import for getEvalCategorySummary from API service
    import('../services/api').then(({ getEvalResults, getEvalDataset, getEvalCategorySummary }) => {
      Promise.all([
        getEvalResults().then(d => d.results || []).catch(() => []),
        getEvalDataset().then(d => d.dataset || []).catch(() => []),
        getEvalCategorySummary().catch(() => null)
      ]).then(([res, ds, catSummary]) => {
        setResults(res);
        setDataset(ds);
        setCategorySummary(catSummary);
        setLoading(false);
      });
    });
  };

  useEffect(() => { fetchData(); }, []);

  const handleRunEval = async () => {
    setRunningEval(true);
    setRunStatus(null);
    try {
      const data = await runEvaluation();
      setRunStatus({ ok: true, msg: data.message });
    } catch (e) {
      setRunStatus({ ok: false, msg: `Error: ${e.message}` });
    }
    setRunningEval(false);
  };


  const tabs = [
    { id: 'summary', label: 'Summary Metrics' },
    { id: 'comparison', label: 'Question Comparison' },
    { id: 'definitions', label: 'Metric Definitions' },
    { id: 'dataset', label: 'Dataset (25 Questions)' },
  ];

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
          <h1 style={{ margin: 0 }}>Evaluation Dashboard</h1>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              className="btn btn-secondary"
              onClick={fetchData}
              disabled={loading}
              style={{ padding: '0.5rem 1rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
            <button
              className="btn"
              onClick={handleRunEval}
              disabled={runningEval}
              style={{ padding: '0.5rem 1.25rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem', background: '#22c55e', color: '#000' }}
            >
              {runningEval ? <><Loader2 size={13} className="spin" /> Running...</> : <><Play size={13} /> Run Evaluation</>}
            </button>
          </div>
        </div>
        <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0' }}>
          Week 4 — Multi-Model Category Evaluation (Semantic & LLM-as-a-Judge)
        </p>
        {runStatus && (
          <div style={{ marginTop: '0.5rem', padding: '0.6rem 0.8rem', border: `1px solid ${runStatus.ok ? '#22c55e' : '#ef4444'}`, background: runStatus.ok ? '#0a1f0a' : '#1f0a0a', fontSize: '0.82rem', color: runStatus.ok ? '#4ade80' : '#ef4444' }}>
            {runStatus.msg} {runStatus.ok && '— Refresh results in ~30-60 seconds when complete.'}
          </div>
        )}

      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-color)', marginBottom: '2rem' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '0.75rem 1.25rem',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === t.id ? '2px solid var(--text-primary)' : '2px solid transparent',
              color: activeTab === t.id ? 'var(--text-primary)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: activeTab === t.id ? 600 : 400,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          <Loader2 size={14} className="spin" /> Loading evaluation data...
        </div>
      ) : (
        <>
          {activeTab === 'summary' && <SummaryTable categorySummary={categorySummary} />}
          {activeTab === 'comparison' && <QuestionComparison results={results} dataset={dataset} />}
          {activeTab === 'definitions' && <MetricDefinitions />}
          {activeTab === 'dataset' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    {['ID', 'Question', 'Category', 'Answerable', 'Expected Source(s)'].map(h => (
                      <th key={h} style={{ padding: '0.5rem 0.75rem', textAlign: 'left', color: 'var(--text-secondary)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dataset.map(q => (
                    <tr key={q.id} style={{ borderBottom: '1px solid #1a1a1a' }}>
                      <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'monospace', color: '#888' }}>{q.id}</td>
                      <td style={{ padding: '0.5rem 0.75rem', maxWidth: '400px' }}>{q.question}</td>
                      <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)' }}>{q.category}</td>
                      <td style={{ padding: '0.5rem 0.75rem', color: q.answerable ? '#4ade80' : '#ef4444' }}>
                        {q.answerable ? 'YES' : 'NO'}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                        {(q.expected_source || []).join(', ') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Evaluation;
