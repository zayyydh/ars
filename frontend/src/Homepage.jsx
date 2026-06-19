import React, { useState, useCallback, useEffect, useRef } from "react";

const C = {
  bg:            "#f5f4f0",
  surface:       "#ffffff",
  surfaceAlt:    "#f9f8f5",
  border:        "rgba(15,14,20,0.10)",
  borderStrong:  "rgba(15,14,20,0.18)",
  text:          "#15141a",
  textDim:       "rgba(21,20,26,0.55)",
  textFaint:     "rgba(21,20,26,0.35)",
  accent:        "#4f46e5",
  accentLight:   "rgba(79,70,229,0.08)",
  accentBorder:  "rgba(79,70,229,0.25)",
  shadow:        "0 1px 3px rgba(15,14,20,0.06), 0 6px 20px rgba(15,14,20,0.07)",
  shadowSm:      "0 1px 2px rgba(15,14,20,0.05)",
};

const SIG = {
  good: { c: "#16a34a", bg: "rgba(22,163,74,0.08)",   border: "rgba(22,163,74,0.22)" },
  mid:  { c: "#b45309", bg: "rgba(180,83,9,0.08)",    border: "rgba(180,83,9,0.22)"  },
  bad:  { c: "#dc2626", bg: "rgba(220,38,38,0.08)",   border: "rgba(220,38,38,0.22)" },
};

const VERDICT = {
  SHORTLIST: { label: "Strong match",  ...SIG.good },
  REVIEW:    { label: "Partial match", ...SIG.mid  },
  REJECT:    { label: "Low match",     ...SIG.bad  },
};

const sigFor = v => v >= 70 ? SIG.good : v >= 45 ? SIG.mid : SIG.bad;

const MOCK = {
  overall_score: 78, verdict: "SHORTLIST",
  skills_score: 84, experience_score: 76, education_score: 70,
  matched_skills: ["React", "TypeScript", "Node.js", "REST APIs", "PostgreSQL", "Docker"],
  missing_skills: ["GraphQL", "Kubernetes"],
  suggestions: [
    "Quantify the platform migration impact — numbers make senior scope easier to verify.",
    "Surface any GraphQL exposure from side projects — it's the largest gap against this role.",
    "Lead with your most recent title; the resume currently buries it under the summary.",
  ],
};

function useCountUp(target, { duration = 950, start = false, delay = 0 } = {}) {
  const [val, setVal] = useState(0);
  const raf = useRef(null);
  useEffect(() => {
    if (!start) { setVal(0); return; }
    let startTime = null;
    const tid = setTimeout(() => {
      raf.current = requestAnimationFrame(function tick(now) {
        if (!startTime) startTime = now;
        const t = Math.min(1, (now - startTime) / duration);
        setVal(target * (1 - Math.pow(1 - t, 3)));
        if (t < 1) raf.current = requestAnimationFrame(tick);
      });
    }, delay);
    return () => { clearTimeout(tid); if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target, start, duration, delay]);
  return val;
}

function ScoreRing({ value, active }) {
  const animated = useCountUp(value, { duration: 1100, start: active, delay: 500 });
  const r = 42, cx = 50, cy = 50, circ = 2 * Math.PI * r;
  const sig = sigFor(value);
  return (
    <svg width={100} height={100} viewBox="0 0 100 100" style={{ transform: "rotate(-90deg)", flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#f0eeea" strokeWidth={7}/>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={sig.c} strokeWidth={7}
        strokeDasharray={circ} strokeDashoffset={active ? circ - (animated / 100) * circ : circ}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1.1s cubic-bezier(.16,1,.3,1)", transitionDelay: "0.5s" }}/>
      <text x={cx} y={cy + 1.5} textAnchor="middle" dominantBaseline="middle"
        fill={sig.c} fontSize={22} fontWeight={600}
        fontFamily="ui-monospace, 'JetBrains Mono', monospace"
        style={{ transform: "rotate(90deg)", transformOrigin: `${cx}px ${cy}px` }}>
        {Math.round(animated)}
      </text>
    </svg>
  );
}

function ScoreBar({ value, delay = 0, active }) {
  const sig = sigFor(value);
  return (
    <div style={{ background: "#f0eeea", borderRadius: 99, height: 5, overflow: "hidden" }}>
      <div style={{
        width: active ? `${Math.min(100, value)}%` : "0%",
        height: "100%", background: sig.c, borderRadius: 99,
        transition: `width 0.85s cubic-bezier(.16,1,.3,1) ${delay}ms`,
      }}/>
    </div>
  );
}

function Pill({ label, type, style = {} }) {
  const s = type === "matched" ? SIG.good : SIG.bad;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: 99, fontSize: 12.5, fontWeight: 500,
      background: s.bg, color: s.c, border: `1px solid ${s.border}`,
      margin: "3px 4px 0 0", ...style,
    }}>
      <span style={{ fontSize: 10 }}>{type === "matched" ? "✓" : "✕"}</span>
      {label}
    </span>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: "22px 22px", boxShadow: C.shadow, ...style,
    }}>
      {children}
    </div>
  );
}

