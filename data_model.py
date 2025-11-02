from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Literal, Optional

# All pydantic Data Models

class AdkBaseModel(BaseModel):
    """A base model that is compatible with Google's Gemini API."""
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def model_json_schema(cls, **kwargs):
        """Override to remove additionalProperties from the schema."""
        schema = super().model_json_schema(**kwargs)

        def remove_additional_properties(obj):
            """Recursively remove additionalProperties from schema."""
            if isinstance(obj, dict):
                obj.pop('additionalProperties', None)
                for value in obj.values():
                    remove_additional_properties(value)
            elif isinstance(obj, list):
                for item in obj:
                    remove_additional_properties(item)

        remove_additional_properties(schema)
        return schema

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
    # NEW: Add testability indicator
    is_testable: bool = Field(
        default=True,
        description="Whether this requirement is testable/verifiable"
    )

class PreprocessedDoc(AdkBaseModel):
    """Structured output from the Preprocessor agent for one document."""
    software_name: Optional[str] = Field(
        default=None,
        description="The name of the software product, e.g., 'Project Titan'."
    )
    version: Optional[str] = Field(
        default=None,
        description="The document version, e.g., 'v1.2' or '2025-11-01'."
    )
    document_type: Literal["srs", "user_stories"] = Field(
        description="The type of document that was processed."
    )
    chunks: List[RequirementChunk] = Field(
        description="A complete list of all indexed chunks from the document."
    )
    # NEW: Quality metrics
    chunk_count: int = Field(
        description="Total number of chunks identified"
    )
    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="0-1 score indicating document completeness and quality"
    )

class TraceabilityMapping(AdkBaseModel):
    """A single mapping between a user story and related SRS requirements."""
    story_id: str = Field(
        description="The User Story chunk_id (e.g., 'STORY-001')"
    )
    srs_ids: List[str] = Field(
        description="List of related SRS chunk_ids (e.g., ['SRS-001', 'SRS-002'])"
    )
    # NEW: Confidence and reasoning
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in this mapping (0-1)"
    )
    reasoning: str = Field(
        description="Brief explanation of why these are related"
    )

class TraceabilityMap(AdkBaseModel):
    """Structured output from the Mapper agent with bidirectional traceability."""
    mappings: List[TraceabilityMapping] = Field(
        description="A list of mappings between User Story chunk_ids and their related SRS chunk_ids."
    )
    # NEW: Orphaned requirements tracking
    orphaned_srs: List[str] = Field(
        default_factory=list,
        description="SRS requirements not linked to any user story"
    )
    orphaned_stories: List[str] = Field(
        default_factory=list,
        description="User stories not linked to any SRS requirement"
    )
    coverage_percentage: float = Field(
        ge=0.0, le=100.0,
        description="Percentage of SRS requirements covered by user stories"
    )

class InspectionFinding(AdkBaseModel):
    """A single problem found by the Inspector agent."""
    # NEW: More granular finding types
    type: Literal[
        "Conflict",
        "Ambiguity",
        "Gap",
        "Inconsistency",
        "Incompleteness",
        "Duplicate",
        "Testability_Issue",
        "Missing_NFR",
        "Other"
    ]
    # NEW: Severity levels
    severity: Literal["Critical", "High", "Medium", "Low"] = Field(
        description="Impact severity of this finding"
    )
    description: str = Field(
        description="A clear description of the problem found."
    )
    sources: List[str] = Field(
        description="The list of chunk_ids that are involved in this finding."
    )
    # NEW: Business impact
    impact: str = Field(
        description="Explanation of the business/technical impact"
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
    # NEW: Implementation guidance
    implementation_notes: Optional[str] = Field(
        default=None,
        description="Technical guidance for implementing this solution"
    )

class ArchitectSuggestion(AdkBaseModel):
    """A new enhancement proposed by the Architect agent."""
    description: str = Field(
        description="A description of the new or missing requirement."
    )
    justification: str = Field(
        description="The reason this suggestion is important (e.g., 'Security', 'Performance')."
    )
    # NEW: Category and priority
    category: Literal[
        "Security",
        "Performance",
        "Scalability",
        "Maintainability",
        "Usability",
        "Reliability",
        "Compliance",
        "Other"
    ] = Field(
        description="The category of this enhancement"
    )
    recommended_priority: Literal["High", "Medium", "Low"] = Field(
        description="Suggested implementation priority"
    )

class ArchitectReport(AdkBaseModel):
    """Structured output from the Architect agent."""
    solutions: List[ArchitectSolution]
    new_suggestions: List[ArchitectSuggestion]

class FinalReportItem(AdkBaseModel):
    """A single, prioritized item for the end-user."""
    priority: Literal["Critical", "High", "Medium", "Low"]
    type: Literal[
        "Conflict",
        "Ambiguity",
        "Gap",
        "Enhancement",
        "Quality_Issue",
        "Missing_Requirement"
    ]
    problem: str
    action: str
    sources: List[str]
    impact: str = Field(
        description="Business/technical impact description"
    )

class FinalReport(AdkBaseModel):
    """The final, single report for the end-user."""
    report: List[FinalReportItem]

# Agent I/O Models

class DualDocumentInput(AdkBaseModel):
    """Input containing both SRS and User Stories documents."""
    srs_document: str = Field(
        min_length=100,
        description="The raw text content of the SRS document"
    )
    user_stories_document: str = Field(
        min_length=100,
        description="The raw text content of the User Stories document"
    )

    @field_validator('srs_document', 'user_stories_document')
    @classmethod
    def validate_content(cls, v):
        if len(v.strip()) < 100:
            raise ValueError("Document content is too short (minimum 100 characters)")
        return v


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
    preprocessed_stories: PreprocessedDoc


class CoordinatorInput(AdkBaseModel):
    """The data needed by the Coordinator agent."""
    inspection_report: InspectionReport
    architect_report: ArchitectReport
    traceability_map: TraceabilityMap