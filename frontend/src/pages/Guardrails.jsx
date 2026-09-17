import React, { useState, useEffect } from 'react';
import {
  Shield, ShieldCheck, ShieldX, AlertTriangle, CheckCircle,
  XCircle, Play, Loader2, FlaskConical, Activity, Terminal, ChevronDown, ChevronRight
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

// ── Constants ────────────────────────────────────────────────────────────────

const BEFORE_AFTER = [
  {
    scenario: 'Out-of-Scope Question',
    tag: 'ScopeGuard',
    tagColor: '#6366f1',
    query: 'Who is the Prime Minister of India?',
    without: { emoji: '❌', label: 'Problematic', text: 'Model answers from general knowledge → hallucinated response not grounded in any university document.' },
    withGuard: { emoji: '✅', label: 'Controlled', text: 'BLOCKED — "Your question appears to be outside the scope of the BMU University knowledge base. Please ask about university policies, fees, attendance, examinations..."' },
  },
  {
    scenario: 'Excessively Long Input',
    tag: 'InputLengthGuard',
    tagColor: '#8b5cf6',
    query: 'What is the fee structure? '.repeat(22).trim(),
    without: { emoji: '❌', label: 'Problematic', text: 'Long prompts can overload the LLM context window, cause prompt injection attacks, or produce garbled answers.' },
    withGuard: { emoji: '✅', label: 'Controlled', text: 'BLOCKED — "Your query is too long (572 chars). Please limit your question to 500 characters."' },
  },
  {
    scenario: 'Personal Info (PII)',
    tag: 'PIIGuard',
    tagColor: '#f59e0b',
    query: 'My Aadhaar is 1234 5678 9012, what is my fee waiver status?',
    without: { emoji: '❌', label: 'Problematic', text: 'Personal data sent to the LLM and stored in application logs — GDPR/privacy violation risk.' },
    withGuard: { emoji: '✅', label: 'Controlled', text: 'BLOCKED — "Your query appears to contain personal information (Aadhaar-like number). Please do not share personal data."' },
  },
  {
    scenario: 'Inappropriate Language',
    tag: 'ContentGuard',
    tagColor: '#ec4899',
    query: 'What the fuck is the hostel policy?',
    without: { emoji: '❌', label: 'Problematic', text: 'Offensive language passes through → inappropriate LLM interactions, reputational risk for the university system.' },
    withGuard: { emoji: '✅', label: 'Controlled', text: 'BLOCKED — "Your query contains inappropriate language. Please rephrase your question respectfully."' },
  },
  {
    scenario: 'Valid BMU Query',
    tag: null,
    tagColor: '#22c55e',
    query: 'What is the minimum attendance required to appear in exams?',
    without: { emoji: '✅', label: 'Passes Through', text: 'Valid query goes through normally. No difference in behavior for legitimate questions.' },
    withGuard: { emoji: '✅', label: 'Passes Through', text: 'ALLOWED — Passes all 4 input guards → RAG pipeline retrieves context → Grounded answer generated with source citations.' },
  },
];

const GUARDS = [
  { name: 'ScopeGuard', icon: '🎯', type: 'Input', desc: 'Rejects questions outside the BMU university domain using keyword matching against 50+ BMU-specific terms.', color: '#6366f1', example: '"Who invented Python?" → BLOCKED' },
  { name: 'InputLengthGuard', icon: '📏', type: 'Input', desc: 'Rejects queries over 500 characters to prevent prompt injection and LLM context overload.', color: '#8b5cf6', example: '600-char query → BLOCKED' },
  { name: 'ContentGuard', icon: '🚫', type: 'Input', desc: 'Rejects offensive or inappropriate language before it reaches the LLM.', color: '#ec4899', example: '"fuck" in query → BLOCKED' },
  { name: 'PIIGuard', icon: '🔒', type: 'Input', desc: 'Detects and blocks personal identifiable information: Aadhaar, phone numbers, PAN cards, email addresses.', color: '#f59e0b', example: 'Phone: 9876543210 → BLOCKED' },
  { name: 'RefusalConsistencyGuard', icon: '🤔', type: 'Output', desc: 'Flags answers that fail to refuse when no context is available — prevents hallucination without grounding.', color: '#14b8a6', example: 'Answer w/ no context → WARNING' },
  { name: 'ContextGroundingGuard', icon: '📌', type: 'Output', desc: 'Checks that the answer is semantically grounded in retrieved context via cosine similarity (all-MiniLM-L6-v2).', color: '#10b981', example: 'sim < 0.15 → WARNING' },
  { name: 'MinimumLengthGuard', icon: '📝', type: 'Output', desc: 'Flags suspiciously short (<20 chars) or excessively long (>2000 chars) answers — indicative of empty or looping responses.', color: '#3b82f6', example: '"Yes." → WARNING' },
  { name: 'SourceCitationGuard', icon: '📚', type: 'Output', desc: 'Checks that answers include [SOURCE X] citation tags when context was available — ensures traceability.', color: '#06b6d4', example: 'No [SOURCE] tag → INFO' },
];

const OUTPUT_CRITERIA = [
  { criterion: 'Relevance', icon: '🎯', desc: 'Answer addresses the question asked', threshold: 'Semantic similarity(answer, question) ≥ 0.25', color: '#6366f1' },
  { criterion: 'Grounding', icon: '📌', desc: 'Answer is supported by retrieved context', threshold: 'Semantic similarity(answer, context) ≥ 0.25', color: '#10b981' },
  { criterion: 'Hallucination', icon: '⚠️', desc: 'No unsupported numeric/factual claims', threshold: 'Hallucination rate < 0.30', color: '#f59e0b' },
  { criterion: 'Format', icon: '📋', desc: 'Answer follows expected output format', threshold: '[SOURCE X] citation tag present', color: '#8b5cf6' },
  { criterion: 'Refusal', icon: '🚫', desc: 'Refuses appropriately when info unavailable', threshold: 'Refusal phrase present when context empty', color: '#ec4899' },
  { criterion: 'Answerability', icon: '✅', desc: 'Provides answer when sufficient context exists', threshold: 'No refusal when context available', color: '#14b8a6' },
  { criterion: 'LengthSanity', icon: '📏', desc: 'Answer is within reasonable length bounds', threshold: '20 < len(answer) < 2000 chars', color: '#3b82f6' },
];

// ── Shared styles ─────────────────────────────────────────────────────────────
const card = (extra = {}) => ({
  background: 'var(--panel-bg)',
  border: '1px solid var(--border-color)',
  borderRadius: '12px',
  padding: '1.5rem',
  ...extra,
});

const statusBadge = (passed) => ({
  display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
  padding: '0.25rem 0.7rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 700,
  background: passed ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
  color: passed ? '#22c55e' : '#ef4444',
});

// ── Stat Card ────────────────────────────────────────────────────────────────
const Stat = ({ label, value, color = 'var(--text-primary)' }) => (
  <div style={{ textAlign: 'center', background: 'var(--bg-color)', borderRadius: '10px', padding: '1rem' }}>
    <div style={{ fontSize: '2.2rem', fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.3rem', letterSpacing: '0.05em' }}>{label}</div>
  </div>
);

// ── Live Input Tester ────────────────────────────────────────────────────────
const LiveTester = () => {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const test = async () => {
    if (!query.trim()) return;
    setLoading(true); setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/guardrails/check`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      setResult(await res.json());
    } catch (e) { setResult({ error: e.message }); }
    finally { setLoading(false); }
  };

  const presets = [
    'What is the minimum attendance for exams?',
    'Who is the President of America?',
    'My Aadhaar is 1234 5678 9012, fee waiver?',
    'What the fuck is the hostel policy?',
    'W'.repeat(600),
  ];

  return (
    <div style={card()}>
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Terminal size={16} color="var(--accent-color)" /> Live Input Guardrail Tester
      </h3>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
        {presets.map((p, i) => (
          <button key={i} onClick={() => setQuery(p)} style={{
            fontSize: '0.72rem', padding: '0.3rem 0.65rem', borderRadius: '6px', border: '1px solid var(--border-color)',
            background: 'var(--bg-color)', color: 'var(--text-secondary)', cursor: 'pointer', maxWidth: '180px',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
          }} title={p}>Preset {i + 1}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '0.75rem' }}>
        <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && test()}
          placeholder="Type or paste a query to test..." className="input" style={{ flex: 1, fontSize: '0.9rem' }} />
        <button className="btn" onClick={test} disabled={loading || !query.trim()} style={{ whiteSpace: 'nowrap' }}>
          {loading ? <Loader2 size={15} className="spin" /> : <><Play size={14} /> Test</>}
        </button>
      </div>
      {result && !result.error && (
        <div style={{
          padding: '1rem', borderRadius: '8px',
          background: result.passed ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${result.passed ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.4)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: result.reason ? '0.5rem' : 0 }}>
            {result.passed ? <ShieldCheck size={18} color="#22c55e" /> : <ShieldX size={18} color="#ef4444" />}
            <span style={{ fontWeight: 700, color: result.passed ? '#22c55e' : '#ef4444', fontSize: '0.9rem' }}>
              {result.passed ? '✅ ALLOWED — All guards passed' : `🚫 BLOCKED by ${result.blocked_by}`}
            </span>
          </div>
          {result.reason && !result.passed && (
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{result.reason}</p>
          )}
        </div>
      )}
    </div>
  );
};

// ── Guardrail Test Results Panel ─────────────────────────────────────────────
const GuardrailTestResults = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({});

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/tests/guardrails`);
      setData(await res.json());
    } catch (e) { setData({ error: e.message }); }
    finally { setLoading(false); }
  };

  const catLabels = { OUT: 'Out-of-Scope', LEN: 'Long Input', CON: 'Content', PII: 'PII', VAL: 'Valid' };
  const catColors = { OUT: '#ef4444', LEN: '#f59e0b', CON: '#ec4899', PII: '#f59e0b', VAL: '#22c55e' };

  const grouped = data?.input_tests?.reduce((acc, t) => {
    const k = t.id.slice(0, 3);
    if (!acc[k]) acc[k] = [];
    acc[k].push(t);
    return acc;
  }, {}) || {};

  return (
    <div style={card()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FlaskConical size={16} color="var(--accent-color)" /> Guardrail Test Set — {data ? `${data.passed}/${data.total} passed` : '22 cases (17 input + 5 output)'}
        </h3>
        <button className="btn" onClick={run} disabled={loading} style={{ fontSize: '0.8rem', padding: '0.4rem 0.9rem' }}>
          {loading ? <><Loader2 size={13} className="spin" /> Running...</> : '▶ Run All'}
        </button>
      </div>

      {data && !data.error && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <Stat label="TOTAL TESTS" value={data.total} />
            <Stat label="PASSED" value={data.passed} color="#22c55e" />
            <Stat label="FAILED" value={data.failed} color={data.failed > 0 ? '#ef4444' : '#22c55e'} />
            <Stat label="PASS RATE" value={`${(data.pass_rate * 100).toFixed(0)}%`} color={data.pass_rate === 1 ? '#22c55e' : '#f59e0b'} />
          </div>

          {/* Input tests grouped by category */}
          <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>INPUT GUARDRAIL TESTS</h4>
          {Object.entries(grouped).map(([cat, tests]) => {
            const allPass = tests.every(t => t.passed_test);
            const isOpen = expanded[cat] !== false;
            return (
              <div key={cat} style={{ marginBottom: '0.6rem', border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
                <button onClick={() => setExpanded(e => ({ ...e, [cat]: !isOpen }))}
                  style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.65rem 1rem', background: 'var(--bg-color)', border: 'none', cursor: 'pointer', color: 'var(--text-primary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: catColors[cat] || '#888' }} />
                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{catLabels[cat] || cat}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{tests.length} tests</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={statusBadge(allPass)}>{allPass ? '✅ ALL PASS' : '❌ FAIL'}</span>
                    {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </div>
                </button>
                {isOpen && (
                  <div style={{ padding: '0.5rem 1rem 0.75rem' }}>
                    {tests.map(t => (
                      <div key={t.id} style={{ display: 'flex', gap: '0.6rem', alignItems: 'flex-start', padding: '0.5rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        {t.passed_test ? <CheckCircle size={14} color="#22c55e" style={{ marginTop: 3, flexShrink: 0 }} /> : <XCircle size={14} color="#ef4444" style={{ marginTop: 3, flexShrink: 0 }} />}
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: 'var(--accent-color)' }}>[{t.id}]</span>
                            <span style={{ fontSize: '0.75rem' }}>
                              Expected: <b style={{ color: t.expected === 'PASS' ? '#22c55e' : '#f59e0b' }}>{t.expected}</b> →
                              Got: <b style={{ color: t.actual === 'PASS' ? '#22c55e' : t.passed_test ? '#f59e0b' : '#ef4444' }}>{t.actual}</b>
                            </span>
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginTop: '0.15rem' }}>{t.description}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem', fontStyle: 'italic' }}>
                            "{t.query_preview}"
                          </div>
                          {t.blocked_by && <span style={{ fontSize: '0.7rem', color: '#6366f1', marginTop: '0.2rem', display: 'block' }}>🛡 {t.blocked_by}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* Output tests */}
          <h4 style={{ margin: '1.25rem 0 0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>OUTPUT GUARDRAIL TESTS</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {data.output_tests?.map(t => (
              <div key={t.id} style={{
                display: 'flex', gap: '0.6rem', alignItems: 'flex-start', padding: '0.65rem 0.85rem',
                borderRadius: '7px',
                background: t.passed_test ? 'rgba(34,197,94,0.05)' : 'rgba(239,68,68,0.07)',
                border: `1px solid ${t.passed_test ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.25)'}`,
              }}>
                {t.passed_test ? <CheckCircle size={14} color="#22c55e" style={{ marginTop: 3, flexShrink: 0 }} /> : <XCircle size={14} color="#ef4444" style={{ marginTop: 3, flexShrink: 0 }} />}
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: 'var(--accent-color)' }}>[{t.id}]</span>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <span style={{ ...statusBadge(t.refusal_ok), fontSize: '0.68rem' }}>Refusal {t.refusal_ok ? '✅' : '❌'}</span>
                      <span style={{ ...statusBadge(t.length_ok), fontSize: '0.68rem' }}>Length {t.length_ok ? '✅' : '❌'}</span>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginTop: '0.15rem' }}>{t.description}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem', fontStyle: 'italic' }}>"{t.answer_preview}"</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {!data && !loading && (
        <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem 0', fontSize: '0.9rem' }}>
          Click <strong>▶ Run All</strong> to execute the full guardrail test suite.
        </p>
      )}
    </div>
  );
};

// ── Output Quality Test Panel ─────────────────────────────────────────────────
const OutputQualityTests = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/tests/output-quality`);
      setData(await res.json());
    } catch (e) { setData({ error: e.message }); }
    finally { setLoading(false); }
  };

  const criteriaColors = {
    Relevance: '#6366f1', Grounding: '#10b981', Hallucination: '#f59e0b',
    Format: '#8b5cf6', Refusal: '#ec4899', Answerability: '#14b8a6', LengthSanity: '#3b82f6',
  };

  return (
    <div style={card()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={16} color="var(--accent-color)" /> AI Output Quality Tests — 7 Criteria, 24 Test Cases
        </h3>
        <button className="btn" onClick={run} disabled={loading} style={{ fontSize: '0.8rem', padding: '0.4rem 0.9rem' }}>
          {loading ? <><Loader2 size={13} className="spin" /> Running (~15s)...</> : '▶ Run pytest'}
        </button>
      </div>

      {/* Criteria reference cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px,1fr))', gap: '0.65rem', marginBottom: '1.5rem' }}>
        {OUTPUT_CRITERIA.map(c => {
          const resultGroup = data?.criteria?.find(g => g.criterion === c.criterion);
          return (
            <div key={c.criterion} style={{
              padding: '0.85rem 1rem', borderRadius: '8px', background: 'var(--bg-color)',
              borderLeft: `3px solid ${c.color}`,
              border: `1px solid ${c.color}33`,
              borderLeftWidth: '3px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.3rem' }}>
                <span style={{ fontSize: '0.9rem' }}>{c.icon} <strong style={{ color: 'var(--text-primary)' }}>{c.criterion}</strong></span>
                {resultGroup && (
                  <span style={statusBadge(resultGroup.passed === resultGroup.total)}>
                    {resultGroup.passed}/{resultGroup.total}
                  </span>
                )}
              </div>
              <p style={{ margin: '0 0 0.25rem', fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{c.desc}</p>
              <p style={{ margin: 0, fontSize: '0.7rem', color: c.color, fontFamily: 'monospace' }}>Pass: {c.threshold}</p>
            </div>
          );
        })}
      </div>

      {data && !data.error && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <Stat label="TOTAL TESTS" value={data.total} />
            <Stat label="PASSED" value={data.passed} color="#22c55e" />
            <Stat label="FAILED" value={data.failed} color={data.failed > 0 ? '#ef4444' : '#22c55e'} />
            <Stat label="PASS RATE" value={`${(data.pass_rate * 100).toFixed(0)}%`} color={data.pass_rate >= 0.9 ? '#22c55e' : '#f59e0b'} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {data.raw_tests?.map((t, i) => {
              const color = criteriaColors[t.criterion] || '#888';
              return (
                <div key={i} style={{
                  display: 'flex', gap: '0.7rem', alignItems: 'center', padding: '0.55rem 0.85rem',
                  borderRadius: '7px',
                  background: t.passed ? 'rgba(34,197,94,0.04)' : 'rgba(239,68,68,0.07)',
                  border: `1px solid ${t.passed ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.25)'}`,
                }}>
                  {t.passed ? <CheckCircle size={14} color="#22c55e" style={{ flexShrink: 0 }} /> : <XCircle size={14} color="#ef4444" style={{ flexShrink: 0 }} />}
                  <span style={{ width: '90px', flexShrink: 0, fontSize: '0.72rem', fontWeight: 700, color, letterSpacing: '0.03em' }}>{t.criterion}</span>
                  <span style={{ flex: 1, fontSize: '0.8rem', color: 'var(--text-primary)' }}>{t.test}</span>
                  <span style={statusBadge(t.passed)}>{t.status}</span>
                </div>
              );
            })}
          </div>
        </>
      )}
      {data?.error && <p style={{ color: '#ef4444', fontSize: '0.85rem' }}>Error: {data.error}</p>}
      {!data && !loading && (
        <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '1.5rem 0', fontSize: '0.9rem' }}>
          Click <strong>▶ Run pytest</strong> to execute all 24 output quality tests (~15 seconds).
        </p>
      )}
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────
const Guardrails = () => {
  const [activeScenario, setActiveScenario] = useState(0);
  const [tab, setTab] = useState('overview'); // overview | tests | quality

  const tabs = [
    { id: 'overview', label: '🛡 Guards & Demo' },
    { id: 'tests', label: '🧪 Guardrail Tests' },
    { id: 'quality', label: '📊 Output Quality Tests' },
  ];

  const s = BEFORE_AFTER[activeScenario];

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: '50%', background: 'rgba(99,102,241,0.15)', marginBottom: '1rem' }}>
          <Shield size={28} color="#6366f1" />
        </div>
        <h1 style={{ fontSize: '2rem', margin: '0 0 0.6rem' }}>Guardrails & AI Output Testing</h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto', lineHeight: 1.6 }}>
          Input/output safety controls that make the BMU RAG system reliable, controlled, and trustworthy.
          8 active guards · 22 guardrail tests · 24 output quality tests.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '0.6rem 1.2rem', border: 'none', background: 'transparent', cursor: 'pointer',
            fontSize: '0.85rem', fontWeight: 600, color: tab === t.id ? 'var(--accent-color)' : 'var(--text-secondary)',
            borderBottom: `2px solid ${tab === t.id ? 'var(--accent-color)' : 'transparent'}`,
            marginBottom: '-1px', transition: 'all 0.15s',
          }}>{t.label}</button>
        ))}
      </div>

      {/* Tab: Overview */}
      {tab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Guard Inventory */}
          <div>
            <h2 style={{ fontSize: '1.15rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Active Guards</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(270px,1fr))', gap: '0.85rem' }}>
              {GUARDS.map(g => (
                <div key={g.name} style={{ ...card(), borderLeft: `4px solid ${g.color}`, padding: '1rem', border: `1px solid ${g.color}22`, borderLeftWidth: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                    <span style={{ fontSize: '1.2rem' }}>{g.icon}</span>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>{g.name}</div>
                      <div style={{ fontSize: '0.68rem', color: g.color, fontWeight: 700, letterSpacing: '0.04em' }}>{g.type.toUpperCase()} GUARD</div>
                    </div>
                  </div>
                  <p style={{ margin: '0 0 0.4rem', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{g.desc}</p>
                  <p style={{ margin: 0, fontSize: '0.72rem', color: g.color, fontFamily: 'monospace' }}>{g.example}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Before/After */}
          <div>
            <h2 style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>Before / After Demonstration</h2>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
              {BEFORE_AFTER.map((sc, i) => (
                <button key={i} onClick={() => setActiveScenario(i)} style={{
                  padding: '0.4rem 0.85rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
                  border: `1px solid ${activeScenario === i ? 'var(--accent-color)' : 'var(--border-color)'}`,
                  background: activeScenario === i ? 'var(--accent-color)' : 'var(--panel-bg)',
                  color: activeScenario === i ? '#fff' : 'var(--text-secondary)',
                  transition: 'all 0.15s',
                }}>{sc.scenario}</button>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
              {/* Without */}
              <div style={{ ...card(), border: '1px solid rgba(239,68,68,0.3)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <ShieldX size={18} color="#ef4444" />
                  <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#ef4444' }}>Without Guardrail</h3>
                </div>
                <div style={{ background: '#080808', borderRadius: '6px', padding: '0.7rem', marginBottom: '0.85rem', fontFamily: 'monospace', fontSize: '0.75rem', color: '#555', wordBreak: 'break-all', lineHeight: 1.5 }}>
                  Query: "{s.query.slice(0, 120)}{s.query.length > 120 ? '...' : ''}"
                </div>
                <div style={{ padding: '0.85rem', background: 'rgba(239,68,68,0.07)', borderRadius: '8px', lineHeight: 1.6 }}>
                  <div style={{ fontWeight: 700, color: '#ef4444', marginBottom: '0.35rem', fontSize: '0.85rem' }}>{s.without.emoji} {s.without.label}</div>
                  <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{s.without.text}</p>
                </div>
              </div>
              {/* With */}
              <div style={{ ...card(), border: '1px solid rgba(34,197,94,0.3)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <ShieldCheck size={18} color="#22c55e" />
                  <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#22c55e' }}>With Guardrail</h3>
                </div>
                <div style={{ background: '#080808', borderRadius: '6px', padding: '0.7rem', marginBottom: '0.85rem', fontFamily: 'monospace', fontSize: '0.75rem', color: '#555', wordBreak: 'break-all', lineHeight: 1.5 }}>
                  Query: "{s.query.slice(0, 120)}{s.query.length > 120 ? '...' : ''}"
                </div>
                <div style={{ padding: '0.85rem', background: 'rgba(34,197,94,0.07)', borderRadius: '8px', lineHeight: 1.6 }}>
                  <div style={{ fontWeight: 700, color: '#22c55e', marginBottom: '0.35rem', fontSize: '0.85rem' }}>{s.withGuard.emoji} {s.withGuard.label}</div>
                  <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{s.withGuard.text}</p>
                </div>
                {s.tag && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Shield size={12} color={s.tagColor} />
                    <span style={{ fontSize: '0.72rem', color: s.tagColor, fontWeight: 700 }}>{s.tag}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Live tester */}
          <div>
            <h2 style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>Live Tester</h2>
            <LiveTester />
          </div>
        </div>
      )}

      {/* Tab: Guardrail Tests */}
      {tab === 'tests' && <GuardrailTestResults />}

      {/* Tab: Output Quality Tests */}
      {tab === 'quality' && <OutputQualityTests />}
    </div>
  );
};

export default Guardrails;