function Label({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: "0.08em",
      color: C.textFaint, textTransform: "uppercase",
      marginBottom: 14, fontFamily: "ui-monospace, monospace",
    }}>
      {children}
    </div>
  );
}

function ScanLoader() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20 }}>
      <svg width={200} height={140} viewBox="0 0 200 140" style={{ overflow: "visible" }}>
        <defs>
          <clipPath id="clip"><rect x="24" y="4" width="152" height="132" rx="8"/></clipPath>
          <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={C.accent} stopOpacity="0"/>
            <stop offset="50%"  stopColor={C.accent} stopOpacity="0.45"/>
            <stop offset="100%" stopColor={C.accent} stopOpacity="0"/>
          </linearGradient>
        </defs>
        <rect x="24" y="4" width="152" height="132" rx="8" fill={C.surface} stroke={C.border} strokeWidth="1"/>
        {[18,32,46,60,74,88,102,116,128].map((y,i) => (
          <rect key={y} x="40" y={y} width={i%3===0?80:110-(i*3)%32} height="6" rx="3" fill="#ede9e3"/>
        ))}
        <g clipPath="url(#clip)">
          <rect x="24" y="-24" width="152" height="40" fill="url(#beam)">
            <animate attributeName="y" values="-28;140;-28" dur="2s" repeatCount="indefinite"/>
          </rect>
        </g>
        <line x1="24" y1="0" x2="24" y2="140" stroke={C.border} strokeWidth="1"/>
        <line x1="176" y1="0" x2="176" y2="140" stroke={C.border} strokeWidth="1"/>
      </svg>
      <p style={{ margin: 0, fontSize: 13, color: C.textDim, fontFamily: "ui-monospace, monospace" }}>
        Reading resume · matching skills…
      </p>
    </div>
  );
}

