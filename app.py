from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import json
import datetime
import os
import random
import base64
import time
import sys
import asyncio
from dotenv import load_dotenv

# --- FIX: Ép stdout/stderr UTF-8 trên Windows để in emoji & tiếng Việt ---
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# --- Khởi tạo Agent và Session Service ---
load_dotenv() 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Import agent definitions
try:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from agent_definitions import root_agent
    from document_splitter import split_combined_document, detect_document_type
    
    # Tạo session service toàn cục
    session_service = InMemorySessionService()
    APP_NAME = "requirements_engineering"
    
    agent_available = True
except ImportError as e:
    print(f"⚠️ Không thể import Agent: {e}")
    agent_available = False
    session_service = None

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'  # Cần thiết cho Flask session
CORS(app, supports_credentials=True)  # Cho phép credentials

# BIẾN TOÀN CỤC ĐỂ ĐÁNH SỐ THỨ TỰ
message_count = 0
session_start_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Dictionary lưu trữ Runner cho mỗi user session
active_runners = {}
session_data = {}  # Lưu trữ dữ liệu phân tích của mỗi session

# --- HÀM LƯU FILE JSON CÓ CẤU TRÚC ---
def save_structured_data_to_file(data):
    export_dir = "json_exports"
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    session_id = data.get('session_id', 'unknown_session')
    step_id = data.get('user_id', 'step_unknown') 
    file_name = os.path.join(export_dir, f"{session_id}_{step_id}.json")

    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu file JSON tự động: {file_name}")
        return file_name
    except IOError:
        return None

# --- HÀM LƯU FILE TEXT THÔ TUẦN TỰ ---
def save_raw_text_to_file(raw_content: str, step_number: int):
    txt_export_dir = "txt_exports"
    if not os.path.exists(txt_export_dir):
        os.makedirs(txt_export_dir)

    file_name = f"analyst_text_{step_number:03d}.txt"
    full_path = os.path.join(txt_export_dir, file_name)

    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(raw_content)
        print(f"✅ Đã lưu file TXT thô tuần tự: {full_path}")
        return full_path
    except IOError:
        return None

# --- HÀM MỚI: GHI ĐÈ FILE input.txt ---
def save_current_input_txt(input_content: str):
    file_name = "input.txt"
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(input_content)
        print(f"✅ Đã ghi đè nội dung vào {file_name}")
        return file_name
    except IOError:
        return None

def read_file_content(file_data_base64):
    try:
        decoded_bytes = base64.b64decode(file_data_base64)
        content = decoded_bytes.decode('utf-8', errors='ignore')
        if not content.strip():
            return "Nội dung file không thể giải mã hoặc trống."
        return content
    except Exception:
        return "Nội dung file không thể giải mã hoặc trống."

def extract_markdown_from_text(text: str) -> str:
    """Trích xuất markdown từ text, loại bỏ code blocks nếu có"""
    if not text:
        return ""
    
    text = text.strip()
    
    # Nếu text bắt đầu bằng ```markdown và kết thúc bằng ```
    if text.startswith("```markdown") and text.endswith("```"):
        lines = text.split('\n')
        if len(lines) > 2:
            # Lấy nội dung giữa ```markdown và ```
            return '\n'.join(lines[1:-1]).strip()
    
    # Nếu text bắt đầu bằng ``` bất kỳ
    if text.startswith("```") and text.endswith("```"):
        lines = text.split('\n')
        if len(lines) > 2:
            return '\n'.join(lines[1:-1]).strip()
    
    return text

def build_dual_document_input(document_text: str) -> dict:
    """Xây dựng input cho agent từ document text"""
    doc_type = detect_document_type(document_text)
    
    if doc_type == 'both':
        split_result = split_combined_document(document_text)
        if split_result.get('has_both'):
            return {
                "srs_document": split_result['srs_text'],
                "user_stories_document": split_result['stories_text'],
            }
        return {
            "srs_document": document_text, 
            "user_stories_document": "No user stories found in the document."
        }
    elif doc_type == 'srs':
        return {
            "srs_document": document_text, 
            "user_stories_document": "No user stories provided."
        }
    elif doc_type == 'user_stories':
        return {
            "srs_document": "No SRS document provided.", 
            "user_stories_document": document_text
        }
    else:
        return {
            "srs_document": document_text, 
            "user_stories_document": "No user stories provided."
        }

