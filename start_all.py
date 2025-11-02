#!/usr/bin/env python3
"""
Threaded Startup Script - Chạy tất cả services trong một terminal với đa luồng
Mỗi service chạy trong thread riêng, logs được gộp chung (real-time, unbuffered, UTF-8)
"""

import threading
import subprocess
import sys
import time
import queue
import os
from datetime import datetime
from pathlib import Path

# Bật unbuffered + I/O UTF-8 cho chính process hiện tại
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ANSI Colors
class Colors:
    HEADER = '[95m'
    BLUE = '[94m'
    CYAN = '[96m'
    GREEN = '[92m'
    YELLOW = '[93m'
    RED = '[91m'
    BOLD = '[1m'
    END = '[0m'

class ServiceThread:
    """Thread wrapper cho mỗi service"""

    def __init__(self, name, command, color):
        self.name = name
        self.command = command
        self.color = color
        self.process = None
        self.thread = None
        self.running = False
        self.log_queue = queue.Queue()

    def start(self):
        """Khởi động service trong thread riêng"""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        """Chạy service và capture output (real-time, UTF-8 safe)"""
        try:
            print(f"{self.color}[{self.name}] Đang khởi động...{Colors.END}", flush=True)

            # Kế thừa env hiện tại + ép unbuffered + UTF-8 cho tiến trình con
            child_env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}

            # text=True + encoding='utf-8' + errors='replace' để tránh lỗi cp1252 decode
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=child_env,
                encoding="utf-8",
                errors="replace",
            )

            self.running = True
            print(f"{Colors.GREEN}[{self.name}] ✅ Đã khởi động (PID: {self.process.pid}){Colors.END}", flush=True)

            # Đọc output và in ra với prefix + flush ngay
            if self.process.stdout is not None:
                for line in self.process.stdout:
                    if not line:
                        continue
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(
                        f"{self.color}[{timestamp}][{self.name}]{Colors.END} {line.rstrip()}",
                        flush=True,
                    )

            self.process.wait()
            self.running = False

            if self.process.returncode != 0:
                print(f"{Colors.RED}[{self.name}] ❌ Đã dừng với mã lỗi: {self.process.returncode}{Colors.END}", flush=True)
            else:
                print(f"{Colors.YELLOW}[{self.name}] ⚠️  Đã dừng{Colors.END}", flush=True)

        except Exception as e:
            self.running = False
            print(f"{Colors.RED}[{self.name}] ❌ Lỗi: {str(e)}{Colors.END}", flush=True)

    def stop(self):
        """Dừng service"""
        if self.process and self.running:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()

