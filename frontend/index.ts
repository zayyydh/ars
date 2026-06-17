// types/index.ts — TypeScript contracts for all API shapes.
//
// These mirror the Python dataclasses from scorer/models.py exactly.
// If you change a field in Python, change it here too — they are the same contract.

export type Verdict = "SHORTLIST" | "REVIEW" | "REJECT";
export type Status  = "pending" | "processing" | "completed" | "failed";

// One skill's match result — used in the skill breakdown table
export interface SkillMatchDetail {
  skill:        string;
  matched:      boolean;
  matched_as:   string;
  similarity:   number;  // 0–1
  is_required:  boolean;
}

// The full screening result returned by GET /api/results/:id
export interface ScreeningResult {
  id:               string;
  resume_id:        string;
  job_id:           string;
  total_score:      number;
  verdict:          Verdict;
  skill_score:      number;
  experience_score: number;
  education_score:  number;
  matched_skills:   string[];
  missing_skills:   string[];
  extra_skills:     string[];
  skill_details:    SkillMatchDetail[];
  candidate_exp_years:  number;
  required_exp_years:   number;
  exp_gap:              number;
  candidate_degree:     string;
  required_degree:      string;
  degree_match:         boolean;
  candidate_name:       string;
  job_title:            string;
  warnings:             string[];
  status:               Status;
  created_at:           string;
  completed_at:         string | null;
}

// Polling response from GET /api/results/:id
export interface PollResponse {
  id:      string;
  status:  Status;
  result?: ScreeningResult;
  error?:  string;
  message?: string;
}

// POST /api/jobs response
export interface CreateJobResponse {
  job_id:  string;
  message: string;
}

// POST /api/resumes/upload response
export interface UploadResponse {
  result_id: string;
  resume_id: string;
  status:    Status;
  result?:   ScreeningResult;  // present if sync path completed immediately
  task_id?:  string;
  poll_url?: string;
  message?:  string;
}

// App-level view state machine
export type AppView = "upload" | "processing" | "results";

// Processing stage shown during the animated loading screen
export interface ProcessingStage {
  id:      string;
  label:   string;
  detail:  string;
  done:    boolean;
  active:  boolean;
}
