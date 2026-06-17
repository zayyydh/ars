import { useState, useEffect, useRef, useCallback } from "react";
import type {
  AppView,
  ScreeningResult,
  ProcessingStage,
  Verdict,
} from "./types";
import { createJob, uploadResume, pollUntilDone } from "./api/client";

// ──────────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────────

const VERDICT_CONFIG: Record<Verdict, { label: string; color: string; bg: string; icon: string }> = {
  SHORTLIST: { label: "Shortlist",    color: "#0F6E56", bg: "#E1F5EE", icon: "✓" },
  REVIEW:    { label: "Review",       color: "#854F0B", bg: "#FAEEDA", icon: "~" },
  REJECT:    { label: "Not a fit",    color: "#993C1D", bg: "#FAECE7", icon: "✕" },
};

const STAGES: ProcessingStage[] = [
  { id: "parse",   label: "Parsing resume",         detail: "Extracting text from PDF / DOCX",         done: false, active: false },
  { id: "extract", label: "Extracting entities",    detail: "Finding skills, experience, education",    done: false, active: false },
  { id: "score",   label: "Scoring against JD",     detail: "Comparing profile to requirements",        done: false, active: false },
  { id: "done",    label: "Done",                   detail: "Screening complete",                       done: false, active: false },
];

// ──────────────────────────────────────────────────────────────────
// Utility components
// ──────────────────────────────────────────────────────────────────

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ background: "var(--color-border-tertiary)", borderRadius: 99, height: 8, overflow: "hidden" }}>
      <div style={{
        width:  `${Math.max(0, Math.min(100, value))}%`,
        height: "100%",
        background: color,
        borderRadius: 99,
        transition: "width 0.8s cubic-bezier(0.4,0,0.2,1)",
      }} />
    </div>
  );
}

function Badge({ text, color, bg }: { text: string; color: string; bg: string }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "3px 10px", borderRadius: 99,
      fontSize: 12, fontWeight: 500,
      color, background: bg,
    }}>{text}</span>
  );
}

function SkillPill({ label, matched }: { label: string; matched: boolean }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "4px 10px", borderRadius: 99, fontSize: 12,
      fontWeight: 400,
      background: matched ? "#E1F5EE" : "#FAECE7",
      color:      matched ? "#0F6E56" : "#993C1D",
      border:     `0.5px solid ${matched ? "#9FE1CB" : "#F5C4B3"}`,
      margin: "2px 3px",
    }}>
      <span style={{ fontSize: 10 }}>{matched ? "✓" : "✕"}</span>
      {label}
    </span>
  );
}

// ──────────────────────────────────────────────────────────────────
// Screen 1 — Upload
// ──────────────────────────────────────────────────────────────────

interface UploadScreenProps {
  onSubmit: (jdText: string, file: File) => void;
  error:    string | null;
}

