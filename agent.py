# ADK & Model Imports
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import AgentTool
import data_model
from utils import load_instruction

# --------------------------------------------------------------------------
# == Define the 6 Specialist Agents ==
# --------------------------------------------------------------------------

llm = "gemini-2.0-flash"

# --- Agent 1: Dual Preprocessor ---
dual_preprocessor_agent = LlmAgent(
    name="dual_preprocessor_agent",
    model=llm,
    instruction=load_instruction("./instructions/preprocess_instruction.txt"),
    input_schema=data_model.DualDocumentInput,
    output_schema=data_model.PreprocessedData,
    output_key="preprocessed_data"
)

# --- Agent 2: Enhanced Mapper ---
mapper_agent = LlmAgent(
    name="mapper_agent",
    model=llm,
    instruction=load_instruction("./instructions/mapper_instruction.txt"),
    input_schema=data_model.PreprocessedData,
    output_schema=data_model.TraceabilityMap,
    output_key="traceability_map"
)

# --- Agent 3: Enhanced Inspector ---
inspector_agent = LlmAgent(
    name="inspector_agent",
    model=llm,
    instruction=load_instruction("./instructions/inspector_instruction.txt"),
    input_schema=data_model.InspectorInput,
    output_schema=data_model.InspectionReport,
    output_key="inspection_report"
)

# --- Agent 4: Enhanced Architect ---
architect_agent = LlmAgent(
    name="architect_agent",
    model=llm,
    instruction=load_instruction("./instructions/architect_instruction.txt"),
    input_schema=data_model.ArchitectInput,
    output_schema=data_model.ArchitectReport,
    output_key="architect_report"
)

# --- Agent 5: Enhanced Coordinator ---
coordinator_agent = LlmAgent(
    name="coordinator_agent",
    model=llm,
    instruction=load_instruction("./instructions/coordinator_instruction.txt"),
    input_schema=data_model.CoordinatorInput,
    output_schema=data_model.FinalReport,
    output_key="final_report"
)

# --- Agent 6: Report Generator ---
report_generator_agent = LlmAgent(
    name="report_generator_agent",
    model=llm,
    instruction=load_instruction("./instructions/report_generator_instruction.txt")
)

# --- Agent 7: Query Handler
query_handler_agent = LlmAgent(
    name="query_handler_agent",
    model=llm,
    instruction=load_instruction("./instructions/query_handler_instruction.txt"),
)

# --------------------------------------------------------------------------
# == Define the Workflow ==
# --------------------------------------------------------------------------

analysis_pipeline = SequentialAgent(
    name="analysis_pipeline",
    description="""A comprehensive requirements engineering pipeline that analyzes 
    SRS documents and user stories to identify conflicts, gaps, ambiguities, and 
    improvement opportunities. Provides detailed traceability analysis and 
    actionable recommendations.""",
    sub_agents=[
        dual_preprocessor_agent,
        mapper_agent,
        inspector_agent,
        architect_agent,
        coordinator_agent
    ]
)

requirement_engineer_agent = LlmAgent(
    name='requirement_engineering_agent',
    model=llm,
    description="An interactive agent for requirements engineering that can analyze documents and answer questions",
    instruction=load_instruction("./instructions/requirements_engineering_instruction.txt"),
    tools=[
        AgentTool(analysis_pipeline),
        AgentTool(query_handler_agent),
        AgentTool(report_generator_agent)
    ]
)