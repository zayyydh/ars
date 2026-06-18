import React, { useState, useCallback } from "react";

// ── Helpers ──────────────────────────────────────────────────────────────────

const verdictConfig = {
  SHORTLIST: { label: "Strong Match",  color: "#10b981", bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.35)" },
  REVIEW:    { label: "Partial Match", color: "#f59e0b", bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.35)" },
  REJECT:    { label: "Low Match",     color: "#ef4444", bg: "rgba(239,68,68,0.12)",  border: "rgba(239,68,68,0.35)"  },
};

const scoreColor = (v) =>
  v >= 70 ? "#10b981" : v >= 45 ? "#f59e0b" : "#ef4444";

// ── Sub-components ────────────────────────────────────────────────────────────

function ScoreRing({ value }) {
  const r = 36, cx = 44, cy = 44;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  const col = scoreColor(value);
  return (
    <svg width={88} height={88} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={7} />
      <circle
        cx={cx} cy={cy} r={r} fill="none"
        stroke={col} strokeWidth={7}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)" }}
      />
      <text
        x={cx} y={cy + 1}
        textAnchor="middle" dominantBaseline="middle"
        fill={col} fontSize={15} fontWeight={600}
        style={{ transform: "rotate(90deg)", transformOrigin: `${cx}px ${cy}px` }}
      >
        {Math.round(value)}
      </text>
    </svg>
  );
}

function ScoreBar({ value, color }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.07)", borderRadius: 99, height: 6, overflow: "hidden", marginTop: 6 }}>
      <div style={{
        width: `${Math.min(100, Math.max(0, value))}%`,
        height: "100%",
        background: color,
        borderRadius: 99,
        transition: "width 1s cubic-bezier(.4,0,.2,1)",
      }} />
    </div>
  );
}

