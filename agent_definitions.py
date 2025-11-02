from typing import List, Literal, Optional, Dict

from pydantic import BaseModel, ConfigDict, Field

from google.adk.agents import LlmAgent,SequentialAgent
from google.adk.tools import AgentTool


# --------------------------------------------------------------------------
# == Pydantic Base Model ==
# --------------------------------------------------------------------------

class AdkBaseModel(BaseModel):
    """A base model that is compatible with Google's Gemini API."""
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def model_json_schema(cls, **kwargs):
        """Override to remove additionalProperties from the schema."""
        schema = super().model_json_schema(**kwargs)

        def remove_additional_properties(obj):
            if isinstance(obj, dict):
                obj.pop('additionalProperties', None)
                for value in obj.values():
                    remove_additional_properties(value)
            elif isinstance(obj, list):
                for item in obj:
                    remove_additional_properties(item)

        remove_additional_properties(schema)
        return schema


# --------------------------------------------------------------------------
# == Data Models ==
# --------------------------------------------------------------------------

class RequirementChunk(AdkBaseModel):
    """A single, indexed chunk of a requirement document."""
    chunk_id: str = Field(
        description="A unique sequential ID, e.g., 'SRS-001', 'STORY-001'"
    )
    category: Literal["functional", "non-functional", "user_story", "general_info", "other"] = Field(
        description="The classified type of this requirement chunk."
    )
    text: str = Field(
        description="The raw text content of the chunk."
    )


class PreprocessedDoc(AdkBaseModel):
    """Structured output from the Preprocessor agent for one document."""
    software_name: Optional[str] = Field(
        default=None,
        description="The name of the software product, e.g., 'CampusRide'."
    )
    version: Optional[str] = Field(
        default=None,
        description="The document version, e.g., 'v1.0' or '2025-11-01'."
    )
    document_type: Literal["srs", "user_stories"] = Field(
        description="The type of document that was processed."
    )
    chunks: List[RequirementChunk] = Field(
        description="A complete list of all indexed chunks from the document."
    )


class TraceabilityMapping(AdkBaseModel):
    """A single mapping between a user story and related SRS requirements."""
    story_id: str = Field(
        description="The User Story chunk_id (e.g., 'STORY-001')"
    )
    srs_ids: List[str] = Field(
        description="List of related SRS chunk_ids (e.g., ['SRS-001', 'SRS-002'])"
    )


class TraceabilityMap(AdkBaseModel):
    """Structured output from the Mapper agent."""
    mappings: List[TraceabilityMapping] = Field(
        description="A list of mappings between User Story chunk_ids and their related SRS chunk_ids."
    )


class InspectionFinding(AdkBaseModel):
    """A single problem found by the Inspector agent."""
    type: Literal["Conflict", "Ambiguity", "Gap", "Other"]
    description: str = Field(
        description="A clear description of the problem found."
    )
    sources: List[str] = Field(
        description="The list of chunk_ids that are involved in this finding."
    )


class InspectionReport(AdkBaseModel):
    """Structured output from the Inspector agent."""
    findings: List[InspectionFinding]


class ArchitectSolution(AdkBaseModel):
    """A single solution proposed by the Architect agent."""
    problem_description: str = Field(
        description="A summary of the problem being solved (from the InspectionReport)."
    )
    suggested_solution: str = Field(
        description="A specific, actionable solution or rewritten text."
    )
    sources: List[str] = Field(
        description="The original chunk_ids this solution pertains to."
    )


class ArchitectSuggestion(AdkBaseModel):
    """A new enhancement proposed by the Architect agent."""
    description: str = Field(
        description="A description of the new or missing requirement."
    )
    justification: str = Field(
        description="The reason this suggestion is important (e.g., 'Security', 'Performance')."
    )


class ArchitectReport(AdkBaseModel):
    """Structured output from the Architect agent."""
    solutions: List[ArchitectSolution]
    new_suggestions: List[ArchitectSuggestion]


class FinalReportItem(AdkBaseModel):
    """A single, prioritized item for the end-user."""
    priority: Literal["High", "Medium", "Low"]
    type: Literal["Conflict", "Ambiguity", "Gap", "Enhancement"]
    problem: str
    action: str
    sources: List[str]


