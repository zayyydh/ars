"""
extractors/models.py — Output contract for Layer 3.

CandidateProfile is what Layer 3 produces and Layer 4 consumes.
Every field has a clear type. Optional fields default to safe values
so Layer 4 never crashes on a KeyError or AttributeError.

Design note — two model systems here:
    1. Python dataclasses  → used internally, easy to construct and mutate
    2. Pydantic BaseModel  → used for LLM output validation (LangChain requires it)
       We convert Pydantic → dataclass at the end of the LLM extractor.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────
# Sub-models: Experience and Education entries
# ──────────────────────────────────────────────────────────────────

@dataclass
class ExperienceEntry:
    """
    A single job / work experience entry.

    duration_months is the most important field for Layer 4 scoring —
    it's what we compare against "5+ years experience" in the JD.
    We compute it from start_date and end_date when possible.
    """
    company:         str            = ""
    title:           str            = ""    # "Software Engineer", "Data Scientist"
    start_date:      str            = ""    # Free text: "Jan 2021", "2021", "Q1 2019"
    end_date:        str            = ""    # "Present", "Dec 2023", "2023"
    duration_months: int            = 0     # Computed from dates when parseable
    description:     str            = ""    # Bullet points / responsibilities
    skills_used:     list[str]      = field(default_factory=list)  # Skills mentioned in this role


@dataclass
class EducationEntry:
    """
    A single education entry.

    degree_level is normalised to a comparable string:
    "phd" > "masters" > "bachelors" > "diploma" > "high_school"
    Layer 4 uses this for the education match dimension.
    """
    institution: str  = ""
    degree:      str  = ""    # Full text: "B.Tech Computer Science"
    degree_level: str = ""    # Normalised: "bachelors", "masters", "phd"
    field_of_study: str = ""  # "Computer Science", "Data Science"
    graduation_year: str = "" # "2021", "Expected 2025"
    cgpa:        str  = ""    # "8.5/10", "3.8/4.0" — kept as string, varies widely


# ──────────────────────────────────────────────────────────────────
# Main output dataclass
# ──────────────────────────────────────────────────────────────────

@dataclass
class CandidateProfile:
    """
    Fully structured candidate profile extracted from a resume.
    This is what Layer 4 receives and scores against the job description.

    Confidence fields explain how reliable each section is:
        1.0 = extracted cleanly from explicit text
        0.7 = inferred / partially matched
        0.4 = guessed or defaulted
    """

    # ── Contact info (regex-extracted, high confidence) ──────────────────
    name:        str = ""
    email:       str = ""
    phone:       str = ""
    linkedin:    str = ""
    github:      str = ""
    location:    str = ""

    # ── Skills (LLM + transformer-extracted) ─────────────────────────────
    skills:           list[str]  = field(default_factory=list)
    # Categorised skills for richer scoring
    technical_skills: list[str]  = field(default_factory=list)
    soft_skills:      list[str]  = field(default_factory=list)
    tools:            list[str]  = field(default_factory=list)   # Docker, Git, Jira
    languages:        list[str]  = field(default_factory=list)   # Python, Java, Go

    # ── Experience ────────────────────────────────────────────────────────
    experience:         list[ExperienceEntry] = field(default_factory=list)
    total_exp_years:    float = 0.0   # Computed: sum of all duration_months / 12
    current_title:      str   = ""    # Most recent job title
    current_company:    str   = ""    # Most recent company

    # ── Education ────────────────────────────────────────────────────────
    education:          list[EducationEntry] = field(default_factory=list)
    highest_degree:     str = ""   # "bachelors", "masters", "phd"
    primary_field:      str = ""   # "Computer Science", "Electrical Engineering"

    # ── Summary ───────────────────────────────────────────────────────────
    summary:            str = ""   # Candidate's own summary/objective if present

    # ── Extraction metadata ───────────────────────────────────────────────
    extraction_confidence: float = 0.0   # 0–1 overall confidence
    extraction_warnings:   list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON storage in PostgreSQL."""
        import dataclasses
        return dataclasses.asdict(self)

    def summary_line(self) -> str:
        """One-line summary for logging."""
        skills_count = len(self.skills)
        exp_count    = len(self.experience)
        edu_count    = len(self.education)
        return (
            f"{self.name or 'Unknown'} | "
            f"{self.total_exp_years:.1f} yrs exp | "
            f"{skills_count} skills | "
            f"{exp_count} roles | "
            f"{edu_count} edu entries | "
            f"confidence={self.extraction_confidence:.2f}"
        )


