import React, { useState } from "react";

const AiResumeScreener = () => {
  const [file, setFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setFile(selected || null);
    setError("");
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      setError("");
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please upload a resume file.");
      return;
    }
    if (!jobDescription.trim()) {
      setError("Please paste the job description.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("resume", file);
      formData.append("job_description", jobDescription);

      const res = await fetch("http://localhost:5000/api/screen", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Server error while screening resume.");
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex justify-center px-4 py-10">
      <div className="w-full max-w-5xl bg-slate-900/70 border border-slate-800 rounded-2xl shadow-2xl backdrop-blur-sm p-8 md:p-10">
        {/* Header */}
        <header className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
              AI Resume Screener
            </h1>
            <p className="text-slate-400 mt-2 text-sm md:text-base">
              Upload your resume, paste a job description, and let the AI score
              your fit, highlight gaps, and suggest improvements.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-4 py-1 border border-emerald-500/40 text-emerald-300 text-xs md:text-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Live · Powered by AI
          </div>
        </header>

        {/* Main layout */}
        <div className="grid md:grid-cols-2 gap-8">
          {/* Left: Input panel */}
          <section className="space-y-6">
            {/* Resume upload */}
            <div>
              <h2 className="text-sm font-medium text-slate-200 mb-2">
                1. Upload your resume
              </h2>
              <div
                className="border-2 border-dashed border-slate-700 rounded-xl bg-slate-900/60 px-4 py-6 flex flex-col items-center justify-center text-center cursor-pointer hover:border-emerald-400/80 hover:bg-slate-900 transition-colors"
                onDrop={handleDrop}
                onDragOver={handleDragOver}
              >
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  id="resume-upload"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <label htmlFor="resume-upload" className="cursor-pointer">
                  <div className="text-slate-200 font-medium">
                    Drag & drop your resume here
                  </div>
                  <div className="text-slate-500 text-xs mt-1">
                    or click to browse files (.pdf, .doc, .docx)
                  </div>
                </label>
                {file && (
                  <div className="mt-3 text-xs text-emerald-300">
                    Selected: <span className="font-semibold">{file.name}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Job description */}
            <div>
              <h2 className="text-sm font-medium text-slate-200 mb-2">
                2. Paste job description
              </h2>
              <textarea
                className="w-full h-40 resize-none rounded-xl bg-slate-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/70 focus:border-transparent"
                placeholder="Paste the job description or key responsibilities here..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </div>

            {/* Error & button */}
            {error && (
              <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/40 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 disabled:cursor-not-allowed text-slate-950 font-medium py-2.5 text-sm transition-colors"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
                  Analyzing resume...
                </>
              ) : (
                <>
                  <span>Run AI screening</span>
                </>
              )}
            </button>
          </section>

          {/* Right: Results panel */}
          <section className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 md:p-5 flex flex-col">
            <h2 className="text-sm font-medium text-slate-200 mb-3">
              3. Screening results
            </h2>

            {!result && !loading && (
              <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-500 text-sm">
                <div className="mb-3 text-4xl">📄✨</div>
                <p>
                  Results will appear here once you run the AI screening.
                  You&apos;ll see match scores, strengths, and gaps.
                </p>
              </div>
            )}

            {loading && (
              <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 text-sm">
                <div className="mb-4">
                  <div className="w-10 h-10 border-4 border-slate-700 border-t-emerald-400 rounded-full animate-spin" />
                </div>
                <p>Parsing resume, extracting skills, and matching to the job…</p>
              </div>
            )}

            {result && !loading && (
              <div className="space-y-4 text-sm text-slate-100 overflow-y-auto">
                {/* Overall score */}
                <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-wide text-slate-400">
                      Overall match
                    </div>
                    <div className="text-lg font-semibold">
                      {Math.round(result.overall_score ?? 0)}%
                    </div>
                  </div>
                  <div className="w-24 h-24 rounded-full bg-slate-950 flex items-center justify-center border-4 border-emerald-400/80">
                    <span className="text-xl font-semibold text-emerald-300">
                      {Math.round(result.overall_score ?? 0)}
                    </span>
                  </div>
                </div>

                {/* Sub-scores */}
                <div className="grid grid-cols-3 gap-3">
                  <MetricCard
                    label="Skills match"
                    value={result.skills_score}
                  />
                  <MetricCard
                    label="Experience match"
                    value={result.experience_score}
                  />
                  <MetricCard
                    label="Education match"
                    value={result.education_score}
                  />
                </div>

                {/* Strengths & gaps */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <ListCard
                    title="Top strengths"
                    color="emerald"
                    items={result.strengths}
                    emptyText="Strengths will appear here."
                  />
                  <ListCard
                    title="Improvement areas"
                    color="amber"
                    items={result.gaps}
                    emptyText="Gaps will appear here."
                  />
                </div>

                {/* Suggestions */}
                {result.suggestions && result.suggestions.length > 0 && (
                  <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
                    <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">
                      AI suggestions
                    </div>
                    <ul className="list-disc list-inside space-y-1 text-slate-200">
                      {result.suggestions.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

const MetricCard = ({ label, value }) => {
  const v = Math.round(value ?? 0);
  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">
        {label}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-lg font-semibold text-emerald-300">
          {v}
        </span>
        <span className="text-xs text-slate-500">/ 100</span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full bg-emerald-400"
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  );
};

const ListCard = ({ title, color, items, emptyText }) => {
  const colorMap = {
    emerald: "text-emerald-300 bg-emerald-500/10 border-emerald-500/40",
    amber: "text-amber-300 bg-amber-500/10 border-amber-500/40",
  };

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
      <div
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] border ${colorMap[color]}`}
      >
        {title}
      </div>
      <ul className="mt-2 space-y-1 text-xs text-slate-200">
        {items && items.length > 0 ? (
          items.map((item, idx) => <li key={idx}>• {item}</li>)
        ) : (
          <li className="text-slate-500">{emptyText}</li>
        )}
      </ul>
    </div>
  );
};

export default AiResumeScreener;