export default function ResumeScreener() {
  const [file,    setFile]    = useState(null);
  const [jd,      setJd]      = useState("");
  const [loading, setLoading] = useState(false);
  const [result,  setResult]  = useState(null);
  const [error,   setError]   = useState("");
  const [drag,    setDrag]    = useState(false);
  const [stage,   setStage]   = useState(0);

  const active = stage >= 2;

  const handleFile = useCallback(f => {
    if (!f) return;
    if (!f.name.match(/\.(pdf|docx|doc)$/i)) return setError("Upload a PDF or DOCX file.");
    if (f.size > 10 * 1024 * 1024) return setError("File must be under 10 MB.");
    setFile(f); setError("");
  }, []);

  const reveal = () => {
    setStage(0);
    requestAnimationFrame(() => {
      setStage(1);
      setTimeout(() => setStage(2), 100);
      setTimeout(() => setStage(3), 800);
    });
  };

  const submit = async () => {
    if (!file) return setError("Upload a resume first.");
    if (jd.trim().length < 20) return setError("Paste a job description (at least 20 characters).");
    setLoading(true); setError(""); setResult(null); setStage(0);
    try {
      const fd = new FormData();
      fd.append("resume", file);
      fd.append("job_description", jd);
      const res = await fetch("http://localhost:5000/api/screen", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Server error");
      setResult(data);
      reveal();
    } catch (e) {
      setError(e.message || "Couldn't reach the screening service. Showing a demo result.");
      setResult(MOCK); reveal();
    } finally { setLoading(false); }
  };

  const vc = result ? (VERDICT[result.verdict] || VERDICT.REVIEW) : null;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "'Inter', system-ui, sans-serif", color: C.text, padding: "clamp(24px,5vw,52px) 16px 64px" }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: "clamp(28px,5vw,48px)" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 7, fontSize: 11.5,
            fontWeight: 600, letterSpacing: "0.07em", color: C.accent,
            textTransform: "uppercase", fontFamily: "ui-monospace, monospace", marginBottom: 16,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%", background: C.accent,
              animation: "pulse-dot 2.4s infinite",
            }}/>
            AI Screening Engine
          </div>
          <h1 style={{ fontSize: "clamp(26px,4vw,40px)", fontWeight: 600, margin: "0 0 10px", letterSpacing: "-0.025em", lineHeight: 1.1 }}>
            Resume Screener
          </h1>
          <p style={{ fontSize: 15, color: C.textDim, maxWidth: 420, margin: 0, lineHeight: 1.55 }}>
            Upload a resume and a job description — get a scored match with skill-gap analysis you can act on.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}
          className="screener-grid">

          {/* LEFT — inputs */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            <Card>
              <Label>01 · Resume</Label>
              <div
                onDragOver={e => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onDrop={e => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
                onClick={() => document.getElementById("fi").click()}
                tabIndex={0}
                onKeyDown={e => (e.key==="Enter"||e.key===" ") && document.getElementById("fi").click()}
                role="button"
                style={{
                  border: `1.5px dashed ${drag ? C.accent : C.borderStrong}`,
                  borderRadius: 10, padding: "26px 16px", textAlign: "center",
                  cursor: "pointer", outline: "none",
                  background: drag ? C.accentLight : C.surfaceAlt,
                  transition: "border-color 0.18s, background 0.18s",
                }}>
                {file ? (
                  <>
                    <div style={{
                      width: 38, height: 38, borderRadius: 10, margin: "0 auto 10px",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: SIG.good.bg, color: SIG.good.c,
                    }}>
                      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="m9 15 2 2 4-4"/>
                      </svg>
                    </div>
                    <div style={{ fontSize: 13.5, fontWeight: 500, color: C.text }}>{file.name}</div>
                    <div style={{ fontSize: 11.5, color: C.textFaint, marginTop: 3 }}>{(file.size/1024).toFixed(0)} KB · click to change</div>
                  </>
                ) : (
                  <>
                    <div style={{
                      width: 38, height: 38, borderRadius: 10, margin: "0 auto 10px",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: "#f0eeea", color: C.textDim,
                    }}>
                      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 3v12m0-12 4 4m-4-4-4 4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>
                      </svg>
                    </div>
                    <div style={{ fontSize: 13.5, color: C.text }}>Drag a resume here, or click to browse</div>
                    <div style={{ fontSize: 11.5, color: C.textFaint, marginTop: 3 }}>PDF or DOCX · up to 10 MB</div>
                  </>
                )}
              </div>
              <input id="fi" type="file" accept=".pdf,.doc,.docx" style={{ display:"none" }} onChange={e => handleFile(e.target.files[0])}/>
            </Card>

            <Card style={{ flex: 1 }}>
              <Label>02 · Job description</Label>
              <textarea
                value={jd} onChange={e => setJd(e.target.value)}
                placeholder="Paste the role's requirements, responsibilities, and qualifications…"
                rows={9}
                style={{
                  width: "100%", background: C.surfaceAlt,
                  border: `1px solid ${C.border}`, borderRadius: 9,
                  padding: "11px 13px", fontSize: 13.5, color: C.text,
                  lineHeight: 1.6, resize: "vertical", fontFamily: "inherit", outline: "none",
                  transition: "border-color 0.18s",
                }}
                onFocus={e => e.target.style.borderColor = C.accent}
                onBlur={e => e.target.style.borderColor = C.border}
              />
              <div style={{ fontSize: 11.5, color: C.textFaint, marginTop: 5, fontFamily: "ui-monospace, monospace" }}>
                {jd.length} chars
              </div>
            </Card>

            {error && (
              <div style={{
                background: SIG.bad.bg, border: `1px solid ${SIG.bad.border}`,
                borderRadius: 9, padding: "10px 14px", fontSize: 13, color: SIG.bad.c,
              }}>
                {error}
              </div>
            )}

            <button onClick={submit} disabled={loading} style={{
              width: "100%", padding: "14px", borderRadius: 11, border: "none",
              background: loading ? "#d4d2cc" : C.accent, color: loading ? C.textDim : "#fff",
              fontSize: 14.5, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 9,
              fontFamily: "inherit", transition: "filter 0.18s, transform 0.12s",
              boxShadow: loading ? "none" : `0 2px 12px rgba(79,70,229,0.28)`,
            }}
            onMouseOver={e => !loading && (e.currentTarget.style.filter = "brightness(1.08)")}
            onMouseOut={e => e.currentTarget.style.filter = "none"}
            onMouseDown={e => !loading && (e.currentTarget.style.transform = "scale(0.987)")}
            onMouseUp={e => e.currentTarget.style.transform = "scale(1)"}>
              {loading ? (
                <>
                  <span style={{
                    width: 15, height: 15, borderRadius: "50%",
                    border: `2px solid rgba(21,20,26,0.2)`, borderTopColor: C.textDim,
                    animation: "spin 0.75s linear infinite", display: "inline-block",
                  }}/>
                  Screening…
                </>
              ) : "Run screening →"}
            </button>
          </div>

          {/* RIGHT — results */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {!result && !loading && (
              <Card style={{ minHeight: 380, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
                <div style={{
                  width: 52, height: 52, borderRadius: 14, marginBottom: 16,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: "#f0eeea", color: C.textDim,
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>
                  </svg>
                </div>
                <div style={{ fontSize: 14.5, fontWeight: 500, color: C.text, marginBottom: 7 }}>Nothing screened yet</div>
                <div style={{ fontSize: 12.5, color: C.textFaint, maxWidth: 240, lineHeight: 1.55 }}>
                  Add a resume and a job description, then run screening to see the match score and gaps.
                </div>
              </Card>
            )}

            {loading && (
              <Card style={{ minHeight: 380, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <ScanLoader/>
              </Card>
            )}

            {result && !loading && (
              <>
                {/* Score card */}
                <Card style={{
                  opacity: stage >= 1 ? 1 : 0,
                  transform: stage >= 1 ? "translateY(0)" : "translateY(10px)",
                  transition: "opacity 0.38s ease, transform 0.38s ease",
                }}>
                  <Label>Overall match</Label>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                    <div>
                      <div style={{
                        display: "inline-flex", alignItems: "center", gap: 6,
                        padding: "5px 13px", borderRadius: 99, fontSize: 12.5, fontWeight: 600,
                        background: vc.bg, color: vc.c, border: `1px solid ${vc.border}`,
                        opacity: stage >= 3 ? 1 : 0,
                        transform: stage >= 3 ? "scale(1)" : "scale(0.88)",
                        transition: "opacity 0.3s, transform 0.35s cubic-bezier(.34,1.56,.64,1)",
                        marginBottom: 10,
                      }}>
                        {vc.label}
                      </div>
                      <div style={{ fontSize: 12.5, color: C.textDim, lineHeight: 1.5, maxWidth: 200 }}>
                        {result.candidate_name ? `Screened for ${result.candidate_name}` : "Resume screened"} against your job description
                      </div>
                    </div>
                    <ScoreRing value={result.overall_score} active={stage >= 1}/>
                  </div>
                </Card>

                {/* Breakdown */}
                <Card style={{
                  opacity: stage >= 2 ? 1 : 0,
                  transform: stage >= 2 ? "translateY(0)" : "translateY(10px)",
                  transition: "opacity 0.38s ease 0.06s, transform 0.38s ease 0.06s",
                }}>
                  <Label>Score breakdown</Label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
                    {[
                      { label: "Skills",     value: result.skills_score,     delay: 0   },
                      { label: "Experience", value: result.experience_score, delay: 100 },
                      { label: "Education",  value: result.education_score,  delay: 200 },
                    ].map(d => (
                      <div key={d.label}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: C.textDim, marginBottom: 6 }}>
                          <span>{d.label}</span>
                          <span style={{ fontWeight: 600, color: sigFor(d.value).c, fontFamily: "ui-monospace, monospace" }}>{Math.round(d.value)}</span>
                        </div>
                        <ScoreBar value={d.value} delay={d.delay} active={active}/>
                      </div>
                    ))}
                  </div>
                </Card>

                {/* Skill gaps */}
                <Card style={{
                  opacity: stage >= 2 ? 1 : 0,
                  transform: stage >= 2 ? "translateY(0)" : "translateY(10px)",
                  transition: "opacity 0.38s ease 0.12s, transform 0.38s ease 0.12s",
                }}>
                  <Label>Skill gaps</Label>
                  {result.matched_skills?.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, color: C.textFaint, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 7 }}>Matched</div>
                      <div style={{ display: "flex", flexWrap: "wrap" }}>
                        {result.matched_skills.map((s, i) => (
                          <Pill key={s} label={s} type="matched" style={{
                            opacity: active ? 1 : 0,
                            transform: active ? "translateY(0)" : "translateY(5px)",
                            transition: `opacity 0.28s ease ${150 + i*40}ms, transform 0.28s ease ${150 + i*40}ms`,
                          }}/>
                        ))}
                      </div>
                    </div>
                  )}
                  {result.missing_skills?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 11, color: C.textFaint, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 7 }}>Missing</div>
                      <div style={{ display: "flex", flexWrap: "wrap" }}>
                        {result.missing_skills.map((s, i) => (
                          <Pill key={s} label={s} type="missing" style={{
                            opacity: active ? 1 : 0,
                            transform: active ? "translateY(0)" : "translateY(5px)",
                            transition: `opacity 0.28s ease ${350 + i*40}ms, transform 0.28s ease ${350 + i*40}ms`,
                          }}/>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>

                {/* Suggestions */}
                {result.suggestions?.length > 0 && (
                  <Card style={{
                    opacity: stage >= 3 ? 1 : 0,
                    transform: stage >= 3 ? "translateY(0)" : "translateY(10px)",
                    transition: "opacity 0.4s ease, transform 0.4s ease",
                  }}>
                    <Label>Suggestions</Label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
                      {result.suggestions.map((s, i) => (
                        <div key={i} style={{
                          display: "flex", gap: 11, alignItems: "flex-start",
                          fontSize: 13.5, color: C.textDim, lineHeight: 1.55,
                          opacity: stage >= 3 ? 1 : 0,
                          transition: `opacity 0.3s ease ${i*80}ms`,
                        }}>
                          <span style={{
                            flexShrink: 0, marginTop: 2,
                            width: 20, height: 20, borderRadius: 6,
                            background: C.accentLight, color: C.accent,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: 11, fontWeight: 700, fontFamily: "ui-monospace, monospace",
                          }}>
                            {i + 1}
                          </span>
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
        @keyframes spin     { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.78)} }
        .screener-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
        @media (max-width: 720px) { .screener-grid { grid-template-columns: 1fr; } }
        @media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration:.001ms!important;transition-duration:.001ms!important; } }
      `}</style>
    </div>
  );
}