# ──────────────────────────────────────────────────────────────────
# Pydantic models for LangChain structured output
# ──────────────────────────────────────────────────────────────────
# LangChain's .with_structured_output() requires Pydantic BaseModel.
# We define a parallel Pydantic schema here, then convert it to our
# dataclass after validation. This keeps the two systems separate —
# Pydantic for LLM I/O validation, dataclasses for internal logic.

class PydanticExperience(BaseModel):
    company:         str  = Field(default="", description="Company or organisation name")
    title:           str  = Field(default="", description="Job title / role")
    start_date:      str  = Field(default="", description="Start date e.g. 'Jan 2021' or '2021'")
    end_date:        str  = Field(default="", description="End date or 'Present'")
    duration_months: int  = Field(default=0,  description="Approximate duration in months")
    description:     str  = Field(default="", description="Responsibilities or achievements")
    skills_used:     list[str] = Field(default_factory=list, description="Skills mentioned in this role")

class PydanticEducation(BaseModel):
    institution:     str  = Field(default="", description="University or college name")
    degree:          str  = Field(default="", description="Full degree name e.g. 'B.Tech Computer Science'")
    degree_level:    str  = Field(default="", description="One of: bachelors, masters, phd, diploma, high_school")
    field_of_study:  str  = Field(default="", description="Field e.g. 'Computer Science'")
    graduation_year: str  = Field(default="", description="Year of graduation or 'Expected YYYY'")
    cgpa:            str  = Field(default="", description="CGPA or GPA as string")

class PydanticCandidateProfile(BaseModel):
    """
    The schema we pass to LangChain's with_structured_output().
    The LLM is forced to return JSON matching exactly this shape.
    Field descriptions are sent to the LLM as instructions — write them clearly.
    """
    name:             str  = Field(default="", description="Candidate's full name")
    email:            str  = Field(default="", description="Email address")
    phone:            str  = Field(default="", description="Phone number with country code if present")
    linkedin:         str  = Field(default="", description="LinkedIn profile URL or username")
    github:           str  = Field(default="", description="GitHub profile URL or username")
    location:         str  = Field(default="", description="City, state or country")
    summary:          str  = Field(default="", description="Candidate's professional summary or objective")

    technical_skills: list[str] = Field(default_factory=list, description="Technical skills: programming languages, frameworks, databases, cloud platforms")
    soft_skills:      list[str] = Field(default_factory=list, description="Soft skills: leadership, communication, teamwork etc.")
    tools:            list[str] = Field(default_factory=list, description="Tools and software: Docker, Git, Jira, Figma etc.")
    languages:        list[str] = Field(default_factory=list, description="Programming languages only: Python, Java, Go, JavaScript etc.")

    experience:       list[PydanticExperience]  = Field(default_factory=list)
    education:        list[PydanticEducation]   = Field(default_factory=list)
    total_exp_years:  float = Field(default=0.0, description="Total years of professional experience (sum all roles)")
    current_title:    str   = Field(default="",  description="Most recent job title")
    current_company:  str   = Field(default="",  description="Most recent company")
    highest_degree:   str   = Field(default="",  description="Highest degree: bachelors / masters / phd / diploma")
    primary_field:    str   = Field(default="",  description="Primary field of study")


def pydantic_to_dataclass(p: PydanticCandidateProfile) -> CandidateProfile:
    """
    Convert a validated Pydantic model → our internal CandidateProfile dataclass.
    Called at the end of llm_extractor after LangChain returns a result.
    """
    experience = [
        ExperienceEntry(
            company=e.company, title=e.title,
            start_date=e.start_date, end_date=e.end_date,
            duration_months=e.duration_months, description=e.description,
            skills_used=e.skills_used,
        )
        for e in p.experience
    ]
    education = [
        EducationEntry(
            institution=e.institution, degree=e.degree,
            degree_level=e.degree_level, field_of_study=e.field_of_study,
            graduation_year=e.graduation_year, cgpa=e.cgpa,
        )
        for e in p.education
    ]
    all_skills = list(set(p.technical_skills + p.soft_skills + p.tools))

    return CandidateProfile(
        name=p.name, email=p.email, phone=p.phone,
        linkedin=p.linkedin, github=p.github, location=p.location,
        summary=p.summary,
        skills=all_skills,
        technical_skills=p.technical_skills,
        soft_skills=p.soft_skills,
        tools=p.tools,
        languages=p.languages,
        experience=experience,
        total_exp_years=p.total_exp_years,
        current_title=p.current_title,
        current_company=p.current_company,
        education=education,
        highest_degree=p.highest_degree,
        primary_field=p.primary_field,
    )