function UploadScreen({ onSubmit, error }: UploadScreenProps) {
  const [jdText,   setJdText]   = useState("");
  const [file,     setFile]     = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith(".pdf") || f.name.endsWith(".docx"))) {
      setFile(f);
    }
  }, []);

  const canSubmit = jdText.trim().length >= 50 && file !== null;

  return (
    <div style={{ maxWidth: 680, margin: "0 auto", padding: "2rem 1rem" }}>

      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: 22, fontWeight: 500, margin: "0 0 6px" }}>
          Resume Screener
        </h1>
        <p style={{ fontSize: 14, color: "var(--color-text-secondary)", margin: 0 }}>
          Paste a job description and upload a resume to get an AI-powered match score.
        </p>
      </div>

      {/* JD text area */}
      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6,
                        color: "var(--color-text-secondary)" }}>
          Job description
        </label>
        <textarea
          value={jdText}
          onChange={e => setJdText(e.target.value)}
          placeholder="Paste the full job description here — requirements, responsibilities, qualifications..."
          rows={10}
          style={{
            width: "100%", boxSizing: "border-box",
            padding: "10px 12px", fontSize: 14, lineHeight: 1.6,
            border: "0.5px solid var(--color-border-secondary)",
            borderRadius: "var(--border-radius-md)",
            background: "var(--color-background-primary)",
            color: "var(--color-text-primary)",
            resize: "vertical", outline: "none",
            fontFamily: "var(--font-sans)",
          }}
        />
        <div style={{ fontSize: 12, color: "var(--color-text-tertiary)", marginTop: 4 }}>
          {jdText.length} characters {jdText.length < 50 && jdText.length > 0 && "— need at least 50"}
        </div>
      </div>

      {/* File drop zone */}
      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6,
                        color: "var(--color-text-secondary)" }}>
          Resume file
        </label>
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          style={{
            border: `0.5px dashed ${dragging ? "var(--color-border-info)" : "var(--color-border-secondary)"}`,
            borderRadius: "var(--border-radius-lg)",
            background: dragging ? "var(--color-background-info)" : "var(--color-background-secondary)",
            padding: "2rem 1rem",
            textAlign: "center",
            cursor: "pointer",
            transition: "all 0.15s",
          }}
        >
          {file ? (
            <div>
              <div style={{ fontSize: 28, marginBottom: 6 }}>📄</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-primary)" }}>
                {file.name}
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 2 }}>
                {(file.size / 1024).toFixed(0)} KB · click to change
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 28, marginBottom: 6 }}>⬆</div>
              <div style={{ fontSize: 14, color: "var(--color-text-primary)" }}>
                Drop a resume here, or click to browse
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text-tertiary)", marginTop: 4 }}>
                PDF or DOCX · max 10 MB
              </div>
            </div>
          )}
          <input
            ref={fileRef} type="file" accept=".pdf,.docx"
            style={{ display: "none" }}
            onChange={e => e.target.files?.[0] && setFile(e.target.files[0])}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: "10px 14px", marginBottom: "1rem",
          background: "var(--color-background-danger)",
          border: "0.5px solid var(--color-border-danger)",
          borderRadius: "var(--border-radius-md)",
          fontSize: 13, color: "var(--color-text-danger)",
        }}>
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        disabled={!canSubmit}
        onClick={() => canSubmit && onSubmit(jdText, file!)}
        style={{
          width: "100%", padding: "12px",
          fontSize: 15, fontWeight: 500,
          background: canSubmit ? "var(--color-text-primary)" : "var(--color-background-secondary)",
          color:      canSubmit ? "var(--color-background-primary)" : "var(--color-text-tertiary)",
          border:     "0.5px solid var(--color-border-secondary)",
          borderRadius: "var(--border-radius-md)",
          cursor: canSubmit ? "pointer" : "not-allowed",
          transition: "all 0.15s",
        }}
      >
        Screen resume
      </button>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Screen 2 — Processing
// ──────────────────────────────────────────────────────────────────

interface ProcessingScreenProps {
  stages:      ProcessingStage[];
  statusText:  string;
}