function Pill({ label, type }) {
  const styles = {
    matched:  { bg: "rgba(16,185,129,0.12)", color: "#6ee7b7", border: "rgba(16,185,129,0.3)" },
    missing:  { bg: "rgba(239,68,68,0.12)",  color: "#fca5a5", border: "rgba(239,68,68,0.3)"  },
    extra:    { bg: "rgba(99,102,241,0.12)", color: "#a5b4fc", border: "rgba(99,102,241,0.3)" },
  };
  const s = styles[type] || styles.extra;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "3px 10px", borderRadius: 99, fontSize: 12,
      background: s.bg, color: s.color,
      border: `0.5px solid ${s.border}`,
      margin: "3px 3px",
    }}>
      {type === "matched" && <span style={{ fontSize: 10 }}>✓</span>}
      {type === "missing" && <span style={{ fontSize: 10 }}>✕</span>}
      {label}
    </span>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      border: "0.5px solid rgba(255,255,255,0.09)",
      borderRadius: 16,
      padding: "20px 22px",
      ...style,
    }}>
      {children}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: "0.08em",
      color: "rgba(255,255,255,0.35)", textTransform: "uppercase",
      marginBottom: 12,
    }}>
      {children}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AiResumeScreener() {
  const [file,        setFile]        = useState(null);
  const [jd,          setJd]          = useState("");
  const [loading,     setLoading]     = useState(false);
  const [result,      setResult]      = useState(null);
  const [error,       setError]       = useState("");
  const [dragging,    setDragging]    = useState(false);

  const handleFile = useCallback((f) => {
    if (f && (f.name.endsWith(".pdf") || f.name.endsWith(".docx") || f.name.endsWith(".doc"))) {
      setFile(f);
      setError("");
    } else if (f) {
      setError("Please upload a PDF or DOCX file.");
    }
  }, []);

  const handleSubmit = async () => {
    if (!file)        return setError("Please upload a resume file.");
    if (jd.trim().length < 20) return setError("Please paste a job description (at least 20 characters).");

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const form = new FormData();
      form.append("resume", file);
      form.append("job_description", jd);

      const res = await fetch("http://localhost:5000/api/screen", {
        method: "POST",
        body: form,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Server error");
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const vc = result ? (verdictConfig[result.verdict] || verdictConfig.REVIEW) : null;

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0f0c29 0%, #1a1040 50%, #0f0c29 100%)",
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      color: "#f1f5f9",
      padding: "40px 16px 60px",
    }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>

        {/* ── Header ── */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "rgba(16,185,129,0.1)",
            border: "0.5px solid rgba(16,185,129,0.35)",
            borderRadius: 99, padding: "5px 14px",
            fontSize: 12, color: "#6ee7b7", marginBottom: 18,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%",
              background: "#10b981",
              boxShadow: "0 0 8px #10b981",
              animation: "pulse 2s infinite",
            }} />
            Live · Powered by AI
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 700, margin: "0 0 10px", letterSpacing: "-0.02em" }}>
            AI Resume Screener
          </h1>
          <p style={{ fontSize: 15, color: "rgba(255,255,255,0.45)", maxWidth: 500, margin: "0 auto" }}>
            Upload a resume, paste a job description, and get an instant AI-powered match score with skill gap analysis.
          </p>
        </div>

        {/* ── Two-column layout ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>

          {/* ── LEFT: Input ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* File drop zone */}
            <Card>
              <SectionLabel>1. Upload resume</SectionLabel>
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
                onClick={() => document.getElementById("file-input").click()}
                style={{
                  border: `1.5px dashed ${dragging ? "#10b981" : "rgba(255,255,255,0.15)"}`,
                  borderRadius: 12,
                  padding: "28px 16px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: dragging ? "rgba(16,185,129,0.05)" : "rgba(255,255,255,0.02)",
                  transition: "all 0.2s",
                }}
              >
                {file ? (
                  <>
                    <div style={{ fontSize: 28, marginBottom: 6 }}>📄</div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "#6ee7b7" }}>{file.name}</div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginTop: 3 }}>
                      {(file.size / 1024).toFixed(0)} KB · click to change
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ fontSize: 28, marginBottom: 6 }}>⬆</div>
                    <div style={{ fontSize: 13, color: "rgba(255,255,255,0.7)" }}>
                      Drag & drop your resume here
                    </div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginTop: 3 }}>
                      or click to browse · PDF, DOCX · max 10 MB
                    </div>
                  </>
                )}
              </div>
              <input id="file-input" type="file" accept=".pdf,.doc,.docx"
                style={{ display: "none" }}
                onChange={e => handleFile(e.target.files[0])} />
            </Card>

            {/* JD textarea */}
            <Card style={{ flex: 1 }}>
              <SectionLabel>2. Paste job description</SectionLabel>
              <textarea
                value={jd}
                onChange={e => setJd(e.target.value)}
                placeholder="Paste the full job description here — requirements, skills, qualifications..."
                rows={9}
                style={{
                  width: "100%", boxSizing: "border-box",
                  background: "rgba(255,255,255,0.04)",
                  border: "0.5px solid rgba(255,255,255,0.1)",
                  borderRadius: 10, padding: "10px 12px",
                  fontSize: 13, color: "#f1f5f9",
                  lineHeight: 1.6, resize: "vertical",
                  fontFamily: "inherit", outline: "none",
                }}
              />
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginTop: 4 }}>
                {jd.length} characters
              </div>
            </Card>

            {/* Error */}
            {error && (
              <div style={{
                background: "rgba(239,68,68,0.1)",
                border: "0.5px solid rgba(239,68,68,0.35)",
                borderRadius: 10, padding: "10px 14px",
                fontSize: 13, color: "#fca5a5",
              }}>
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={loading}
              style={{
                width: "100%", padding: "13px",
                borderRadius: 12, border: "none",
                background: loading
                  ? "rgba(16,185,129,0.4)"
                  : "linear-gradient(135deg, #10b981, #059669)",
                color: "#fff", fontSize: 14, fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center",
                justifyContent: "center", gap: 8,
                transition: "all 0.2s",
                boxShadow: loading ? "none" : "0 4px 20px rgba(16,185,129,0.3)",
              }}
            >
              {loading ? (
                <>
                  <span style={{
                    width: 16, height: 16,
                    border: "2px solid rgba(255,255,255,0.3)",
                    borderTopColor: "#fff",
                    borderRadius: "50%",
                    animation: "spin 0.8s linear infinite",
                    display: "inline-block",
                  }} />
                  Analyzing resume...
                </>
              ) : "Run AI screening →"}
            </button>
          </div>

          {/* ── RIGHT: Results ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {!result && !loading && (
              <Card style={{ flex: 1, display: "flex", flexDirection: "column",
                            alignItems: "center", justifyContent: "center",
                            minHeight: 400, textAlign: "center" }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>📄✨</div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "rgba(255,255,255,0.5)", marginBottom: 8 }}>
                  Results will appear here
                </div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.25)", maxWidth: 240 }}>
                  Upload a resume and paste a job description to see the match score, skill gaps, and suggestions.
                </div>
              </Card>
            )}

            {loading && (
              <Card style={{ flex: 1, display: "flex", flexDirection: "column",
                            alignItems: "center", justifyContent: "center", minHeight: 400 }}>
                <div style={{
                  width: 48, height: 48,
                  border: "3px solid rgba(255,255,255,0.1)",
                  borderTopColor: "#10b981",
                  borderRadius: "50%",
                  animation: "spin 0.8s linear infinite",
                  marginBottom: 20,
                }} />
                <div style={{ fontSize: 14, color: "rgba(255,255,255,0.6)" }}>
                  Parsing resume, extracting skills...
                </div>
              </Card>
            )}

            {result && !loading && (
              <>
                {/* Overall score */}
                <Card>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                      <SectionLabel>Overall match</SectionLabel>
                      <div style={{ fontSize: 42, fontWeight: 700, lineHeight: 1,
                                    color: scoreColor(result.overall_score) }}>
                        {Math.round(result.overall_score)}
                        <span style={{ fontSize: 18, fontWeight: 400, color: "rgba(255,255,255,0.3)" }}>/100</span>
                      </div>
                      <div style={{ marginTop: 12 }}>
                        <span style={{
                          display: "inline-block",
                          padding: "4px 14px", borderRadius: 99,
                          fontSize: 12, fontWeight: 600,
                          background: vc.bg, color: vc.color,
                          border: `0.5px solid ${vc.border}`,
                        }}>
                          {vc.label}
                        </span>
                      </div>
                    </div>
                    <ScoreRing value={result.overall_score} />
                  </div>
                </Card>

                {/* Dimension scores */}
                <Card>
                  <SectionLabel>Score breakdown</SectionLabel>
                  <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    {[
                      { label: "Skills match",     value: result.skills_score },
                      { label: "Experience match",  value: result.experience_score },
                      { label: "Education match",   value: result.education_score },
                    ].map(d => (
                      <div key={d.label}>
                        <div style={{ display: "flex", justifyContent: "space-between",
                                      fontSize: 13, color: "rgba(255,255,255,0.7)" }}>
                          <span>{d.label}</span>
                          <span style={{ fontWeight: 600, color: scoreColor(d.value) }}>
                            {Math.round(d.value)}
                          </span>
                        </div>
                        <ScoreBar value={d.value} color={scoreColor(d.value)} />
                      </div>
                    ))}
                  </div>
                </Card>

                {/* Skill pills */}
                <Card>
                  <SectionLabel>Skill gap analysis</SectionLabel>
                  {result.matched_skills?.length > 0 && (
                    <div style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginBottom: 5 }}>
                        Matched
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap" }}>
                        {result.matched_skills.map(s => <Pill key={s} label={s} type="matched" />)}
                      </div>
                    </div>
                  )}
                  {result.missing_skills?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginBottom: 5 }}>
                        Missing
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap" }}>
                        {result.missing_skills.map(s => <Pill key={s} label={s} type="missing" />)}
                      </div>
                    </div>
                  )}
                </Card>

                {/* Suggestions */}
                {result.suggestions?.length > 0 && (
                  <Card>
                    <SectionLabel>AI suggestions</SectionLabel>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {result.suggestions.map((s, i) => (
                        <div key={i} style={{
                          display: "flex", gap: 10, alignItems: "flex-start",
                          fontSize: 13, color: "rgba(255,255,255,0.65)",
                          lineHeight: 1.5,
                        }}>
                          <span style={{ color: "#f59e0b", flexShrink: 0, marginTop: 1 }}>→</span>
                          {s}
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin  { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
        * { box-sizing: border-box; }
        textarea::placeholder { color: rgba(255,255,255,0.2); }
        textarea:focus { border-color: rgba(16,185,129,0.5) !important; }
        button:hover:not(:disabled) { transform: translateY(-1px); }
      `}</style>
    </div>
  );
}