class FinalReport(AdkBaseModel):
    """The final, single report for the end-user."""
    report: List[FinalReportItem]


# --------------------------------------------------------------------------
# == Agent I/O Models ==
# --------------------------------------------------------------------------

class DocumentInput(AdkBaseModel):
    """Input for the preprocessor agent - a single document text."""
    document_text: str = Field(
        description="The raw text content of a document (either SRS or User Stories)"
    )


class PreprocessedData(AdkBaseModel):
    """The output of the Preprocessor, containing the two structured docs."""
    preprocessed_srs: PreprocessedDoc
    preprocessed_stories: PreprocessedDoc


class InspectorInput(AdkBaseModel):
    """The data needed by the Inspector agent."""
    preprocessed_srs: PreprocessedDoc
    preprocessed_stories: PreprocessedDoc
    traceability_map: TraceabilityMap


class ArchitectInput(AdkBaseModel):
    """The data needed by the Architect agent."""
    inspection_report: InspectionReport
    preprocessed_srs: PreprocessedDoc


class CoordinatorInput(AdkBaseModel):
    """The data needed by the Coordinator agent."""
    inspection_report: InspectionReport
    architect_report: ArchitectReport


# --------------------------------------------------------------------------
# == Agent Definitions ==
# --------------------------------------------------------------------------

llm = "gemini-2.0-flash"

# --- Agent 1: Preprocessor ---
preprocessor_agent = LlmAgent(
    name="preprocessor_agent",
    model=llm,
    instruction="""
    You are the 'Preprocessor' agent.

    Your job is to receive a document text and determine whether it is an SRS document 
    or a User Stories document, then process it accordingly.

    **IMPORTANT: The input document may contain BOTH SRS and User Stories sections.**
    If you detect both types of content in a single document:
    1. Separate the SRS content from the User Stories content
    2. Process each section independently
    3. Return the appropriate document type based on what you're currently processing

    **Identification:**
    - SRS documents typically contain: formal requirements, system specifications, 
      functional/non-functional requirements, technical details, architecture info,
      sections like "INTRODUCTION", "SYSTEM FEATURES", "NON-FUNCTIONAL REQUIREMENTS"
    - User Stories typically contain: "User Story" headers, "As a [user]..." format,
      user-centric scenarios, acceptance criteria

    **If it's an SRS document or SRS section:**
    1. Extract software_name and version if present
    2. Break down into logical requirement chunks
    3. Tag chunks (functional, non-functional, general_info, other)
    4. Assign sequential IDs starting with 'SRS-' (e.g., 'SRS-001', 'SRS-002')
    5. Set document_type to "srs"

    **If it's User Stories or User Stories section:**
    1. Extract software_name and version if present
    2. Break down into individual user stories
    3. Tag all chunks with category 'user_story'
    4. Assign sequential IDs starting with 'STORY-' (e.g., 'STORY-001', 'STORY-002')
    5. Set document_type to "user_stories"

    Return *only* a `PreprocessedDoc` object with the processed document section.
    """,
    input_schema=DocumentInput,
    output_schema=PreprocessedDoc
)

# --- Agent 2: Mapper ---
mapper_agent = LlmAgent(
    name="mapper_agent",
    model=llm,
    instruction="""
    You are the 'Mapper' agent. Your job is to create the traceability map.
    1. Read the `preprocessed_srs` and `preprocessed_stories` you are given.
    2. For each user story (STORY-xxx), identify which SRS requirements (SRS-xxx) 
       it relates to by analyzing the content and intent of both.
    3. Create a list of TraceabilityMapping objects where each object contains:
       - story_id: the user story chunk_id (e.g., "STORY-001")
       - srs_ids: a list of related SRS chunk_ids (e.g., ["SRS-001", "SRS-003"])
    4. Return *only* the `TraceabilityMap` object with your list of mappings.
    """,
    input_schema=PreprocessedData,
    output_schema=TraceabilityMap
)

