#!/usr/bin/env python3
"""
CLI Runner for Requirements Engineering Agent (SequentialAgent Version)
Automatically executes all agents in sequence
"""

import json
import sys
import asyncio
import argparse
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent_definitions import root_agent
from document_splitter import split_combined_document, detect_document_type

try:
    import config
    config.setup_api_key()
except ImportError:
    pass

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_step(message: str, step_num: Optional[int] = None):
    if step_num:
        print(f"\n{Colors.BOLD}{Colors.BLUE}[STEP {step_num}]{Colors.END} {Colors.CYAN}{message}{Colors.END}")
    else:
        print(f"{Colors.CYAN}{message}{Colors.END}")

def print_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message: str):
    print(f"{Colors.RED}✗ ERROR: {message}{Colors.END}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

def print_info(message: str):
    print(f"{Colors.CYAN}ℹ {message}{Colors.END}")

def load_api_key():
    """Load API key from environment or .env file"""
    api_key = os.environ.get('GOOGLE_API_KEY')
    
    if api_key:
        print_success("API key loaded from environment variable")
        return api_key
    
    env_file = Path('.env')
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GOOGLE_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        os.environ['GOOGLE_API_KEY'] = api_key
                        print_success("API key loaded from .env file")
                        return api_key
        except Exception as e:
            print_warning(f"Could not read .env file: {e}")
    
    print_error("Google API key not found!")
    print("\nPlease set your API key using one of these methods:")
    print("1. Environment variable:")
    print("   export GOOGLE_API_KEY=\"your-api-key\"")
    print("2. Create a .env file with:")
    print("   GOOGLE_API_KEY=your-api-key")
    print("\nGet your API key from: https://aistudio.google.com/app/apikey")
    sys.exit(1)

def read_input_file(file_path: str) -> str:
    """Read input file and return raw text"""
    print_step(f"Reading input from: {file_path}", 1)
    
    try:
        path = Path(file_path)
        if not path.exists():
            print_error(f"Input file not found: {file_path}")
            sys.exit(1)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print_success(f"Loaded input ({len(content)} characters)")
        return content
    
    except Exception as e:
        print_error(f"Failed to read input file: {str(e)}")
        sys.exit(1)

def write_output_file(file_path: str, report_content: str):
    """Write only the final report content to TXT file"""
    print_step(f"Writing output to: {file_path}")
    
    try:
        path = Path(file_path)
        
        # Write only the report content, nothing else
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print_success(f"Output written successfully")
        print_info(f"Report length: {len(report_content)} characters")
        
    except Exception as e:
        print_error(f"Failed to write output file: {str(e)}")
        sys.exit(1)

def is_json_response(text: str) -> bool:
    """Check if text is a JSON response from intermediate agents"""
    text = text.strip()
    # Check if it starts with JSON structure
    if text.startswith('{') or text.startswith('['):
        try:
            json.loads(text)
            return True
        except:
            pass
    return False

def extract_final_report(text: str) -> str:
    """Extract only the natural language report, skip JSON data"""
    lines = text.split('\n')
    report_lines = []
    skip_json = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip JSON blocks
        if stripped.startswith('{') or stripped.startswith('['):
            skip_json = True
            continue
        
        if skip_json:
            if stripped.endswith('}') or stripped.endswith(']'):
                skip_json = False
            continue
        
        # Skip lines that look like JSON fields
        if '"chunk_id"' in stripped or '"category"' in stripped or '"text"' in stripped:
            continue
        if '"software_name"' in stripped or '"version"' in stripped or '"document_type"' in stripped:
            continue
        if '"mappings"' in stripped or '"findings"' in stripped or '"solutions"' in stripped:
            continue
        
        # Keep meaningful content
        if stripped and not stripped.startswith('"'):
            report_lines.append(line)
    
    return '\n'.join(report_lines).strip()

def build_sequential_input(document_text: str) -> dict:
    """
    Build input for SequentialAgent.
    For SequentialAgent, we need to provide the initial input that the first agent expects.
    """
    
    doc_type = detect_document_type(document_text)
    
    print_info(f"Document type detected: {doc_type}")
    
    if doc_type == 'both':
        print_success("Document contains both SRS and User Stories")
        
        # Split the document
        split_result = split_combined_document(document_text)
        
        if split_result['has_both']:
            srs_text = split_result['srs_text']
            stories_text = split_result['stories_text']
            
            print_info(f"SRS section: {len(srs_text)} characters")
            print_info(f"User Stories section: {len(stories_text)} characters")
            
            # For SequentialAgent, we provide structured input
            # The first agent (preprocessor) expects DocumentInput
            return {
                "srs_document": srs_text,
                "user_stories": stories_text,
                "full_document": document_text
            }
        else:
            return {
                "full_document": document_text
            }
    
    else:
        print_warning(f"Document appears to be {doc_type} only")
        return {
            "full_document": document_text
        }

async def process_documents_async(document_text: str) -> str:
    """Process documents through the SequentialAgent and return only the final report"""
    
    print_step("Preparing Document for Analysis", 2)
    
    if not os.environ.get('GOOGLE_API_KEY'):
        print_error("GOOGLE_API_KEY not set in environment!")
        sys.exit(1)
    
    # Build input data
    print_step("Building Analysis Input", 3)
    input_data = build_sequential_input(document_text)
    
    # Build the prompt for SequentialAgent
    prompt = f"""Please analyze this requirements document for CampusRide application.

The document contains BOTH SRS specifications and User Stories.

FULL DOCUMENT:
═══════════════════════════════════════════════════════════════════════════
{document_text}
═══════════════════════════════════════════════════════════════════════════

Please execute the complete requirements engineering analysis workflow:

1. Preprocess the SRS section and User Stories section separately
2. Create traceability mappings between SRS and User Stories
3. Inspect for conflicts, ambiguities, and gaps
4. Generate architectural solutions and suggestions
5. Coordinate all findings into a final prioritized report
6. Generate a comprehensive natural language report

IMPORTANT: At the end, provide ONLY the final natural language report from the report_generator_agent. 
Do not include any JSON data or intermediate outputs. Just the readable report.
"""
    
    print_success(f"Created prompt ({len(prompt)} characters)")
    
    # Setup ADK Runner
    print_step("Initializing ADK Runner with SequentialAgent", 4)
    
    APP_NAME = "requirements_engineering"
    USER_ID = "cli_user"
    SESSION_ID = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    session_service = InMemorySessionService()
    
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )
    
    print_success(f"Session created: {SESSION_ID}")
    
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    print_success("Runner initialized with SequentialAgent")
    
    # Execute the agent
    print_step("Executing Requirements Engineering Pipeline", 5)
    print(f"{Colors.YELLOW}⏳ Running sequential agent pipeline...{Colors.END}\n")
    print_info("This will automatically execute all 6 agents in sequence\n")
    
    try:
        user_message = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )
        
        # Track execution
        agent_calls = {
            'preprocessor_agent': 0,
            'mapper_agent': 0,
            'inspector_agent': 0,
            'architect_agent': 0,
            'coordinator_agent': 0,
            'report_generator_agent': 0
        }
        
        all_text_parts = []
        report_started = False
        last_agent = None
        
        print(f"{Colors.CYAN}Pipeline stages:{Colors.END}")
        print(f"  1. Preprocessing → 2. Mapping → 3. Inspection → 4. Architecture → 5. Coordination → 6. Report Generation")
        print()
        
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=user_message
        ):
            if hasattr(event, 'content'):
                content = event.content
                
                if hasattr(content, 'parts'):
                    for part in content.parts:
                        # Track function calls
                        if hasattr(part, 'function_call') and part.function_call:
                            func_name = part.function_call.name
                            if func_name in agent_calls:
                                agent_calls[func_name] += 1
                                last_agent = func_name
                                print(f"{Colors.YELLOW}▶ Stage: {func_name}{Colors.END}")
                                
                                # Mark when report generator starts
                                if func_name == 'report_generator_agent':
                                    report_started = True
                                    all_text_parts = []  # Clear previous outputs
                        
                        # Track completions
                        if hasattr(part, 'function_response') and part.function_response:
                            func_name = part.function_response.name
                            if func_name in agent_calls:
                                print(f"{Colors.GREEN}✓ Completed: {func_name}{Colors.END}")
                        
                        # Collect text responses ONLY after report_generator_agent starts
                        if hasattr(part, 'text') and part.text:
                            text_content = part.text.strip()
                            if text_content:
                                # Only collect if it's not JSON and looks like natural language
                                if not is_json_response(text_content):
                                    # Check if it contains report markers
                                    if any(marker in text_content.lower() for marker in [
                                        'executive summary', 'critical issues', 'priority',
                                        'recommendations', 'analysis', 'findings',
                                        'conflict', 'ambiguity', 'gap', 'enhancement'
                                    ]):
                                        all_text_parts.append(text_content)
                                    # Or if report_generator_agent has already run
                                    elif agent_calls.get('report_generator_agent', 0) > 0:
                                        all_text_parts.append(text_content)
            
            elif hasattr(event, 'text') and event.text:
                text_content = event.text.strip()
                if text_content and not is_json_response(text_content):
                    if agent_calls.get('report_generator_agent', 0) > 0:
                        all_text_parts.append(text_content)
        
        # Combine collected text parts
        if all_text_parts:
            final_report = "\n\n".join(all_text_parts).strip()
        else:
            final_report = "No natural language report was generated. The pipeline may have only returned structured data."
        
        # Clean up any remaining JSON artifacts
        final_report = extract_final_report(final_report)
        
        if not final_report:
            print_warning("Pipeline completed but returned empty report")
            final_report = "The pipeline executed successfully but did not generate a readable report."
        
        total_calls = sum(agent_calls.values())
        
        print()
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}   SEQUENTIAL PIPELINE SUMMARY{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print()
        
        if total_calls > 0:
            print(f"{Colors.CYAN}Sub-agent executions detected: {total_calls}{Colors.END}")
            print()
            for agent, count in agent_calls.items():
                if count > 0:
                    print(f"{Colors.GREEN}✓ {agent}: {count} execution(s){Colors.END}")
        else:
            print(f"{Colors.CYAN}Sequential pipeline executed as a single unit{Colors.END}")
        
        print()
        print(f"{Colors.BOLD}{Colors.GREEN}✓ PIPELINE COMPLETE - Analysis generated successfully!{Colors.END}")
        print()
        
        return final_report
        
    except Exception as e:
        print_error(f"Pipeline execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Requirements Engineering Agent - Sequential Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py
  python run_agent.py --input requirements.txt --output analysis.txt
  python run_agent.py -i input.txt -o output.txt -v
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        default='input.txt',
        help='Input file path (default: input.txt)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='output.txt',
        help='Output file path (default: output.txt)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Print header
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}   Requirements Engineering - Sequential Pipeline{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}\n")
    
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print()
    
    # Check and load API key
    load_api_key()
    print()
    
    try:
        # Step 1: Read input
        document_text = read_input_file(args.input)
        
        # Step 2-5: Process through sequential pipeline
        final_report = asyncio.run(process_documents_async(document_text))
        
        # Step 6: Write output (only the report content)
        write_output_file(args.output, final_report)
        
        # Final summary
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}   ✓ ANALYSIS COMPLETE{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")
        
        print(f"{Colors.CYAN}Results saved to: {args.output}{Colors.END}")
        print(f"{Colors.CYAN}Report length: {len(final_report)} characters{Colors.END}")
        print(f"{Colors.GREEN}Status: Sequential pipeline executed successfully{Colors.END}")
        print()
        
    except KeyboardInterrupt:
        print_warning("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nFatal error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()