import React, { useState, useCallback, useEffect, useRef } from "react";

// ── Design tokens ────────────────────────────────────────────────────────────
// Light: paper-white instrument panel. Dark: graphite instrument panel.
// Semantic score colors stay constant across themes (green/amber/red = signal,
// not brand) so a "Strong Match" reads as strong match in either theme.

const THEME = {
  light: {
    bg: "#f7f6f3",
    bgGrid: "rgba(15,15,20,0.035)",
    surface: "#ffffff",
    surfaceSunken: "#f1efe9",
    border: "rgba(15,15,20,0.10)",
    borderStrong: "rgba(15,15,20,0.16)",
    text: "#15141a",
    textDim: "rgba(21,20,26,0.52)",
    textFaint: "rgba(21,20,26,0.32)",
    accent: "#5b4ee8",
    accentText: "#ffffff",
    shadow: "0 1px 2px rgba(15,15,20,0.04), 0 8px 24px rgba(15,15,20,0.06)",
  },
  dark: {
    bg: "#0d0d11",
    bgGrid: "rgba(255,255,255,0.035)",
    surface: "#15151b",
    surfaceSunken: "#1a1a22",
    border: "rgba(255,255,255,0.09)",
    borderStrong: "rgba(255,255,255,0.16)",
    text: "#f3f2f7",
    textDim: "rgba(243,242,247,0.55)",
    textFaint: "rgba(243,242,247,0.32)",
    accent: "#8b7eff",
    accentText: "#0d0d11",
    shadow: "0 1px 2px rgba(0,0,0,0.3), 0 12px 32px rgba(0,0,0,0.45)",
  },
};

const SIGNAL = {
  good: { c: "#1a9c6b", bg: "rgba(26,156,107,0.12)", border: "rgba(26,156,107,0.32)" },
  mid:  { c: "#c2820b", bg: "rgba(194,130,11,0.12)",  border: "rgba(194,130,11,0.32)" },
  bad:  { c: "#d6453d", bg: "rgba(214,69,61,0.12)",   border: "rgba(214,69,61,0.32)" },
};

const verdictConfig = {
  SHORTLIST: { label: "Strong match", ...SIGNAL.good },
  REVIEW:    { label: "Partial match", ...SIGNAL.mid },
  REJECT:    { label: "Low match",    ...SIGNAL.bad },
};

const signalFor = (v) => (v >= 70 ? SIGNAL.good : v >= 45 ? SIGNAL.mid : SIGNAL.bad);

// ── Mock data (for demo/preview without a backend) ─────────────────────────

const MOCK_RESULT = {
  overall_score: 78,
  verdict: "SHORTLIST",
  skills_score: 84,
  experience_score: 76,
  education_score: 70,
  matched_skills: ["React", "TypeScript", "Node.js", "REST APIs", "Jest", "CI/CD"],
  missing_skills: ["GraphQL", "Kubernetes"],
  suggestions: [
    "Quantify the impact of the platform migration mentioned in the third role — numbers make senior-level scope easier to verify.",
    "Surface the GraphQL exposure from side projects, if any exists — it's the largest gap against this role.",
    "Lead with the most recent title; the resume currently buries it under a long summary paragraph.",
  ],
};

// ── Tiny hook: count-up for numeric values ──────────────────────────────────

