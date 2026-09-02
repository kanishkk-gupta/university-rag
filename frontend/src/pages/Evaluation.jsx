import React, { useState, useEffect } from 'react';
import { Loader2, Play, RefreshCw } from 'lucide-react';
import { getEvalResults, getEvalSummary, getEvalDataset, runEvaluation } from '../services/api';


// ─── Metric Definitions (matches actual implementation) ─────────────────────
const METRIC_DEFS = [
  {
    name: 'Accuracy',
    label: 'Heuristic Accuracy',
    formula: 'For answerable questions: answer.length > 10 AND not a rejection string\nFor unanswerable: answer contains "couldn\'t find enough information"',
    note: 'Heuristic — not objective accuracy. Error strings may pass the length check.'
  },
  {
    name: 'Relevance',
    label: 'Heuristic Relevance (0–2)',
    formula: '0 if rejection string in answer\n2 otherwise (always 2 for non-rejection)',
    note: 'Binary heuristic only. Does not measure semantic relevance.'
  },
  {
    name: 'Recall@5',
    label: 'Recall@5',
    formula: 'hits / len(expected_sources)\nwhere hits = expected source doc names found in top-5 retrieved chunk metadata',
    note: 'Currently shows 0.0 for all records due to a metadata key path bug in the runner.'
  },
  {
    name: 'Hallucination',
    label: 'Hallucination Rate (CONSTANT)',
    formula: '0.0 if rejection string\n0.1 otherwise (hardcoded constant)',
    note: 'NOT a real measurement. Fixed at 0.1 for all non-rejection answers. Cannot differentiate models.'
  },
  {
    name: 'Latency',
    label: 'Generation Latency (seconds)',
    formula: 'time.time() after generate() call — time.time() before generate() call\nIncludes Ollama connection check + network + inference',
    note: 'Real wall-clock timer. Includes connection timeout when Ollama is unavailable.'
  },
  {
    name: 'Tokens',
    label: 'Token Usage',
    formula: 'prompt_tokens = prompt_eval_count from Ollama response\ncompletion_tokens = eval_count from Ollama response\ntotal_tokens = sum',
    note: 'Real from Ollama. Shows 0 when Ollama is unavailable (generation failed).'
  },
  {
    name: 'CPU / RAM',
    label: 'System Resources',
    formula: 'CPU%: psutil.cpu_percent() — system-level, single snapshot BEFORE generation\nRAM: psutil.virtual_memory().used in MB — system total, not process',
    note: 'Snapshot taken before generation starts. Does not capture peak load during inference.'
  }
];

