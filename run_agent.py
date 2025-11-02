#!/usr/bin/env python3
"""
CLI Runner for Requirements Engineering Agent (English-only, with Q&A)
- ENGLISH logs & prompts.
- STRICT: Never translate or modify original quoted source content.
- Supports follow-up Q&A in the SAME session via --ask "your question".
"""

import sys
import asyncio
import argparse
import os
from pathlib import Path
from datetime import datetime

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent_definitions import root_agent  # root has both pipeline & query handler
from document_splitter import split_combined_document, detect_document_type

# ---------- Console helpers ----------
class Colors:
    END = "\033[0m"; BOLD = "\033[1m"; HEADER = "\033[95m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; GREEN = "\033[92m"
    YELLOW = "\033[93m"; RED = "\033[91m"

def print_step(msg, n=None):
    prefix = f"[STEP {n}] " if n is not None else ""
    print(f"{Colors.BLUE}{prefix}{msg}{Colors.END}")

def print_success(msg): print(f"{Colors.GREEN}✓ {msg}{Colors.END}")
def print_error(msg):   print(f"{Colors.RED}✗ {msg}{Colors.END}")
def print_warning(msg): print(f"{Colors.YELLOW}! {msg}{Colors.END}")
def print_info(msg):    print(f"{Colors.CYAN}{msg}{Colors.END}")

def is_json_response(text: str) -> bool:
    t = text.strip()
    if t.startswith("```json") and t.endswith("```"):
        t = t[7:-3].strip()
    return (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]"))

def extract_final_report(text: str) -> str:
    """
    Keep readable report (markdown/text). Strip stray JSON blocks but be forgiving.
    """
    if not text:
        return ""
    low = text.lower()
    if "```markdown" in low:
        start = low.find("```markdown")
        end = low.find("```", start + 3)
        if end != -1:
            return text[start + len("```markdown"): end].strip()
    out, skip = [], False
    for line in text.splitlines():
        l = line.strip().lower()
        if l.startswith("```json"):
            skip = True; continue
        if l.startswith("```") and skip:
            skip = False; continue
        if not skip:
            out.append(line)
    cleaned = "\n".join(out).strip()
    return cleaned or text.strip()
# -------------------------------------

# Load API key from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def load_api_key():
    api_key = os.environ.get('GOOGLE_API_KEY')
    if api_key:
        print_success("API key loaded from environment variable")
        return api_key
    env_file = Path('.env')
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('GOOGLE_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                    os.environ['GOOGLE_API_KEY'] = api_key
                    print_success("API key loaded from .env file")
                    return api_key
        except Exception as e:
            print_warning(f"Could not read .env file: {e}")
    print_error("Google API key not found!")
    print("\nSet your API key via:")
    print("1) export GOOGLE_API_KEY=\"your-api-key\"")
    print("2) .env file: GOOGLE_API_KEY=your-api-key")
    sys.exit(1)

def read_input_file(file_path: str) -> str:
    print_step(f"Reading input from: {file_path}", 1)
    path = Path(file_path)
    if not path.exists():
        print_error(f"Input file not found: {file_path}"); sys.exit(1)
    content = path.read_text(encoding='utf-8')
    print_success(f"Loaded input ({len(content)} characters)")
    return content

def write_output_file(file_path: str, report_content: str):
    print_step(f"Writing output to: {file_path}")
    Path(file_path).write_text(report_content, encoding='utf-8')
    print_success("Output written successfully")
    print_info(f"Report length: {len(report_content)} characters")

def build_dual_document_input(document_text: str) -> dict:
    doc_type = detect_document_type(document_text)
    print_info(f"Document type detected: {doc_type}")
    if doc_type == 'both':
        print_success("Input appears to contain BOTH SRS and User Stories")
        split_result = split_combined_document(document_text)
        if split_result.get('has_both'):
            return {
                "srs_document": split_result['srs_text'],
                "user_stories_document": split_result['stories_text'],
            }
        return {"srs_document": document_text, "user_stories_document": "No user stories found in the document."}
    if doc_type == 'srs':
        print_warning("Input appears to be SRS only")
        return {"srs_document": document_text, "user_stories_document": "No user stories provided."}
    if doc_type == 'user_stories':
        print_warning("Input appears to be User Stories only")
        return {"srs_document": "No SRS document provided.", "user_stories_document": document_text}
    print_warning("Document type unclear; treating as SRS")
    return {"srs_document": document_text, "user_stories_document": "No user stories provided."}

async def run_pipeline_and_collect(session_service, runner, user_id, session_id, prompt, verbose=False) -> str:
    user_message = types.Content(role="user", parts=[types.Part(text=prompt)])
    agent_counts = {}
    all_text_parts = []

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=user_message):
        content = getattr(event, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", []) or []
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc:
                name = getattr(fc, "name", None)
                if name:
                    agent_counts[name] = agent_counts.get(name, 0) + 1
                    if verbose:
                        print(f"{Colors.YELLOW}▶ Stage: {name}{Colors.END}")
            fr = getattr(part, "function_response", None)
            if fr and getattr(fr, "name", None) and verbose:
                print(f"{Colors.GREEN}✓ Completed: {fr.name}{Colors.END}")
            text_piece = getattr(part, "text", None)
            if text_piece:
                t = text_piece.strip()
                if not is_json_response(t):
                    all_text_parts.append(t)

    if agent_counts:
        print_info("Sub-agent executions:")
        for k, v in agent_counts.items():
            print(f"{Colors.GREEN}✓ {k}: {v}{Colors.END}")

    final_report = "\n\n".join(all_text_parts).strip()
    final_report = extract_final_report(final_report) or "Report generation returned empty content."
    print_success("Pipeline finished")
    return final_report

async def ask_follow_up_in_same_session(runner, user_id, session_id, question: str) -> str:
    qa_message = types.Content(role="user", parts=[types.Part(text=question)])
    chunks = []
    async for ev in runner.run_async(user_id=user_id, session_id=session_id, new_message=qa_message):
        c = getattr(ev, "content", None)
        if not c:
            continue
        for p in getattr(c, "parts", []) or []:
            if getattr(p, "text", None):
                chunks.append(p.text)
    return "\n".join(chunks).strip()

def main():
    parser = argparse.ArgumentParser(
        description="Requirements Engineering Agent - Sequential Pipeline Runner (EN-only, with Q&A)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py
  python run_agent.py -i input.txt -o output.txt
  python run_agent.py -i input.txt -o output.txt --ask "List critical conflicts"
        """,
    )
    parser.add_argument('--input', '-i', default='input.txt', help='Input file path (default: input.txt)')
    parser.add_argument('--output', '-o', default='output.txt', help='Output file path (default: output.txt)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--ask', help='Ask a follow-up question in the SAME session (uses query_handler_agent)')
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}   Requirements Engineering - Sequential Pipeline (EN){Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}\n")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}\n")

    load_api_key()

    try:
        document_text = read_input_file(args.input)

        # Build prompt
        print_step("Preparing document for analysis", 2)
        input_data = build_dual_document_input(document_text)
        prompt = f"""You are a Requirements Engineering pipeline. Perform the complete workflow below.
LANGUAGE LOCK: Use ENGLISH for all explanations and headings. Never translate or modify any quoted sentences from the original documents—preserve exact wording.

SRS DOCUMENT:
═══════════════════════════════════════════════════════════════════════
{input_data['srs_document']}
═══════════════════════════════════════════════════════════════════════

USER STORIES DOCUMENT:
═══════════════════════════════════════════════════════════════════════
{input_data['user_stories_document']}
═══════════════════════════════════════════════════════════════════════

Execute:
1) Preprocess SRS & User Stories separately
2) Create traceability mappings
3) Inspect conflicts/ambiguities/gaps/quality issues
4) Propose architectural solutions & enhancement suggestions
5) Coordinate into a prioritized final report
6) Generate a comprehensive natural-language MARKDOWN report