function useCountUp(target, { duration = 900, start = false, delay = 0 } = {}) {
  const [value, setValue] = useState(0);
  const raf = useRef(null);

  useEffect(() => {
    if (!start) { setValue(0); return; }
    let startTime = null;
    let timeoutId = null;

    const tick = (now) => {
      if (startTime === null) startTime = now;
      const t = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out-cubic
      setValue(target * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };

    timeoutId = setTimeout(() => {
      raf.current = requestAnimationFrame(tick);
    }, delay);

    return () => {
      clearTimeout(timeoutId);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [target, start, duration, delay]);

  return value;
}

// ── Sub-components ───────────────────────────────────────────────────────────

function ScoreRing({ value, t, active }) {
  const animated = useCountUp(value, { duration: 1100, start: active, delay: 650 });
  const r = 42, cx = 50, cy = 50;
  const circ = 2 * Math.PI * r;
  const offset = circ - (animated / 100) * circ;
  const sig = signalFor(value);

  return (
    <svg width={100} height={100} viewBox="0 0 100 100" style={{ transform: "rotate(-90deg)", flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={t.border} strokeWidth={7} />
      <circle
        cx={cx} cy={cy} r={r} fill="none"
        stroke={sig.c} strokeWidth={7}
        strokeDasharray={circ} strokeDashoffset={active ? offset : circ}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1.1s cubic-bezier(.16,1,.3,1)", transitionDelay: "0.65s" }}
      />
      <text
        x={cx} y={cy + 1.5}
        textAnchor="middle" dominantBaseline="middle"
        fill={sig.c} fontSize={22} fontWeight={600}
        fontFamily="'JetBrains Mono', ui-monospace, monospace"
        style={{ transform: "rotate(90deg)", transformOrigin: `${cx}px ${cy}px` }}
      >
        {Math.round(animated)}
      </text>
    </svg>
  );
}

function ScoreBar({ value, color, t, active, delay }) {
  return (
    <div style={{ background: t.surfaceSunken, borderRadius: 99, height: 5, overflow: "hidden" }}>
      <div style={{
        width: active ? `${Math.min(100, Math.max(0, value))}%` : "0%",
        height: "100%",
        background: color,
        borderRadius: 99,
        transition: `width 0.8s cubic-bezier(.16,1,.3,1)`,
        transitionDelay: `${delay}ms`,
      }} />
    </div>
  );
}

function Pill({ label, type, t, style }) {
  const styles = {
    matched: { bg: SIGNAL.good.bg, color: SIGNAL.good.c, border: SIGNAL.good.border },
    missing: { bg: SIGNAL.bad.bg,  color: SIGNAL.bad.c,  border: SIGNAL.bad.border },
  };
  const s = styles[type] || { bg: t.surfaceSunken, color: t.textDim, border: t.border };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "4px 11px", borderRadius: 99, fontSize: 12.5, fontWeight: 500,
      background: s.bg, color: s.color,
      border: `1px solid ${s.border}`,
      margin: "3px 4px 0 0",
      ...style,
    }}>
      {type === "matched" && <span style={{ fontSize: 10 }}>✓</span>}
      {type === "missing" && <span style={{ fontSize: 10 }}>✕</span>}
      {label}
    </span>
  );
}

function Card({ children, t, style = {} }) {
  return (
    <div style={{
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 14,
      padding: "22px 22px",
      boxShadow: t.shadow,
      ...style,
    }}>
      {children}
    </div>
  );
}

function SectionLabel({ children, t, mono }) {
  return (
    <div style={{
      fontSize: 11.5, fontWeight: 600, letterSpacing: "0.07em",
      color: t.textFaint, textTransform: "uppercase",
      marginBottom: 14,
      fontFamily: mono ? "'JetBrains Mono', ui-monospace, monospace" : "inherit",
    }}>
      {children}
    </div>
  );
}

function ThemeToggle({ theme, setTheme, t }) {
  return (
    <button
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
      aria-label="Toggle color theme"
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 38, height: 38, borderRadius: 10,
        border: `1px solid ${t.border}`, background: t.surface,
        color: t.textDim, cursor: "pointer", flexShrink: 0,
        transition: "border-color 0.2s, color 0.2s, transform 0.15s",
      }}
      onMouseDown={(e) => { e.currentTarget.style.transform = "scale(0.92)"; }}
      onMouseUp={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
    >
      {theme === "light" ? (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      ) : (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="4.5" />
          <path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8l1.8-1.8M18 6l1.8-1.8" />
        </svg>
      )}
    </button>
  );
}

// Scanning-beam loader: a horizontal sweep over a faux document, like a
// flatbed scanner reading the resume. Distinctive to "screening" rather
// than a generic spinner.
function ScanLoader({ t }) {
  return (
    <div style={{ width: "100%", maxWidth: 220 }}>
      <svg width="100%" viewBox="0 0 220 150" style={{ overflow: "visible" }}>
        <defs>
          <clipPath id="doc-clip"><rect x="30" y="6" width="160" height="138" rx="6" /></clipPath>
          <linearGradient id="beam-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={t.accent} stopOpacity="0" />
            <stop offset="50%" stopColor={t.accent} stopOpacity="0.5" />
            <stop offset="100%" stopColor={t.accent} stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x="30" y="6" width="160" height="138" rx="6" fill={t.surfaceSunken} stroke={t.border} />
        {[20, 34, 48, 62, 76, 90, 104, 118, 132].map((y, i) => (
          <rect key={y} x="46" y={y} width={i % 3 === 0 ? 90 : 128 - (i * 4) % 40} height="6" rx="3"
            fill={t.border} />
        ))}
        <g clipPath="url(#doc-clip)">
          <rect x="30" y="-20" width="160" height="40" fill="url(#beam-grad)">
            <animate attributeName="y" values="-30;150;-30" dur="2.1s" repeatCount="indefinite" />
          </rect>
        </g>
      </svg>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AiResumeScreener() {
  const [theme, setTheme] = useState("light");
  const [file,        setFile]        = useState(null);
  const [jd,          setJd]          = useState("");
  const [loading,     setLoading]     = useState(false);
  const [result,      setResult]      = useState(null);
  const [error,       setError]       = useState("");
  const [dragging,    setDragging]    = useState(false);
  const [revealStage, setRevealStage] = useState(0); // 0=idle 1=score-card-in 2=bars+pills 3=settled

  useEffect(() => {
    const m = window.matchMedia("(prefers-color-scheme: dark)");
    setTheme(m.matches ? "dark" : "light");
  }, []);

  const t = THEME[theme];

  const handleFile = useCallback((f) => {
    if (f && (f.name.endsWith(".pdf") || f.name.endsWith(".docx") || f.name.endsWith(".doc"))) {
      if (f.size > 10 * 1024 * 1024) {
        setError("File is larger than 10 MB. Please upload a smaller file.");
        return;
      }
      setFile(f);
      setError("");
    } else if (f) {
      setError("Please upload a PDF or DOCX file.");
    }
  }, []);

  const runReveal = () => {
    setRevealStage(0);
    requestAnimationFrame(() => {
      setRevealStage(1);
      setTimeout(() => setRevealStage(2), 120);
      setTimeout(() => setRevealStage(3), 900);
    });
  };

  const handleSubmit = async () => {
    if (!file)        return setError("Please upload a resume file.");
    if (jd.trim().length < 20) return setError("Please paste a job description (at least 20 characters).");

    setLoading(true);
    setError("");
    setResult(null);
    setRevealStage(0);

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
      runReveal();
    } catch (err) {
      setError(err.message || "Couldn't reach the screening service. Showing a sample result instead.");
      // Fallback so the UI/animation is inspectable without a backend.
      setResult(MOCK_RESULT);
      runReveal();
    } finally {
      setLoading(false);
    }
  };

  const vc = result ? (verdictConfig[result.verdict] || verdictConfig.REVIEW) : null;
  const active = revealStage >= 2;

  return (
    <div style={{
      minHeight: "100vh",
      background: t.bg,
      backgroundImage: `radial-gradient(${t.bgGrid} 1px, transparent 1px)`,
      backgroundSize: "20px 20px",
      fontFamily: "'Inter', -apple-system, 'Segoe UI', sans-serif",
      color: t.text,
      transition: "background-color 0.3s, color 0.3s",
      padding: "clamp(20px, 5vw, 48px) 16px 60px",
    }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>

        {/* ── Header ── */}
        <div style={{
          display: "flex", alignItems: "flex-start", justifyContent: "space-between",
          gap: 16, marginBottom: "clamp(28px, 5vw, 44px)",
        }}>
          <div style={{ textAlign: "left" }}>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              fontSize: 12, fontWeight: 600, letterSpacing: "0.06em",
              color: t.accent, marginBottom: 14,
              fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              textTransform: "uppercase",
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: t.accent,
                animation: "pulse-dot 2.4s infinite",
              }} />
              Screening engine
            </div>
            <h1 style={{
              fontSize: "clamp(28px, 4.2vw, 40px)", fontWeight: 600, margin: "0 0 10px",
              letterSpacing: "-0.02em", lineHeight: 1.1, color: t.text,
            }}>
              Resume screener
            </h1>
            <p style={{ fontSize: 15, color: t.textDim, maxWidth: 440, margin: 0, lineHeight: 1.5 }}>
              Upload a resume and a job description. Get a scored match with skill-gap detail you can act on.
            </p>
          </div>
          <ThemeToggle theme={theme} setTheme={setTheme} t={t} />
        </div>

        {/* ── Two-column layout (collapses to single column under 760px via CSS class) ── */}
        <div className="screener-grid">

          {/* ── LEFT: Input ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            <Card t={t}>
              <SectionLabel t={t} mono>01 · Resume</SectionLabel>
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
                onClick={() => document.getElementById("file-input").click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") document.getElementById("file-input").click(); }}
                style={{
                  border: `1.5px dashed ${dragging ? t.accent : t.borderStrong}`,
                  borderRadius: 12,
                  padding: "26px 16px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: dragging ? t.surfaceSunken : "transparent",
                  transition: "border-color 0.2s, background 0.2s",
                  outline: "none",
                }}
              >
                {file ? (
                  <>
                    <div style={{
                      width: 36, height: 36, borderRadius: 9, margin: "0 auto 10px",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: SIGNAL.good.bg, color: SIGNAL.good.c,
                    }}>
                      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" />
                      </svg>
                    </div>
                    <div style={{ fontSize: 13.5, fontWeight: 500, color: t.text }}>{file.name}</div>
                    <div style={{ fontSize: 11.5, color: t.textFaint, marginTop: 3 }}>
                      {(file.size / 1024).toFixed(0)} KB · click to change
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{
                      width: 36, height: 36, borderRadius: 9, margin: "0 auto 10px",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: t.surfaceSunken, color: t.textDim,
                    }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 3v12m0-12 4 4m-4-4-4 4" /><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
                      </svg>
                    </div>
                    <div style={{ fontSize: 13.5, color: t.text }}>
                      Drag a resume here, or click to browse
                    </div>
                    <div style={{ fontSize: 11.5, color: t.textFaint, marginTop: 3 }}>
                      PDF or DOCX · up to 10 MB
                    </div>
                  </>
                )}
              </div>
              <input id="file-input" type="file" accept=".pdf,.doc,.docx"
                style={{ display: "none" }}
                onChange={e => handleFile(e.target.files[0])} />
            </Card>

            <Card t={t} style={{ flex: 1 }}>
              <SectionLabel t={t} mono>02 · Job description</SectionLabel>
              <textarea
                value={jd}
                onChange={e => setJd(e.target.value)}
                placeholder="Paste the role's requirements, responsibilities, and qualifications…"
                rows={9}
                style={{
                  width: "100%", boxSizing: "border-box",
                  background: t.surfaceSunken,
                  border: `1px solid ${t.border}`,
                  borderRadius: 10, padding: "11px 13px",
                  fontSize: 13.5, color: t.text,
                  lineHeight: 1.6, resize: "vertical",
                  fontFamily: "inherit", outline: "none",
                  transition: "border-color 0.2s",
                }}
                className="jd-textarea"
              />
              <div style={{ fontSize: 11.5, color: t.textFaint, marginTop: 6, fontFamily: "'JetBrains Mono', monospace" }}>
                {jd.length} characters
              </div>
            </Card>

            {error && (
              <div style={{
                background: SIGNAL.bad.bg,
                border: `1px solid ${SIGNAL.bad.border}`,
                borderRadius: 10, padding: "11px 14px",
                fontSize: 13, color: theme === "light" ? "#9c2e28" : SIGNAL.bad.c,
              }}>
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="run-button"
              style={{
                width: "100%", padding: "14px",
                borderRadius: 12, border: "none",
                background: loading ? t.borderStrong : t.accent,
                color: loading ? t.textDim : t.accentText,
                fontSize: 14.5, fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center",
                justifyContent: "center", gap: 9,
                transition: "filter 0.2s, transform 0.15s",
                fontFamily: "inherit",
              }}
            >
              {loading ? (
                <>
                  <span style={{
                    width: 15, height: 15,
                    border: `2px solid ${t.textFaint}`,
                    borderTopColor: t.text,
                    borderRadius: "50%",
                    animation: "spin 0.8s linear infinite",
                    display: "inline-block",
                  }} />
                  Screening…
                </>
              ) : "Run screening"}
            </button>
          </div>

          {/* ── RIGHT: Results ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {!result && !loading && (
              <Card t={t} style={{ flex: 1, display: "flex", flexDirection: "column",
                            alignItems: "center", justifyContent: "center",
                            minHeight: 380, textAlign: "center" }}>
                <div style={{
                  width: 52, height: 52, borderRadius: 13, marginBottom: 16,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: t.surfaceSunken, color: t.textDim,
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
                  </svg>
                </div>
                <div style={{ fontSize: 14.5, fontWeight: 500, color: t.text, marginBottom: 6 }}>
                  Nothing screened yet
                </div>
                <div style={{ fontSize: 12.5, color: t.textFaint, maxWidth: 260, lineHeight: 1.5 }}>
                  Add a resume and a job description, then run screening to see the match score and gaps.
                </div>
              </Card>
            )}

            {loading && (
              <Card t={t} style={{ flex: 1, display: "flex", flexDirection: "column",
                            alignItems: "center", justifyContent: "center", minHeight: 380, gap: 18 }}>
                <ScanLoader t={t} />
                <div style={{ fontSize: 13.5, color: t.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
                  Reading resume, matching skills…
                </div>
              </Card>
            )}

            {result && !loading && (
              <>
                <Card t={t} style={{
                  opacity: revealStage >= 1 ? 1 : 0,
                  transform: revealStage >= 1 ? "translateY(0)" : "translateY(8px)",
                  transition: "opacity 0.4s ease-out, transform 0.4s ease-out",
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                    <div>
                      <SectionLabel t={t} mono>Overall match</SectionLabel>
                      <div style={{
                        fontSize: 13, fontWeight: 500,
                        color: t.textDim, marginBottom: 4,
                      }} />
                      <div style={{
                        display: "inline-flex", alignItems: "center", gap: 6,
                        padding: "5px 13px", borderRadius: 99,
                        fontSize: 12.5, fontWeight: 600,
                        background: vc.bg, color: vc.c,
                        border: `1px solid ${vc.border}`,
                        transform: revealStage >= 3 ? "scale(1)" : "scale(0.85)",
                        opacity: revealStage >= 3 ? 1 : 0,
                        transition: "transform 0.35s cubic-bezier(.34,1.56,.64,1), opacity 0.3s",
                      }}>
                        {vc.label}
                      </div>
                    </div>
                    <ScoreRing value={result.overall_score} t={t} active={revealStage >= 1} />
                  </div>
                </Card>

                <Card t={t} style={{
                  opacity: revealStage >= 2 ? 1 : 0,
                  transform: revealStage >= 2 ? "translateY(0)" : "translateY(8px)",
                  transition: "opacity 0.4s ease-out 0.05s, transform 0.4s ease-out 0.05s",
                }}>
                  <SectionLabel t={t} mono>Score breakdown</SectionLabel>
                  <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    {[
                      { label: "Skills",     value: result.skills_score,     d: 0 },
                      { label: "Experience", value: result.experience_score, d: 90 },
                      { label: "Education",  value: result.education_score,  d: 180 },
                    ].map(row => (
                      <div key={row.label}>
                        <div style={{ display: "flex", justifyContent: "space-between",
                                      fontSize: 13, color: t.textDim, marginBottom: 6 }}>
                          <span>{row.label}</span>
                          <span style={{ fontWeight: 600, color: signalFor(row.value).c, fontFamily: "'JetBrains Mono', monospace" }}>
                            {Math.round(row.value)}
                          </span>
                        </div>
                        <ScoreBar value={row.value} color={signalFor(row.value).c} t={t} active={active} delay={row.d} />
                      </div>
                    ))}
                  </div>
                </Card>

                <Card t={t} style={{
                  opacity: revealStage >= 2 ? 1 : 0,
                  transform: revealStage >= 2 ? "translateY(0)" : "translateY(8px)",
                  transition: "opacity 0.4s ease-out 0.1s, transform 0.4s ease-out 0.1s",
                }}>
                  <SectionLabel t={t} mono>Skill gaps</SectionLabel>
                  {result.matched_skills?.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11.5, color: t.textFaint, marginBottom: 6 }}>Matched</div>
                      <div style={{ display: "flex", flexWrap: "wrap" }}>
                        {result.matched_skills.map((s, i) => (
                          <Pill key={s} label={s} type="matched" t={t} style={{
                            opacity: active ? 1 : 0,
                            transform: active ? "translateY(0)" : "translateY(4px)",
                            transition: `opacity 0.3s ease-out ${200 + i * 45}ms, transform 0.3s ease-out ${200 + i * 45}ms`,
                          }} />
                        ))}
                      </div>
                    </div>
                  )}
                  {result.missing_skills?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 11.5, color: t.textFaint, marginBottom: 6 }}>Missing</div>
                      <div style={{ display: "flex", flexWrap: "wrap" }}>
                        {result.missing_skills.map((s, i) => (
                          <Pill key={s} label={s} type="missing" t={t} style={{
                            opacity: active ? 1 : 0,
                            transform: active ? "translateY(0)" : "translateY(4px)",
                            transition: `opacity 0.3s ease-out ${400 + i * 45}ms, transform 0.3s ease-out ${400 + i * 45}ms`,
                          }} />
                        ))}
                      </div>
                    </div>
                  )}
                </Card>

                {result.suggestions?.length > 0 && (
                  <Card t={t} style={{
                    opacity: revealStage >= 3 ? 1 : 0,
                    transform: revealStage >= 3 ? "translateY(0)" : "translateY(8px)",
                    transition: "opacity 0.4s ease-out, transform 0.4s ease-out",
                  }}>
                    <SectionLabel t={t} mono>Suggestions</SectionLabel>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {result.suggestions.map((s, i) => (
                        <div key={i} style={{
                          display: "flex", gap: 10, alignItems: "flex-start",
                          fontSize: 13.5, color: t.textDim, lineHeight: 1.55,
                        }}>
                          <span style={{ color: t.accent, flexShrink: 0, marginTop: 1, fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                            {String(i + 1).padStart(2, "0")}
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
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
        * { box-sizing: border-box; }

        .screener-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 24px;
          align-items: start;
        }
        @media (max-width: 760px) {
          .screener-grid { grid-template-columns: 1fr; }
        }

        textarea.jd-textarea::placeholder { color: ${t.textFaint}; }
        textarea.jd-textarea:focus { border-color: ${t.accent} !important; }

        .run-button:hover:not(:disabled) { filter: brightness(1.08); }
        .run-button:active:not(:disabled) { transform: scale(0.985); }

        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.001ms !important;
            transition-duration: 0.001ms !important;
          }
        }
      `}</style>
    </div>
  );
}