// ─── Summary Table ───────────────────────────────────────────────────────────
const SummaryTable = ({ results }) => {
  if (!results || results.length === 0) return <p style={{ color: 'var(--text-secondary)' }}>No results available.</p>;

  const models = [...new Set(results.map(r => r.model))];
  const stats = {};

  for (const m of models) {
    const recs = results.filter(r => r.model === m);
    const successful = recs.filter(r => !r.answer.startsWith('Error:'));
    const lats = recs.map(r => r.generation_latency);
    const sorted = [...lats].sort((a, b) => a - b);
    const retr = recs.map(r => r.retrieval_latency);
    const pt = recs.map(r => r.tokens?.prompt_tokens || 0);
    const ct = recs.map(r => r.tokens?.completion_tokens || 0);
    const cpu = recs.map(r => r.resources?.cpu_percent || 0);
    const ram = recs.map(r => r.resources?.ram_mb || 0);
    const acc = recs.map(r => r.metrics?.accuracy || 0);
    const hal = recs.map(r => r.metrics?.hallucination || 0);
    const rec5 = recs.map(r => r.metrics?.recall_at_5 || 0);
    const mean = arr => arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length) : 0;
    const p95 = sorted[Math.floor(sorted.length * 0.95)] || 0;

    stats[m] = {
      total: recs.length,
      successful: successful.length,
      failed: recs.length - successful.length,
      accuracy: mean(acc),
      recall5: mean(rec5),
      hallucination: mean(hal),
      genLatMean: mean(lats),
      genLatMedian: sorted[Math.floor(sorted.length / 2)] || 0,
      genLatP95: p95,
      retrLatMean: mean(retr),
      promptTokens: mean(pt),
      completionTokens: mean(ct),
      cpuMean: mean(cpu),
      ramMean: mean(ram),
    };
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'right' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
            {['Metric', ...models].map(h => (
              <th key={h} style={{ padding: '0.6rem 0.8rem', textAlign: h === 'Metric' ? 'left' : 'right', color: 'var(--text-secondary)', fontWeight: 600 }}>{h.replace('codellama:7b-instruct','Code Llama 7B').replace('starcoder2:3b','StarCoder2 3B').replace('qwen2.5-coder:1.5b','Qwen2.5 1.5B')}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[
            ['Total Questions', m => stats[m].total],
            ['Successful Generations', m => stats[m].successful],
            ['Failed (Ollama down)', m => stats[m].failed],
            ['Heuristic Accuracy *', m => (stats[m].accuracy * 100).toFixed(1) + '%'],
            ['Recall@5 (buggy=0) *', m => stats[m].recall5.toFixed(3)],
            ['Hallucination (fixed 0.1) *', m => stats[m].hallucination.toFixed(3)],
            ['Gen Latency Mean', m => stats[m].genLatMean.toFixed(3) + 's'],
            ['Gen Latency Median', m => stats[m].genLatMedian.toFixed(3) + 's'],
            ['Gen Latency P95', m => stats[m].genLatP95.toFixed(3) + 's'],
            ['Retrieval Latency Mean', m => stats[m].retrLatMean.toFixed(3) + 's'],
            ['Prompt Tokens Mean', m => stats[m].promptTokens.toFixed(0)],
            ['Completion Tokens Mean', m => stats[m].completionTokens.toFixed(0)],
            ['CPU% Mean (pre-gen)', m => stats[m].cpuMean.toFixed(1) + '%'],
            ['RAM MB Mean (pre-gen)', m => stats[m].ramMean.toFixed(0) + ' MB'],
            ['GPU', () => 'unavailable'],
          ].map(([label, fn]) => (
            <tr key={label} style={{ borderBottom: '1px solid #222' }}>
              <td style={{ padding: '0.5rem 0.8rem', textAlign: 'left', color: label.includes('*') ? '#888' : 'var(--text-primary)', fontStyle: label.includes('*') ? 'italic' : 'normal' }}>{label}</td>
              {models.map(m => (
                <td key={m} style={{ padding: '0.5rem 0.8rem', fontFamily: 'monospace' }}>{fn(m)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#666', borderTop: '1px solid #333', paddingTop: '0.75rem' }}>
        <strong>Note:</strong> Evaluation includes heuristic metrics. Wait for the full run to complete for accurate results.
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
                        <div>Accuracy: {rec.metrics?.accuracy ?? '—'}</div>
                        <div>Relevance: {rec.metrics?.relevance ?? '—'}</div>
                        <div>Recall@5: {rec.metrics?.recall_at_5 ?? '—'}</div>
                        <div>Hallucination: {rec.metrics?.hallucination ?? '—'}</div>
                        <div>Gen Lat: {rec.generation_latency?.toFixed(3)}s</div>
                        <div>Retr Lat: {rec.retrieval_latency?.toFixed(3)}s</div>
                        <div>Prompt Tok: {rec.tokens?.prompt_tokens ?? 'N/A'}</div>
                        <div>Compl Tok: {rec.tokens?.completion_tokens ?? 'N/A'}</div>
                        <div>CPU: {rec.resources?.cpu_percent?.toFixed(1)}%</div>
                        <div>RAM: {rec.resources?.ram_mb?.toFixed(0)} MB</div>
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
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('summary');
  const [runningEval, setRunningEval] = useState(false);
  const [runStatus, setRunStatus] = useState(null);

  const fetchData = () => {
    setLoading(true);
    Promise.all([
      getEvalResults().then(d => d.results || []).catch(() => []),
      getEvalDataset().then(d => d.dataset || []).catch(() => []),
    ]).then(([res, ds]) => {
      setResults(res);
      setDataset(ds);
      setLoading(false);
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
          Week 4 — Multi-Model Evaluation: 25 questions × 2 models = 50 controlled generations
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
          {activeTab === 'summary' && <SummaryTable results={results} />}
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