# --- Agent 3: Inspector ---
inspector_agent = LlmAgent(
    name="inspector_agent",
    model=llm,
    instruction="""
    You are the 'Inspector' agent. Your job is to find all problems.
    1. Read the `preprocessed_srs`, `preprocessed_stories`, and `traceability_map`.
    2. Look for:
       - Conflicts: contradictions between SRS and user stories
       - Ambiguities: unclear or vague requirements
       - Gaps: user stories not mapped to any SRS requirement, or SRS requirements 
         without corresponding user stories
    3. For each finding, create an InspectionFinding with:
       - type: "Conflict", "Ambiguity", "Gap", or "Other"
       - description: clear explanation of the problem
       - sources: list of relevant chunk_ids (SRS-xxx and/or STORY-xxx)
    4. Return *only* the `InspectionReport` object with all your findings.
    """,
    input_schema=InspectorInput,
    output_schema=InspectionReport
)

# --- Agent 4: Architect ---
architect_agent = LlmAgent(
    name="architect_agent",
    model=llm,
    instruction="""
    You are the 'Architect & Resolver' agent. Your job is to fix problems
    and suggest improvements.
    1. Read the `inspection_report` and `preprocessed_srs`.
    2. For each finding in `inspection_report`, create an 'ArchitectSolution':
       - Provide a clear problem summary
       - Suggest specific, actionable solution or rewritten text
       - Reference the original chunk_ids involved
    3. Analyze the `preprocessed_srs` for missing or weak requirements:
       - Look for missing non-functional requirements (security, performance, 
         scalability, maintainability, etc.)
       - Identify areas that need more detail or clarification
       - Consider industry best practices
    4. For each improvement idea, create an 'ArchitectSuggestion':
       - Describe the new or enhanced requirement
       - Justify why it's important
    5. Return *only* the `ArchitectReport` object containing both the solutions 
       list and new_suggestions list.
    """,
    input_schema=ArchitectInput,
    output_schema=ArchitectReport
)

# --- Agent 5: Coordinator ---
coordinator_agent = LlmAgent(
    name="coordinator_agent",
    model=llm,
    instruction="""
    You are the 'Coordinator' agent. Your job is to create the final report.
    1. Read the `inspection_report` and `architect_report`.
    2. For each problem in inspection_report:
       - Find the corresponding solution in architect_report
       - Create a 'FinalReportItem' with:
         - priority: "High" for conflicts and critical gaps, "Medium" for ambiguities
         - type: "Conflict", "Ambiguity", "Gap", or "Enhancement"
         - problem: description from inspection report
         - action: solution from architect report
         - sources: the relevant chunk_ids
    3. For each suggestion in architect_report.new_suggestions:
       - Create a 'FinalReportItem' with:
         - priority: "Low" (these are enhancements, not fixes)
         - type: "Enhancement"
         - problem: the justification
         - action: the description of the suggestion
         - sources: empty list (these are new suggestions)
    4. Return *only* the `FinalReport` object with all items prioritized and organized.
    """,
    input_schema=CoordinatorInput,
    output_schema=FinalReport
)

# --------------------------------------------------------------------------
# == Root Agent (STRONGLY ENFORCED WORKFLOW) ==
# --------------------------------------------------------------------------

# root_agent = LlmAgent(
#     name='requirement_engineering_agent',
#     model=llm,
#     description="An agent for engineering requirements from SRS documents and user stories",
#     instruction="""
#     You are the Requirements Engineering Agent. You MUST execute ALL 5 agents in the correct sequence.

#     ═══════════════════════════════════════════════════════════════════════════
#     MANDATORY WORKFLOW - YOU MUST COMPLETE ALL STEPS:
#     ═══════════════════════════════════════════════════════════════════════════

#     STEP 1: PREPROCESSING (REQUIRED)
#     --------------------------------
#     When you receive a document:
#     - If it contains BOTH SRS and User Stories (look for "User Story" markers):
#       * Call preprocessor_agent with ONLY the SRS portion (before "User Story 1")
#       * Call preprocessor_agent again with ONLY the User Stories portion
#     - If it contains only one type:
#       * Process what you have and inform user about missing document

#     STEP 2: MAPPING (REQUIRED - DO NOT SKIP)
#     -----------------------------------------
#     Once you have both preprocessed_srs AND preprocessed_stories:
#     - Create a PreprocessedData object with BOTH documents
#     - Call mapper_agent with this PreprocessedData
#     - Store the returned TraceabilityMap

