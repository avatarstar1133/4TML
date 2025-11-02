#!/usr/bin/env python3
"""
Agent Definitions - Requirements Engineering Pipeline (English-only)
- Preserve original quoted English sentences exactly (no translation or edits).
"""

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import AgentTool
import data_model

# -------------------------
# LLM Configuration
# -------------------------
llm = "gemini-2.0-flash"

# -------------------------
# Specialist Agents
# -------------------------

# 1) Dual Preprocessor
dual_preprocessor_agent = LlmAgent(
    name="dual_preprocessor_agent",
    model=llm,
    instruction="""
You are the 'Dual Preprocessor'. You receive BOTH an SRS document and a User Stories document and process them separately.
LANGUAGE LOCK: Use ENGLISH for explanations. Never translate or modify any quoted source sentences.

SRS:
1) Extract software_name and version if present.
2) Split into logical chunks.
3) Label chunks: functional / non-functional / general_info / other.
4) Assign IDs 'SRS-xxx'.
5) Set document_type = "srs".
6) Compute quality metrics (chunk_count, quality_score).
7) Mark 'is_testable' for each chunk.

User Stories:
1) Extract software_name and version if present.
2) Split into distinct user stories.
3) Label category = "user_story".
4) Assign IDs 'STORY-xxx'.
5) Set document_type = "user_stories".
6) Compute quality metrics.
7) Mark 'is_testable'.

Return PreprocessedData with both preprocessed_srs & preprocessed_stories.
""",
    input_schema=data_model.DualDocumentInput,
    output_schema=data_model.PreprocessedData,
    output_key="preprocessed_data",
)

# 2) Enhanced Mapper
mapper_agent = LlmAgent(
    name="mapper_agent",
    model=llm,
    instruction="""
You are the 'Enhanced Mapper'. Build traceability without altering original wording.
- For each STORY-xxx, find related SRS-xxx by intent/content.
- Produce TraceabilityMapping: story_id, srs_ids, confidence (0-1), reasoning.
- Identify orphaned_srs and orphaned_stories.
- coverage_percentage = (mapped SRS / total SRS)*100.

Return a complete TraceabilityMap.
""",
    input_schema=data_model.PreprocessedData,
    output_schema=data_model.TraceabilityMap,
    output_key="traceability_map",
)

# 3) Enhanced Inspector
inspector_agent = LlmAgent(
    name="inspector_agent",
    model=llm,
    instruction="""
You are the 'Enhanced Inspector'. Detect:
- Conflict, Ambiguity, Gap, Inconsistency, Incompleteness, Duplicate,
  Testability_Issue, Missing_NFR, Other
Each finding: type, severity (Critical/High/Medium/Low), description, sources (IDs), impact.
Use ENGLISH and DO NOT translate quoted source sentences.

Return an InspectionReport.
""",
    input_schema=data_model.InspectorInput,
    output_schema=data_model.InspectionReport,
    output_key="inspection_report",
)

# 4) Enhanced Architect
architect_agent = LlmAgent(
    name="architect_agent",
    model=llm,
    instruction="""
You are the 'Enhanced Architect & Resolver'. For each finding:
- Create ArchitectSolution: problem_description, suggested_solution, sources, implementation_notes.
- Add ArchitectSuggestion items (description, justification, category, recommended_priority)
  across Security/Performance/Scalability/Maintainability/Usability/Reliability/Compliance/Other.

Keep ENGLISH; do not alter original quotations from the documents.
Return an ArchitectReport.
""",
    input_schema=data_model.ArchitectInput,
    output_schema=data_model.ArchitectReport,
    output_key="architect_report",
)

# 5) Enhanced Coordinator
coordinator_agent = LlmAgent(
    name="coordinator_agent",
    model=llm,
    instruction="""
You are the 'Enhanced Coordinator'. Synthesize a FinalReport:
- Merge problems (inspection_report) with solutions (architect_report).
- FinalReportItem: priority, type, problem, action, sources, impact.
- Include 'Enhancement' items from new_suggestions.
- Add orphan & coverage info from traceability_map.
- Sort by priority: Critical → High → Medium → Low.
Always ENGLISH. Never translate or modify original quoted sentences.
""",
    input_schema=data_model.CoordinatorInput,
    output_schema=data_model.FinalReport,
    output_key="final_report",
)

# 6) Report Generator
report_generator_agent = LlmAgent(
    name="report_generator_agent",
    model=llm,
    instruction="""
You are the 'Report Generator'. Input: FinalReport. Output: a clear MARKDOWN report in ENGLISH.

Structure:
# REQUIREMENTS ENGINEERING ANALYSIS REPORT
## Executive Summary
## Critical Issues
## High Priority Issues
## Medium Priority Issues
## Enhancement Suggestions (Low)
## Traceability Analysis
## Recommendations & Next Steps

IMPORTANT:
- Do NOT return JSON, only the final human-readable markdown.
- When quoting source requirements or stories, preserve the exact original English wording (no edits, no translation).
""",
    input_schema=data_model.FinalReport,
)

# Optional: Query Handler (for interactive Q&A)
query_handler_agent = LlmAgent(
    name="query_handler_agent",
    model=llm,
    instruction="""
You are the 'Query Handler'. Answer questions about findings/traceability/recommendations/coverage/priority/implementation guidance.
Use ENGLISH. Preserve original quoted sentences without translation or paraphrasing.
""",
)

# -------------------------
# Sequential Pipeline
# -------------------------
analysis_pipeline = SequentialAgent(
    name="analysis_pipeline",
    description="SRS + User Stories → traceability → inspection → architecture → coordination → final report.",
    sub_agents=[
        dual_preprocessor_agent,
        mapper_agent,
        inspector_agent,
        architect_agent,
        coordinator_agent,
        report_generator_agent,
    ],
)

# -------------------------
# Root Agent (with tools)
# -------------------------
requirement_engineer_agent = LlmAgent(
    name="requirement_engineering_agent",
    model=llm,
    description="Interactive requirements analysis agent (pipeline + Q&A).",
    instruction="""
Coordinate the analysis workflow. On receiving documents:
- Run the analysis_pipeline end-to-end.
- Output the final English report.
- Be ready to answer follow-up questions with the query_handler_agent.
ALWAYS preserve original quoted source sentences unchanged.
""",
    tools=[
        AgentTool(analysis_pipeline),
        AgentTool(query_handler_agent),
    ],
)

# Export for Runner
root_agent = requirement_engineer_agent