function ProcessingScreen({ stages, statusText }: ProcessingScreenProps) {
  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: "4rem 1rem", textAlign: "center" }}>
      {/* Spinner */}
      <div style={{
        width: 48, height: 48, borderRadius: "50%",
        border: "2px solid var(--color-border-tertiary)",
        borderTopColor: "var(--color-text-primary)",
        animation: "spin 0.9s linear infinite",
        margin: "0 auto 2rem",
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <h2 style={{ fontSize: 18, fontWeight: 500, margin: "0 0 6px" }}>
        Screening in progress
      </h2>
      <p style={{ fontSize: 14, color: "var(--color-text-secondary)", margin: "0 0 2.5rem" }}>
        {statusText}
      </p>

      {/* Stage list */}
      <div style={{ textAlign: "left" }}>
        {stages.map((stage, i) => (
          <div key={stage.id} style={{
            display: "flex", alignItems: "flex-start", gap: 12,
            padding: "10px 0",
            borderBottom: i < stages.length - 1 ? "0.5px solid var(--color-border-tertiary)" : "none",
          }}>
            {/* Step indicator */}
            <div style={{
              flexShrink: 0, width: 24, height: 24, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 500,
              background: stage.done
                ? "#E1F5EE"
                : stage.active
                  ? "var(--color-background-secondary)"
                  : "transparent",
              border: `0.5px solid ${stage.done ? "#9FE1CB" : "var(--color-border-secondary)"}`,
              color: stage.done ? "#0F6E56" : "var(--color-text-tertiary)",
              transition: "all 0.3s",
            }}>
              {stage.done ? "✓" : i + 1}
            </div>
            <div>
              <div style={{
                fontSize: 14, fontWeight: stage.active ? 500 : 400,
                color: stage.done ? "var(--color-text-secondary)"
                     : stage.active ? "var(--color-text-primary)"
                     : "var(--color-text-tertiary)",
                transition: "color 0.3s",
              }}>
                {stage.label}
              </div>
              {stage.active && (
                <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 2 }}>
                  {stage.detail}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Screen 3 — Results
// ──────────────────────────────────────────────────────────────────

interface ResultsScreenProps {
  result:   ScreeningResult;
  onReset:  () => void;
}

function ResultsScreen({ result, onReset }: ResultsScreenProps) {
  const vc = VERDICT_CONFIG[result.verdict];

  const dimensions = [
    { label: "Skills",     score: result.skill_score,      color: "#1D9E75", detail: `${result.matched_skills.length} matched, ${result.missing_skills.length} missing` },
    { label: "Experience", score: result.experience_score,  color: "#185FA5", detail: `${result.candidate_exp_years.toFixed(1)} yrs vs ${result.required_exp_years.toFixed(1)} yrs required` },
    { label: "Education",  score: result.education_score,   color: "#534AB7", detail: result.degree_match ? `${result.candidate_degree} ✓` : `${result.candidate_degree || "Unknown"} (req: ${result.required_degree || "any"})` },
  ];

  return (
    <div style={{ maxWidth: 680, margin: "0 auto", padding: "2rem 1rem" }}>

      {/* Back button */}
      <button
        onClick={onReset}
        style={{
          background: "transparent", border: "none", padding: 0,
          fontSize: 13, color: "var(--color-text-secondary)",
          cursor: "pointer", marginBottom: "1.5rem", display: "flex",
          alignItems: "center", gap: 4,
        }}
      >
        ← Screen another
      </button>

      {/* Header card */}
      <div style={{
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "1.25rem 1.5rem",
        marginBottom: "1rem",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 500, margin: "0 0 4px" }}>
              {result.candidate_name || "Candidate"}
            </h2>
            <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
              {result.job_title || "Role"}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <Badge text={`${vc.icon}  ${vc.label}`} color={vc.color} bg={vc.bg} />
            <div style={{ fontSize: 22, fontWeight: 500, lineHeight: 1 }}>
              {result.total_score.toFixed(0)}
              <span style={{ fontSize: 13, fontWeight: 400, color: "var(--color-text-secondary)" }}> / 100</span>
            </div>
          </div>
        </div>

        {/* Main score bar */}
        <ScoreBar
          value={result.total_score}
          color={result.total_score >= 70 ? "#1D9E75" : result.total_score >= 45 ? "#BA7517" : "#D85A30"}
        />
      </div>

      {/* Dimension breakdown */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem",
        marginBottom: "1rem",
      }}>
        {dimensions.map(d => (
          <div key={d.label} style={{
            background: "var(--color-background-secondary)",
            borderRadius: "var(--border-radius-md)",
            padding: "0.9rem 1rem",
          }}>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
              {d.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 500, marginBottom: 6, lineHeight: 1 }}>
              {d.score.toFixed(0)}
              <span style={{ fontSize: 12, fontWeight: 400, color: "var(--color-text-tertiary)" }}>/100</span>
            </div>
            <ScoreBar value={d.score} color={d.color} />
            <div style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginTop: 5 }}>
              {d.detail}
            </div>
          </div>
        ))}
      </div>

      {/* Skill breakdown */}
      <div style={{
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "1.25rem 1.5rem",
        marginBottom: "1rem",
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 500, margin: "0 0 1rem" }}>
          Skill gap analysis
        </h3>

        {/* Required skills grid */}
        {result.skill_details.filter(s => s.is_required).length > 0 && (
          <div style={{ marginBottom: "1rem" }}>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
              Required skills
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 0 }}>
              {result.skill_details
                .filter(s => s.is_required)
                .map(s => (
                  <SkillPill key={s.skill} label={s.skill} matched={s.matched} />
                ))}
            </div>
          </div>
        )}

        {/* Preferred skills */}
        {result.skill_details.filter(s => !s.is_required).length > 0 && (
          <div style={{ marginBottom: "1rem" }}>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
              Preferred skills
            </div>
            <div style={{ display: "flex", flexWrap: "wrap" }}>
              {result.skill_details
                .filter(s => !s.is_required)
                .map(s => (
                  <SkillPill key={s.skill} label={s.skill} matched={s.matched} />
                ))}
            </div>
          </div>
        )}

        {/* Extra skills candidate brings */}
        {result.extra_skills.length > 0 && (
          <div>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
              Additional skills candidate brings
            </div>
            <div style={{ display: "flex", flexWrap: "wrap" }}>
              {result.extra_skills.slice(0, 12).map(s => (
                <span key={s} style={{
                  display: "inline-block", padding: "4px 10px",
                  margin: "2px 3px", borderRadius: 99, fontSize: 12,
                  background: "var(--color-background-secondary)",
                  color: "var(--color-text-secondary)",
                  border: "0.5px solid var(--color-border-tertiary)",
                }}>{s}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Experience & Education summary */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem",
        marginBottom: "1rem",
      }}>
        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "1rem 1.25rem",
        }}>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 8 }}>
            Experience
          </div>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4 }}>
            {result.candidate_exp_years.toFixed(1)} years
          </div>
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
            Required: {result.required_exp_years.toFixed(0)}+ years
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            <span style={{
              color: result.exp_gap >= 0 ? "#0F6E56" : "#993C1D",
              fontWeight: 500,
            }}>
              {result.exp_gap >= 0 ? `+${result.exp_gap.toFixed(1)} years above req.` : `${result.exp_gap.toFixed(1)} years below req.`}
            </span>
          </div>
        </div>

        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "1rem 1.25rem",
        }}>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 8 }}>
            Education
          </div>
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4 }}>
            {result.candidate_degree
              ? result.candidate_degree.charAt(0).toUpperCase() + result.candidate_degree.slice(1)
              : "Unknown"}
          </div>
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
            Required: {result.required_degree || "Not specified"}
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            <Badge
              text={result.degree_match ? "✓ Meets requirement" : "Does not meet"}
              color={result.degree_match ? "#0F6E56" : "#993C1D"}
              bg={result.degree_match ? "#E1F5EE" : "#FAECE7"}
            />
          </div>
        </div>
      </div>

      {/* Warnings */}
      {result.warnings?.length > 0 && (
        <div style={{
          background: "var(--color-background-warning)",
          border: "0.5px solid var(--color-border-warning)",
          borderRadius: "var(--border-radius-md)",
          padding: "10px 14px",
          fontSize: 13, color: "var(--color-text-warning)",
        }}>
          <strong>Notes:</strong>
          <ul style={{ margin: "4px 0 0", paddingLeft: "1.2rem" }}>
            {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Root App — state machine
// ──────────────────────────────────────────────────────────────────

export default function App() {
  const [view,       setView]       = useState<AppView>("upload");
  const [stages,     setStages]     = useState<ProcessingStage[]>(STAGES);
  const [statusText, setStatusText] = useState("Sending resume to pipeline...");
  const [result,     setResult]     = useState<ScreeningResult | null>(null);
  const [error,      setError]      = useState<string | null>(null);

  // Advance the stage list visually
  const advanceStage = useCallback((statusLabel: string) => {
    const stageMap: Record<string, number> = {
      pending:    0,
      parsing:    0,
      processing: 1,
      scoring:    2,
      completed:  3,
    };
    const idx = stageMap[statusLabel] ?? 0;
    setStages(prev => prev.map((s, i) => ({
      ...s,
      done:   i < idx,
      active: i === idx,
    })));
    const labels: Record<string, string> = {
      pending:    "Sending to pipeline...",
      parsing:    "Parsing resume text...",
      processing: "Extracting entities with AI...",
      scoring:    "Scoring against job description...",
      completed:  "Finalising results...",
    };
    setStatusText(labels[statusLabel] ?? "Processing...");
  }, []);

  // Main submit handler
  const handleSubmit = useCallback(async (jdText: string, file: File) => {
    setError(null);
    setView("processing");
    setStages(STAGES.map((s, i) => ({ ...s, active: i === 0, done: false })));

    try {
      // 1. Create job
      const { job_id } = await createJob(jdText);

      // 2. Upload resume
      const upload = await uploadResume(file, job_id);

      // 3. If sync path returned result immediately
      if (upload.status === "completed" && upload.result) {
        setResult(upload.result);
        setView("results");
        return;
      }

      // 4. Poll for async result
      const final = await pollUntilDone(
        upload.result_id,
        (status) => advanceStage(status),
      );

      if (final.status === "completed" && final.result) {
        setResult(final.result);
        setView("results");
      } else {
        throw new Error(final.error ?? "Screening failed");
      }
    } catch (e: any) {
      setError(e.message ?? "Something went wrong");
      setView("upload");
    }
  }, [advanceStage]);

  const handleReset = useCallback(() => {
    setView("upload");
    setResult(null);
    setError(null);
    setStages(STAGES);
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--color-background-tertiary)",
      fontFamily: "var(--font-sans)",
    }}>
      {view === "upload" && (
        <UploadScreen onSubmit={handleSubmit} error={error} />
      )}
      {view === "processing" && (
        <ProcessingScreen stages={stages} statusText={statusText} />
      )}
      {view === "results" && result && (
        <ResultsScreen result={result} onReset={handleReset} />
      )}
    </div>
  );
}