async def run_agent_async(runner, user_id, adk_session_id, prompt):
    """Chạy agent async và thu thập response - XỬ LÝ FUNCTION_CALL"""
    user_message = types.Content(role="user", parts=[types.Part(text=prompt)])
    
    all_text_parts = []
    agent_executions = {}
    last_function_response = None
    
    print(f"🚀 Bắt đầu chạy agent...")
    
    async for event in runner.run_async(
        user_id=user_id, 
        session_id=adk_session_id, 
        new_message=user_message
    ):
        content = getattr(event, "content", None)
        if not content:
            continue
            
        parts = getattr(content, "parts", []) or []
        
        for part in parts:
            # 1. XỬ LÝ FUNCTION_CALL (sub-agent được gọi)
            fc = getattr(part, "function_call", None)
            if fc:
                agent_name = getattr(fc, "name", "unknown_agent")
                agent_executions[agent_name] = agent_executions.get(agent_name, 0) + 1
                print(f"  🔄 Executing: {agent_name} (lần {agent_executions[agent_name]})")
                continue
            
            # 2. XỬ LÝ FUNCTION_RESPONSE (kết quả từ sub-agent)
            fr = getattr(part, "function_response", None)
            if fr:
                response_name = getattr(fr, "name", None)
                if response_name:
                    print(f"  ✅ Completed: {response_name}")
                    last_function_response = fr
                continue
            
            # 3. XỬ LÝ TEXT RESPONSE (output cuối cùng)
            text_piece = getattr(part, "text", None)
            if text_piece:
                t = text_piece.strip()
                
                # Bỏ qua JSON responses
                if t.startswith("{") or t.startswith("["):
                    continue
                
                # Bỏ qua empty strings
                if not t:
                    continue
                
                # Trích xuất markdown nếu nằm trong code block
                t = extract_markdown_from_text(t)
                
                if t:
                    all_text_parts.append(t)
                    print(f"  📝 Nhận text response ({len(t)} chars)")
    
    # Log tổng kết
    if agent_executions:
        print(f"\n📊 Tổng kết sub-agents:")
        for agent_name, count in agent_executions.items():
            print(f"   • {agent_name}: {count} lần")
    
    # Ghép tất cả text parts
    final_report = "\n\n".join(all_text_parts).strip()
    
    if not final_report:
        print(f"⚠️ Không có text response. Kiểm tra function_response...")
        # Thử lấy từ function_response nếu có
        if last_function_response:
            response_data = getattr(last_function_response, "response", None)
            if response_data:
                # Nếu response là dict/object, thử lấy trường 'text' hoặc 'content'
                if hasattr(response_data, 'get'):
                    final_report = response_data.get('text') or response_data.get('content') or str(response_data)
                else:
                    final_report = str(response_data)
    
    if not final_report:
        final_report = "⚠️ Agent đã xử lý xong nhưng không trả về nội dung text.\n\nCó thể kết quả đang ở dạng structured data (JSON). Vui lòng kiểm tra logs hoặc thử lại."
    
    print(f"✅ Hoàn tất. Độ dài report: {len(final_report)} chars\n")
    
    return final_report

def get_or_create_session_id():
    """Lấy hoặc tạo mới session ID cho user"""
    if 'user_session_id' not in session:
        session['user_session_id'] = f"web_session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
    return session['user_session_id']

def get_or_create_runner(user_session_id):
    """Lấy hoặc tạo mới Runner cho session"""
    if user_session_id not in active_runners:
        # Tạo ADK session ID
        adk_session_id = f"adk_{user_session_id}"
        
        # Tạo session trong session service
        try:
            asyncio.run(session_service.create_session(
                app_name=APP_NAME,
                user_id=user_session_id,
                session_id=adk_session_id
            ))
        except Exception as e:
            print(f"⚠️ Lỗi khi tạo session: {e}")
        
        # Tạo runner
        runner = Runner(
            agent=root_agent,
            app_name=APP_NAME,
            session_service=session_service
        )
        
        active_runners[user_session_id] = {
            'runner': runner,
            'adk_session_id': adk_session_id,
            'created_at': datetime.datetime.now()
        }
        
        print(f"✅ Tạo Runner mới cho session: {user_session_id}")
    
    return active_runners[user_session_id]