class ServiceManager:
    """Quản lý tất cả services"""

    def __init__(self):
        self.services = []
        self.running = False

    def add_service(self, name, command, color):
        """Thêm service vào danh sách"""
        service = ServiceThread(name, command, color)
        self.services.append(service)
        return service

    def start_all(self):
        """Khởi động tất cả services"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}  🚀 KHỞI ĐỘNG TẤT CẢ SERVICES (MULTI-THREADED){Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n", flush=True)

        self.running = True

        for i, service in enumerate(self.services, 1):
            print(f"{Colors.YELLOW}[{i}/{len(self.services)}] Khởi động {service.name}...{Colors.END}", flush=True)
            service.start()
            time.sleep(1.0)

        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}  ✅ TẤT CẢ SERVICES ĐÃ ĐƯỢC KHỞI ĐỘNG{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n", flush=True)

        self._print_info()

    def _print_info(self):
        """In thông tin sử dụng"""
        print(f"{Colors.CYAN}📍 THÔNG TIN TRUY CẬP:{Colors.END}")
        print(f"   🌐 Web Interface: {Colors.BOLD}http://localhost:8000{Colors.END}")
        print(f"   🔌 Flask API: {Colors.BOLD}http://localhost:5000{Colors.END}\n")

        print(f"{Colors.CYAN}📊 SERVICES ĐANG CHẠY:{Colors.END}")
        for service in self.services:
            status = f"{Colors.GREEN}🟢 RUNNING{Colors.END}" if service.running else f"{Colors.RED}🔴 STOPPED{Colors.END}"
            print(f"   • {service.name}: {status}")

        print(f"\n{Colors.YELLOW}💡 LOGS:{Colors.END}")
        print(f"   • Tất cả logs được hiển thị trong terminal này")
        print(f"   • Mỗi dòng có prefix [Service Name] để phân biệt")
        print(f"   • Logs theo thời gian thực (real-time)\n")

        print(f"{Colors.YELLOW}⚠️  ĐỂ DỪNG HỆ THỐNG:{Colors.END}")
        print(f"   • Nhấn {Colors.BOLD}Ctrl+C{Colors.END} để dừng tất cả services")
        print(f"   • Services sẽ được dọn dẹp tự động\n")

        print(f"{Colors.BOLD}{Colors.CYAN}{'─'*70}{Colors.END}\n")
        print(f"{Colors.BOLD}📝 LOGS BẮT ĐẦU TỪ ĐÂY:{Colors.END}\n")
        print(f"{Colors.CYAN}{'─'*70}{Colors.END}\n", flush=True)

    def stop_all(self):
        """Dừng tất cả services"""
        print(f"\n\n{Colors.YELLOW}{'='*70}{Colors.END}")
        print(f"{Colors.YELLOW}⚠️  ĐANG DỪNG TẤT CẢ SERVICES...{Colors.END}")
        print(f"{Colors.YELLOW}{'='*70}{Colors.END}\n", flush=True)

        self.running = False

        for service in self.services:
            if service.running:
                print(f"{Colors.YELLOW}[STOP] {service.name}...{Colors.END}", flush=True)
                service.stop()
                time.sleep(0.3)

        print(f"\n{Colors.GREEN}✅ Tất cả services đã được dừng{Colors.END}\n", flush=True)

    def wait_for_services(self):
        """Đợi cho đến khi user dừng (Ctrl+C)"""
        try:
            while self.running:
                active = sum(1 for s in self.services if s.running)
                if active == 0:
                    print(f"\n{Colors.RED}⚠️  Tất cả services đã dừng{Colors.END}", flush=True)
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}🛑 Nhận tín hiệu dừng (Ctrl+C){Colors.END}", flush=True)


def check_dependencies():
    """Kiểm tra dependencies"""
    print(f"{Colors.CYAN}🔍 Kiểm tra dependencies...{Colors.END}\n", flush=True)

    required_modules = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
        'watchdog': 'Watchdog'
    }

    missing = []

    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
            print(f"{Colors.GREEN}✅ {package_name}{Colors.END}", flush=True)
        except ImportError:
            print(f"{Colors.RED}❌ {package_name} - CHƯA CÀI ĐẶT{Colors.END}", flush=True)
            missing.append(package_name)

    if missing:
        print(f"\n{Colors.YELLOW}⚠️  Cài đặt dependencies bị thiếu:{Colors.END}")
        pip_line = ' '.join([pkg.lower().replace('-cors', '_cors') for pkg in missing])
        print(f"{Colors.CYAN}pip install {pip_line}{Colors.END}\n", flush=True)
        return False

    print()
    return True


def check_files():
    """Kiểm tra files cần thiết"""
    print(f"{Colors.CYAN}📁 Kiểm tra files...{Colors.END}\n", flush=True)

    required_files = {
        'app.py': 'Flask Backend',
        'watcher_service.py': 'File Watcher',
        'index.html': 'Web Interface'
    }

    for filename, description in required_files.items():
        if not Path(filename).exists():
            print(f"{Colors.RED}❌ {description} ({filename}) - KHÔNG TỒN TẠI{Colors.END}", flush=True)
            return False
        print(f"{Colors.GREEN}✅ {description} ({filename}){Colors.END}", flush=True)

    print()
    return True


def check_ports():
    """Kiểm tra ports có bị chiếm không"""
    print(f"{Colors.CYAN}🔌 Kiểm tra ports...{Colors.END}\n", flush=True)

    import socket

    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    ports = {
        5000: 'Flask Backend',
        8000: 'Web Server'
    }

    all_clear = True

    for port, service in ports.items():
        if is_port_in_use(port):
            print(f"{Colors.YELLOW}⚠️  Port {port} ({service}) - ĐANG ĐƯỢC SỬ DỤNG{Colors.END}", flush=True)
            all_clear = False
        else:
            print(f"{Colors.GREEN}✅ Port {port} ({service}) - SẴN SÀNG{Colors.END}", flush=True)

    print()
    return all_clear


def main():
    """Main function"""
    # Set UTF-8 encoding cho stdout trên Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}  [*] HE THONG DA LUONG - Requirements Engineering{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}\n", flush=True)

    # Kiểm tra
    if not check_dependencies():
        sys.exit(1)

    if not check_files():
        sys.exit(1)

    ports_clear = check_ports()
    if not ports_clear:
        print(f"{Colors.YELLOW}⚠️  Một số ports đang được sử dụng{Colors.END}")
        try:
            response = input(f"{Colors.CYAN}Tiếp tục? (y/n): {Colors.END}").lower()
        except EOFError:
            response = 'n'
        if response != 'y':
            print(f"{Colors.RED}Đã hủy{Colors.END}\n", flush=True)
            sys.exit(1)
        print()

    # Tạo Service Manager
    manager = ServiceManager()

    # Thêm các services với màu sắc khác nhau
    python_cmd = sys.executable

    # Thêm -u để ép unbuffered cho script Python
    manager.add_service(
        "FLASK",
        f'"{python_cmd}" -u app.py',
        Colors.BLUE
    )

    manager.add_service(
        "WATCHER",
        f'"{python_cmd}" -u watcher_service.py',
        Colors.CYAN
    )

    manager.add_service(
        "WEB",
        f'"{python_cmd}" -m http.server 8000',
        Colors.GREEN
    )

    try:
        # Khởi động tất cả
        manager.start_all()

        # Đợi cho đến khi user muốn dừng
        manager.wait_for_services()

    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()