IMPORTANT OUTPUT RULES:
- Provide ONLY the final markdown report in ENGLISH.
- Do NOT output JSON or intermediate objects.
- When quoting from the source, keep the exact original text (no translation, no paraphrasing).
"""
        print_success(f"Created prompt ({len(prompt)} characters)")

        # One session & one runner for both pipeline and follow-up Q&A
        print_step("Initializing ADK Runner (root agent = requirement_engineer_agent)", 3)
        APP_NAME = "requirements_engineering"
        USER_ID = "cli_user"
        SESSION_ID = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        session_service = InMemorySessionService()
        # IMPORTANT: create session BEFORE runner usage
        asyncio.run(session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID))
        runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
        print_success(f"Session created: {SESSION_ID}")
        print_success("Runner initialized")

        print_step("Executing pipeline", 4)
        final_report = asyncio.run(
            run_pipeline_and_collect(session_service, runner, USER_ID, SESSION_ID, prompt, args.verbose)
        )
        write_output_file(args.output, final_report)

        # Optional follow-up Q&A in the SAME session
        if args.ask:
            print_step("Follow-up Q&A (same session)", 5)
            answer = asyncio.run(ask_follow_up_in_same_session(runner, USER_ID, SESSION_ID, args.ask))
            print_success("Q&A Answer:")
            print(answer or "(empty)")

        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}   ✓ ANALYSIS COMPLETE{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")
        print(f"{Colors.CYAN}Results saved to: {args.output}{Colors.END}")
        print(f"{Colors.CYAN}Report length: {len(final_report)} characters{Colors.END}")
        print(f"{Colors.GREEN}Status: Sequential pipeline executed successfully{Colors.END}\n")

    except KeyboardInterrupt:
        print_warning("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nFatal error: {str(e)}")
        import traceback; traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
