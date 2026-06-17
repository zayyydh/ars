from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Verdict(Enum):
    SHORTLIST = "SHORTLIST"
    REVIEW    = "REVIEW"
    REJECT    = "REJECT"


@dataclass
class JobRequirements:
    raw_jd_text:           str       = ""
    job_title:             str       = ""
    company:               str       = ""
    location:              str       = ""
    required_skills:       list[str] = field(default_factory=list)
    preferred_skills:      list[str] = field(default_factory=list)
    all_skills:            list[str] = field(default_factory=list)
    min_exp_years:         float     = 0.0
    max_exp_years:         float     = 99.0
    required_roles:        list[str] = field(default_factory=list)
    required_degree_level: str       = ""
    preferred_fields:      list[str] = field(default_factory=list)
    weight_skills:         float     = 0.50
    weight_experience:     float     = 0.30
    weight_education:      float     = 0.20

    def __post_init__(self):
        total = self.weight_skills + self.weight_experience + self.weight_education
        if total > 0 and abs(total - 1.0) > 0.001:
            self.weight_skills     /= total
            self.weight_experience /= total
            self.weight_education  /= total
        seen = set()
        for s in self.required_skills + self.preferred_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                self.all_skills.append(s)


@dataclass
class SkillMatchDetail:
    skill:       str
    matched:     bool
    matched_as:  str
    similarity:  float
    is_required: bool


@dataclass
class ScreeningResult:
    total_score:          float   = 0.0
    verdict:              Verdict = Verdict.REJECT
    skill_score:          float   = 0.0
    experience_score:     float   = 0.0
    education_score:      float   = 0.0
    matched_skills:       list[str] = field(default_factory=list)
    missing_skills:       list[str] = field(default_factory=list)
    extra_skills:         list[str] = field(default_factory=list)
    skill_details:        list[SkillMatchDetail] = field(default_factory=list)
    candidate_exp_years:  float   = 0.0
    required_exp_years:   float   = 0.0
    exp_gap:              float   = 0.0
    candidate_degree:     str     = ""
    required_degree:      str     = ""
    degree_match:         bool    = False
    candidate_name:       str     = ""
    job_title:            str     = ""
    warnings:             list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        import dataclasses
        d = dataclasses.asdict(self)
        d["verdict"] = self.verdict.value
        return d

    def summary(self) -> str:
        bar = "█" * int(self.total_score / 5) + "░" * (20 - int(self.total_score / 5))
        return (
            f"\n  Candidate : {self.candidate_name or 'Unknown'}\n"
            f"  Score     : [{bar}] {self.total_score:.1f}/100\n"
            f"  Verdict   : {self.verdict.value}"
        )