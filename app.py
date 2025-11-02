from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import datetime
import os
import random
import base64
import time
import sys
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
# --------------------------------------------------------------------------

# --- Khởi tạo LLM Client và Biến Toàn Cục ---
load_dotenv() 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 

try:
    from google import genai
    from google.genai import types
    if GOOGLE_API_KEY:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    else:
        client = None
except ImportError:
    client = None
except Exception:
    client = None
    
# BIẾN TOÀN CỤC ĐỂ ĐÁNH SỐ THỨ TỰ
message_count = 0
session_start_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
# ----------------------------------------

app = Flask(__name__)
CORS(app) 

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

# --- HÀM KIỂM TRA TRẠNG THÁI XỬ LÝ ---
def check_processing_status():
    status_file = 'processing_status.json'
    try:
        if os.path.exists(status_file):
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return None

def wait_for_output(timeout=120, check_interval=2):
    output_file = 'output.txt'
    start_time = time.time()

    while time.time() - start_time < timeout:
        status = check_processing_status()
        if status:
            if status.get('status') == 'completed':
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        return f.read(), True
                except:
                    pass
            elif status.get('status') == 'failed':
                return None, False
        time.sleep(check_interval)
    return None, False

def read_file_content(file_data_base64):
    try:
        decoded_bytes = base64.b64decode(file_data_base64)
        content = decoded_bytes.decode('utf-8', errors='ignore')
        if not content.strip():
            return "Nội dung file không thể giải mã hoặc trống."
        if len(content) < 50:
            content = f"Nội dung được trích xuất từ file upload. {content * 3}"
        return content
    except Exception:
        return "Nội dung file không thể giải mã hoặc trống."

def extract_structured_data(input_content: str, is_file: bool, step_id: str, session_id: str):
    srs_parts = []
    user_stories_parts = []
    if "mật khẩu" in input_content.lower() or "password" in input_content.lower():
        srs_parts.append("- Passwords MUST be at least 8 characters long (Detected by AI).")
    if "quản lý" in input_content.lower() or "manage" in input_content.lower():
        user_stories_parts.append(
            f"US-00{random.randint(1, 9)}: Management Feature\nAs a Manager, I want to manage projects.\nPriority: MUST"
        )
    if is_file:
        srs_parts.append("- Requirement extracted from uploaded File.")

    srs_text = "3.1 Requirements:\n" + "\n".join(srs_parts)
    user_stories_text = "US-001:\n" + "\n".join(user_stories_parts)

    return {
        "srs_text": srs_text if srs_parts else "No specific SRS requirements found.",
        "user_stories_text": user_stories_text if user_stories_parts else "No specific User Stories found.",
        "user_id": step_id, 
        "session_id": session_id
    }

@app.route('/api/process_prompt', methods=['POST'])
def process_prompt():
    global message_count, session_start_time

    message_count += 1
    current_step_id = f"analyst_{message_count:03d}"
    current_session_id = f"analysis_session_{session_start_time}"

    data = request.get_json()
    user_prompt = data.get('prompt')
    file_data_base64 = data.get('file_data')
    # use_agent = data.get('use_agent', False) # Bỏ qua biến này

    is_file_input = bool(file_data_base64)

    if is_file_input:
        input_content = read_file_content(file_data_base64)
    elif user_prompt:
        input_content = user_prompt
    else:
        return jsonify({"error": "Missing input (prompt or file data)"}), 400

    saved_raw_file_sequential = save_raw_text_to_file(input_content, message_count)
    saved_raw_file_current = save_current_input_txt(input_content)
    
    # *** CẬP NHẬT: MÔ PHỎNG LUỒNG AGENT XỬ LÝ ***
    
    # 1. Cập nhật status file thành "processing" (để script.js nhận biết)
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

    # 2. Tạo dữ liệu đầu ra và lưu trữ (Giả lập Agent)
    structured_data = extract_structured_data(
        input_content, 
        is_file_input, 
        current_step_id, 
        current_session_id
    )
    saved_json_file = save_structured_data_to_file(structured_data)
    
    # 3. Ghi đè file output.txt để có nội dung mẫu cho việc tải xuống
    output_content_for_download = (
        f"*** BÁO CÁO PHÂN TÍCH YÊU CẦU (BƯỚC {message_count}) ***\n\n"
        f"1. Yêu cầu Hệ thống (SRS):\n{structured_data['srs_text']}\n\n"
        f"2. User Stories:\n{structured_data['user_stories_text']}\n\n"
        f"3. Nguồn: {'File đã tải' if is_file_input else 'Lời nhắc từ người dùng'}\n"
        f"4. File Gốc Tuần Tự: {os.path.basename(saved_raw_file_sequential)}\n"
    )
    
    try:
        with open('output.txt', 'w', encoding='utf-8') as f:
            f.write(output_content_for_download)
    except:
        pass

    # 4. Cập nhật status file thành "completed" (Hoàn tất giả lập)
    try:
        status_file = 'processing_status.json'
        status_data = {
            'status': 'completed',
            'timestamp': datetime.datetime.now().isoformat(),
            'output_file': 'output.txt'
        }
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)
    except:
        pass

    # 5. Tạo phản hồi cho Frontend
    source_type = "tệp tin" if is_file_input else "câu lệnh"
    ai_response = (
        f"✅ **Phân tích {source_type} (Bước {message_count}) hoàn tất!**\n\n"
        f"Tôi đã đọc nội dung, xử lý và lưu trữ thành công.\n"
        f"Thông tin đã lưu trên Server:\n"
        f"- **File Gốc Tuần Tự (.txt):** `{os.path.basename(saved_raw_file_sequential)}`\n"
        f"- **File Ghi Đè (input.txt):** `{saved_raw_file_current}`\n"
        f"- **File Cấu Trúc (JSON):** `{os.path.basename(saved_json_file)}`\n"
        f"- **Báo cáo phân tích:** Đã tạo nội dung mẫu trong `output.txt`."
    )
    # --- KẾT THÚC MÔ PHỎNG LUỒNG AGENT ---


    return jsonify({
        "structured_json_saved": True,
        "ai_response_text": ai_response,
        "step_id": current_step_id,
        "session_id": current_session_id,
        "agent_processed": True
    })

# *** API MỚI: Tải file output.txt ***
@app.route('/api/download_output', methods=['GET'])
def download_output():
    file_name = 'output.txt'
    if not os.path.exists(file_name):
        return jsonify({"success": False, "error": "Output file not found"}), 404
        
    try:
        # Sử dụng send_from_directory để gửi file từ thư mục hiện tại
        # os.path.abspath(os.path.dirname(__file__)) là thư mục gốc của app.py
        return send_from_directory(
            directory=os.path.abspath(os.path.dirname(__file__)),
            path=file_name,
            as_attachment=True,
            mimetype='text/plain',
            download_name=file_name
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# *** API MỚI: Kiểm tra trạng thái Agent ***
@app.route('/api/check_status', methods=['GET'])
def check_status_api():
    status = check_processing_status()
    if status:
        return jsonify(status)
        
    # Nếu không tìm thấy file status, trả về trạng thái sẵn sàng
    return jsonify({"status": "ready", "message": "Ready to accept input"})

# Các route hiện có (get_output) được giữ nguyên nhưng không dùng trong luồng mới

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

@app.route('/api/check_status', methods=['GET'])
def check_status():
    status = check_processing_status()
    if status:
        return jsonify(status)
    return jsonify({"status": "unknown", "message": "No processing status available"})


if __name__ == '__main__':
    app.run(debug=True, port=5000)