#     STEP 3: INSPECTION (REQUIRED - DO NOT SKIP)
#     --------------------------------------------
#     After mapping is complete:
#     - Create an InspectorInput with: preprocessed_srs, preprocessed_stories, traceability_map
#     - Call inspector_agent with this InspectorInput
#     - Store the returned InspectionReport

#     STEP 4: ARCHITECTURE (REQUIRED - DO NOT SKIP)
#     ----------------------------------------------
#     After inspection is complete:
#     - Create an ArchitectInput with: inspection_report, preprocessed_srs
#     - Call architect_agent with this ArchitectInput
#     - Store the returned ArchitectReport

#     STEP 5: COORDINATION (REQUIRED - DO NOT SKIP)
#     ----------------------------------------------
#     After architecture is complete:
#     - Create a CoordinatorInput with: inspection_report, architect_report
#     - Call coordinator_agent with this CoordinatorInput
#     - Store the returned FinalReport

#     STEP 6: PRESENT FINAL REPORT (REQUIRED)
#     ----------------------------------------
#     - Present the complete FinalReport to the user
#     - Include all prioritized findings, solutions, and suggestions

#     ═══════════════════════════════════════════════════════════════════════════
#     CRITICAL RULES:
#     ═══════════════════════════════════════════════════════════════════════════
    
#     1. YOU MUST CALL ALL 5 AGENTS (or 6 calls if preprocessor is called twice)
#     2. DO NOT stop after any step - continue until coordinator_agent is called
#     3. DO NOT ask the user for permission to continue - just execute
#     4. DO NOT summarize intermediate results - execute the full pipeline
#     5. Each agent's output is input for the next agent - pass data correctly
#     6. If ANY agent fails, report the error but explain what data it expected

#     ═══════════════════════════════════════════════════════════════════════════
#     EXECUTION CHECKLIST (Check off mentally as you go):
#     ═══════════════════════════════════════════════════════════════════════════
    
#     [ ] Called preprocessor_agent (at least once, maybe twice)
#     [ ] Have both preprocessed_srs and preprocessed_stories
#     [ ] Called mapper_agent with PreprocessedData
#     [ ] Have traceability_map
#     [ ] Called inspector_agent with InspectorInput
#     [ ] Have inspection_report
#     [ ] Called architect_agent with ArchitectInput
#     [ ] Have architect_report
#     [ ] Called coordinator_agent with CoordinatorInput
#     [ ] Have final_report
#     [ ] Presented complete report to user

#     YOUR GOAL: Complete the checklist above. Do not respond until ALL items are checked.
#     """,
#     tools=[
#         AgentTool(preprocessor_agent),
#         AgentTool(mapper_agent),
#         AgentTool(inspector_agent),
#         AgentTool(architect_agent),
#         AgentTool(coordinator_agent)
#     ]
# )
report_generator_agent = LlmAgent(
    name="report_generator_agent",
    model=llm,
    instruction="""
    You are the 'Report Generator' agent. Your job is to convert the structured 
    FinalReport into a comprehensive, natural language report that is easy to read 
    and understand.

    You will receive a FinalReport object containing a list of FinalReportItem objects.
    Each item has: priority, type, problem, action, and sources.

    Create a detailed, professional report with the following structure:

    1. **Executive Summary**: Brief overview of findings and key statistics
    2. **Critical Issues (High Priority)**: Detailed explanation of each High priority item
    3. **Medium Priority Issues**: Explanation of each Medium priority item  
    4. **Enhancement Suggestions (Low Priority)**: Description of each enhancement
    5. **Recommendations**: Overall next steps and action items

    For each issue/enhancement:
    - Write in clear, natural language
    - Explain the problem in context
    - Describe the recommended action
    - Reference the source chunk IDs when relevant
    - Make it actionable and specific

    Format the report professionally using markdown with headers, sections, and lists.
    Make it suitable for presentation to stakeholders.

    Return the complete report as a single string.
    """,
    input_schema=FinalReport
)
root_agent = SequentialAgent(
    name="root_agent",
    description="A pipeline that will take in a srs document and user stories and process for a report of conflicts and improvements",
    sub_agents= [
        preprocessor_agent,
        mapper_agent,
        inspector_agent,
        architect_agent,
        coordinator_agent,
        report_generator_agent
    ]
)