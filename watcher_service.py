#!/usr/bin/env python3
"""
File Watcher Service - Tự động chạy run_agent.py khi input.txt thay đổi
Sử dụng watchdog để theo dõi thay đổi file và xử lý đa luồng
(ĐÃ SỬA: ép UTF-8 khi đọc stdout của subprocess để tránh UnicodeDecodeError cp1252)
"""

import os
import sys
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Ép UTF-8 cho stdout/stderr của chính process (in emoji & TV có dấu an toàn)
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

class InputFileHandler(FileSystemEventHandler):
    """Handler để theo dõi thay đổi của input.txt"""
    
    def __init__(self, input_file='input.txt', output_file='output.txt', cooldown=2.0):
        self.input_file = input_file
        self.output_file = output_file
        self.cooldown = cooldown
        self.last_processed = 0
        self.processing_lock = threading.Lock()
        self.is_processing = False
        
    def on_modified(self, event):
        if event.src_path.endswith(self.input_file):
            current_time = time.time()
            if current_time - self.last_processed < self.cooldown:
                return
            if self.is_processing:
                print(f"{Colors.YELLOW}[!] Dang xu ly file truoc do, bo qua thay doi moi{Colors.END}", flush=True)
                return
            self.last_processed = current_time
            threading.Thread(target=self._process_file, daemon=True).start()
    
    def on_created(self, event):
        if event.src_path.endswith(self.input_file):
            print(f"{Colors.GREEN}✓ Phát hiện file mới: {self.input_file}{Colors.END}", flush=True)
            time.sleep(0.5)
            threading.Thread(target=self._process_file, daemon=True).start()
    
    def _process_file(self):
        """Xử lý file input.txt bằng run_agent.py (đọc stdout UTF-8)"""
        with self.processing_lock:
            if self.is_processing:
                return
            self.is_processing = True
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
            print(f"{Colors.BOLD}{Colors.BLUE}  🚀 BẮT ĐẦU XỬ LÝ - {timestamp}{Colors.END}")
            print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n", flush=True)
            
            if not os.path.exists(self.input_file):
                print(f"{Colors.RED}✗ File {self.input_file} không tồn tại{Colors.END}", flush=True)
                return
            
            file_size = os.path.getsize(self.input_file)
            if file_size == 0:
                print(f"{Colors.YELLOW}⚠ File {self.input_file} rỗng, bỏ qua{Colors.END}", flush=True)
                return
            
            print(f"{Colors.CYAN}📄 File: {self.input_file} ({file_size} bytes){Colors.END}")
            print(f"{Colors.CYAN}📝 Output sẽ được lưu vào: {self.output_file}{Colors.END}\n", flush=True)
            
            print(f"{Colors.YELLOW}⏳ Đang chạy run_agent.py...{Colors.END}\n", flush=True)
            
            cmd = [
                sys.executable,
                'run_agent.py',
                '--input', self.input_file,
                '--output', self.output_file
            ]
            
            start_time = time.time()
            
            # *** FIX QUAN TRỌNG ***
            # - Ép môi trường PYTHONIOENCODING=utf-8 để child process ghi UTF-8
            # - Đặt encoding='utf-8', errors='replace' khi đọc stdout để tránh charmap decode CP1252
            child_env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'}
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=child_env,
                encoding='utf-8',
                errors='replace',
            )
            
            # Đọc output theo dòng (đã UTF-8 safe)
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end='', flush=True)
            
            process.wait()
            elapsed_time = time.time() - start_time
            
            if process.returncode == 0:
                print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
                print(f"{Colors.BOLD}{Colors.GREEN}  ✓ XỬ LÝ THÀNH CÔNG{Colors.END}")
                print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")
                print(f"{Colors.GREEN}⏱ Thời gian xử lý: {elapsed_time:.2f} giây{Colors.END}")
                print(f"{Colors.GREEN}📁 Kết quả đã lưu vào: {self.output_file}{Colors.END}\n", flush=True)
                self._notify_web_completion(success=True)
            else:
                print(f"\n{Colors.BOLD}{Colors.RED}{'='*70}{Colors.END}")
                print(f"{Colors.BOLD}{Colors.RED}  ✗ XỬ LÝ THẤT BẠI{Colors.END}")
                print(f"{Colors.BOLD}{Colors.RED}{'='*70}{Colors.END}\n")
                print(f"{Colors.RED}⏱ Thời gian: {elapsed_time:.2f} giây{Colors.END}")
                print(f"{Colors.RED}Exit code: {process.returncode}{Colors.END}\n", flush=True)
                self._notify_web_completion(success=False)
        
        except Exception as e:
            print(f"\n{Colors.RED}✗ LỖI KHI XỬ LÝ: {str(e)}{Colors.END}\n", flush=True)
            import traceback
            traceback.print_exc()
            self._notify_web_completion(success=False)
        
        finally:
            self.is_processing = False
    
    def _notify_web_completion(self, success: bool):
        try:
            status_file = 'processing_status.json'
            import json
            status_data = {
                'status': 'completed' if success else 'failed',
                'timestamp': datetime.now().isoformat(),
                'output_file': self.output_file if success else None
            }
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2)
            print(f"{Colors.CYAN}📊 Đã cập nhật trạng thái: {status_file}{Colors.END}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠ Không thể lưu trạng thái: {e}{Colors.END}")


def main():
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}  [*] FILE WATCHER SERVICE - Requirements Engineering{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}\n", flush=True)
    
    input_file = 'input.txt'
    output_file = 'output.txt'
    watch_directory = '.'
    
    print(f"{Colors.CYAN}[>>] Thu muc theo doi: {os.path.abspath(watch_directory)}{Colors.END}")
    print(f"{Colors.CYAN}[>>] File input: {input_file}{Colors.END}")
    print(f"{Colors.CYAN}[>>] File output: {output_file}{Colors.END}")
    print(f"{Colors.CYAN}[>>] Cooldown: 2 giay{Colors.END}\n", flush=True)
    
    if not os.path.exists('run_agent.py'):
        print(f"{Colors.RED}[X] CANH BAO: Khong tim thay run_agent.py{Colors.END}")
        print(f"{Colors.YELLOW}Dam bao file run_agent.py nam cung thu muc voi watcher_service.py{Colors.END}\n", flush=True)
    
    event_handler = InputFileHandler(
        input_file=input_file,
        output_file=output_file,
        cooldown=2.0
    )
    
    observer = Observer()
    observer.schedule(event_handler, watch_directory, recursive=False)
    observer.start()
    
    print(f"{Colors.GREEN}[OK] Service da khoi dong thanh cong!{Colors.END}")
    print(f"{Colors.YELLOW}[>>] Dang theo doi thay doi cua {input_file}...{Colors.END}")
    print(f"{Colors.CYAN}[!] Nhan Ctrl+C de dung service{Colors.END}\n")
    print(f"{Colors.BOLD}{'─'*70}{Colors.END}\n", flush=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}[!] Dang dung service...{Colors.END}")
        observer.stop()
        observer.join()
        print(f"{Colors.GREEN}[OK] Service da dung{Colors.END}\n", flush=True)


if __name__ == "__main__":
    try:
        import watchdog  # noqa: F401
    except ImportError:
        print(f"{Colors.RED}✗ Thiếu thư viện watchdog{Colors.END}")
        print(f"{Colors.CYAN}Cài đặt bằng: pip install watchdog{Colors.END}\n", flush=True)
        sys.exit(1)
    main()