@app.route('/api/process_prompt', methods=['POST'])
def process_prompt():
    global message_count

    message_count += 1
    current_step_id = f"analyst_{message_count:03d}"

    data = request.get_json()
    user_prompt = data.get('prompt')
    file_data_base64 = data.get('file_data')
    is_query = data.get('is_query', False)  # Đánh dấu có phải là query không

    # Lấy hoặc tạo session ID
    user_session_id = get_or_create_session_id()
    
    is_file_input = bool(file_data_base64)

    if is_file_input:
        input_content = read_file_content(file_data_base64)
    elif user_prompt:
        input_content = user_prompt
    else:
        return jsonify({"error": "Missing input (prompt or file data)"}), 400

    # Lưu file
    saved_raw_file_sequential = save_raw_text_to_file(input_content, message_count)
    saved_raw_file_current = save_current_input_txt(input_content)
    
    # Cập nhật status
    try:
        status_file = 'processing_status.json'
        status_data = {
            'status': 'processing',
            'timestamp': datetime.datetime.now().isoformat(),
            'output_file': 'output.txt'
        }
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)
    except:
        pass

    # *** SỬ DỤNG AGENT THỰC SỰ ***
    if agent_available:
        try:
            # Lấy hoặc tạo runner cho session này
            runner_info = get_or_create_runner(user_session_id)
            runner = runner_info['runner']
            adk_session_id = runner_info['adk_session_id']
            
            # Xây dựng prompt dựa trên loại request
            if is_query:
                # Nếu là query, thêm context hint cho Agent
                has_previous_analysis = user_session_id in session_data and 'last_analysis' in session_data[user_session_id]
                
                if has_previous_analysis:
                    last_analysis_time = session_data[user_session_id]['last_analysis']['timestamp']
                    prompt = f"""You have just completed a requirements engineering analysis in this session at {last_analysis_time}.

The user is now asking a follow-up question about the analysis results:

USER QUESTION: {user_prompt}

IMPORTANT:
- Use the analysis results from the previous interaction in THIS SESSION
- DO NOT ask for the document again
- Answer directly based on the findings, conflicts, gaps, and recommendations you identified
- Be specific and reference the actual findings from your analysis

If you cannot answer from the previous analysis, explain why."""
                    print(f"📋 Query mode WITH CONTEXT: {user_prompt[:100]}...")
                else:
                    prompt = f"""The user is asking: {user_prompt}

However, there is no previous analysis in this session. Please inform the user that they need to provide a document (SRS + User Stories) first before asking questions about the analysis."""
                    print(f"📋 Query mode WITHOUT CONTEXT: {user_prompt[:100]}...")
            else:
                # Nếu là phân tích, build prompt đầy đủ
                input_data = build_dual_document_input(input_content)
                
                prompt = f"""You are a Requirements Engineering pipeline. Perform the complete workflow below.
LANGUAGE LOCK: Use ENGLISH for all explanations and headings. Never translate or modify any quoted sentences from the original documents—preserve exact wording.

SRS DOCUMENT:
═══════════════════════════════════════════════════════════════════════════════
{input_data['srs_document']}
═══════════════════════════════════════════════════════════════════════════════

USER STORIES DOCUMENT:
═══════════════════════════════════════════════════════════════════════════════
{input_data['user_stories_document']}
═══════════════════════════════════════════════════════════════════════════════

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
                print(f"📋 Analysis mode: Processing {len(input_content)} chars")
            
            # Chạy agent
            final_report = asyncio.run(run_agent_async(
                runner, 
                user_session_id, 
                adk_session_id, 
                prompt
            ))
            
            # Lưu kết quả vào session data
            if not is_query:
                if user_session_id not in session_data:
                    session_data[user_session_id] = {}
                session_data[user_session_id]['last_analysis'] = {
                    'report': final_report,
                    'input_content': input_content,
                    'timestamp': datetime.datetime.now().isoformat()
                }
            
            # Lưu output
            try:
                with open('output.txt', 'w', encoding='utf-8') as f:
                    f.write(final_report)
                print(f"💾 Đã lưu output.txt ({len(final_report)} chars)")
            except Exception as e:
                print(f"⚠️ Lỗi khi lưu output.txt: {e}")
            
            # Cập nhật status completed
            try:
                status_data = {
                    'status': 'completed',
                    'timestamp': datetime.datetime.now().isoformat(),
                    'output_file': 'output.txt'
                }
                with open(status_file, 'w', encoding='utf-8') as f:
                    json.dump(status_data, f, indent=2)
            except:
                pass
            
            source_type = "tệp tin" if is_file_input else "câu lệnh"
            query_or_analysis = "truy vấn" if is_query else "phân tích"
            ai_response = f"✅ **{query_or_analysis.capitalize()} {source_type} (Bước {message_count}) hoàn tất!**\n\n{final_report}"
            
            return jsonify({
                "structured_json_saved": True,
                "ai_response_text": ai_response,
                "step_id": current_step_id,
                "session_id": user_session_id,
                "agent_processed": True
            })
            
        except Exception as e:
            print(f"❌ Lỗi khi chạy Agent: {e}")
            import traceback
            traceback.print_exc()
            
            # Cập nhật status failed
            try:
                status_data = {
                    'status': 'failed',
                    'timestamp': datetime.datetime.now().isoformat(),
                    'error': str(e)
                }
                with open('processing_status.json', 'w', encoding='utf-8') as f:
                    json.dump(status_data, f, indent=2)
            except:
                pass
            
            # Fallback về mock response
            ai_response = f"⚠️ **Lỗi khi xử lý bằng Agent:**\n\n```\n{str(e)}\n```\n\nVui lòng thử lại hoặc kiểm tra logs."
            return jsonify({
                "structured_json_saved": False,
                "ai_response_text": ai_response,
                "step_id": current_step_id,
                "session_id": user_session_id,
                "agent_processed": False
            })
    
    # Fallback nếu agent không available
    source_type = "tệp tin" if is_file_input else "câu lệnh"
    ai_response = (
        f"⚠️ **Agent không khả dụng (Bước {message_count})**\n\n"
        f"Nội dung đã được lưu nhưng không thể phân tích.\n"
        f"- **File Gốc Tuần Tự (.txt):** `{os.path.basename(saved_raw_file_sequential)}`\n"
        f"- **File Ghi Đè (input.txt):** `{saved_raw_file_current}`\n"
    )

    return jsonify({
        "structured_json_saved": False,
        "ai_response_text": ai_response,
        "step_id": current_step_id,
        "session_id": user_session_id,
        "agent_processed": False
    })

@app.route('/api/download_output', methods=['GET'])
def download_output():
    file_name = 'output.txt'
    if not os.path.exists(file_name):
        return jsonify({"success": False, "error": "Output file not found"}), 404
        
    try:
        return send_from_directory(
            directory=os.path.abspath(os.path.dirname(__file__)),
            path=file_name,
            as_attachment=True,
            mimetype='text/plain',
            download_name=file_name
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/check_status', methods=['GET'])
def check_status_api():
    try:
        status_file = 'processing_status.json'
        if os.path.exists(status_file):
            with open(status_file, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
    except:
        pass
    return jsonify({"status": "ready", "message": "Ready to accept input"})

@app.route('/api/get_output', methods=['GET'])
def get_output():
    try:
        with open('output.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"success": True, "content": content})
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Output file not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/new_session', methods=['POST'])
def new_session():
    """Tạo session mới và xóa session cũ"""
    old_session_id = session.get('user_session_id')
    
    # Xóa runner cũ nếu có
    if old_session_id and old_session_id in active_runners:
        del active_runners[old_session_id]
        if old_session_id in session_data:
            del session_data[old_session_id]
        print(f"🗑️ Đã xóa session cũ: {old_session_id}")
    
    # Clear session
    session.clear()
    
    # Tạo session mới
    new_session_id = get_or_create_session_id()
    print(f"🆕 Tạo session mới: {new_session_id}")
    
    return jsonify({
        "success": True,
        "session_id": new_session_id,
        "message": "New session created"
    })

@app.route('/api/has_context', methods=['GET'])
def has_context():
    """Kiểm tra xem session hiện tại có context analysis không"""
    user_session_id = session.get('user_session_id')
    
    if not user_session_id:
        return jsonify({"has_context": False, "message": "No active session"})
    
    has_analysis = (
        user_session_id in session_data and 
        'last_analysis' in session_data[user_session_id]
    )
    
    context_info = {}
    if has_analysis:
        context_info = {
            "timestamp": session_data[user_session_id]['last_analysis']['timestamp'],
            "report_length": len(session_data[user_session_id]['last_analysis']['report'])
        }
    
    return jsonify({
        "has_context": has_analysis,
        "session_id": user_session_id,
        "context_info": context_info if has_analysis else None
    })

if __name__ == '__main__':
    output_file = 'output.txt'
    try:
        if os.path.exists(output_file):
            os.remove(output_file)
            print(f"🧹 Đã xóa file cũ: {output_file}")
        else:
            print("✅ Không có file output.txt cũ để xóa.")
    except Exception as e:
        print(f"⚠️ Lỗi khi xóa file output.txt: {e}")

    print(f"\n{'='*70}")
    print(f"🚀 Flask Server đang khởi động...")
    print(f"📡 Agent available: {agent_available}")
    print(f"🔐 Session management: Enabled")
    print(f"{'='*70}\n")

    app.run(debug=True, port=5000, threaded=True)