import tkinter as tk
from tkinter import messagebox
import subprocess
import socket
import threading
import sys
import os
try:
    import psutil
except Exception:
    psutil = None

class WebAppLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Web App 启动器")
        self.root.geometry("520x360")
        self.root.resizable(False, False)
        
        self.process = None
        self.port = 8001
        self.is_running = False
        self.stopping_by_user = False
        
        # 状态显示
        self.status_label = tk.Label(root, text="状态: 未运行", fg="red", font=("Arial", 12))
        self.status_label.pack(pady=10)
        
        # 按钮区域
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=10)
        
        self.start_btn = tk.Button(self.btn_frame, text="启动服务", command=self.start_server, 
                                 width=15, height=2, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = tk.Button(self.btn_frame, text="停止服务", command=self.stop_server, 
                                state=tk.DISABLED, width=15, height=2, bg="#f44336", fg="white", font=("Arial", 10, "bold"))
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # 信息显示区域
        self.info_frame = tk.LabelFrame(root, text="访问地址", padx=10, pady=10)
        self.info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.local_url_var = tk.StringVar(value="-")
        self.lan_url_var = tk.StringVar(value="-")

        local_row = tk.Frame(self.info_frame)
        local_row.pack(fill=tk.X, pady=4)
        tk.Label(local_row, text="本机访问", width=10, anchor="w").pack(side=tk.LEFT)
        self.local_entry = tk.Entry(local_row, textvariable=self.local_url_var, state="readonly")
        self.local_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        tk.Button(local_row, text="复制", width=6, command=lambda: self.copy_url(self.local_url_var.get())).pack(side=tk.RIGHT)

        lan_row = tk.Frame(self.info_frame)
        lan_row.pack(fill=tk.X, pady=4)
        tk.Label(lan_row, text="手机访问", width=10, anchor="w").pack(side=tk.LEFT)
        self.lan_entry = tk.Entry(lan_row, textvariable=self.lan_url_var, state="readonly")
        self.lan_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        tk.Button(lan_row, text="复制", width=6, command=lambda: self.copy_url(self.lan_url_var.get())).pack(side=tk.RIGHT)
        
        self.tip_label = tk.Label(self.info_frame, text="请确保手机和电脑在同一局域网", fg="gray", font=("Arial", 9))
        self.tip_label.pack(fill=tk.X, pady=(10, 0))

        # 检查是否已有服务在运行
        self.check_existing_process()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def get_lan_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def check_existing_process(self):
        # 简单检查端口占用
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', self.port))
        sock.close()
        if result == 0:
            self.status_label.config(text=f"状态: 端口 {self.port} 已被占用", fg="orange")
            # 这里不自动接管，因为不知道是不是我们的服务，只提示
    
    def start_server(self):
        if self.is_running:
            return
            
        self.start_btn.config(state=tk.DISABLED, bg="#a5d6a7")
        self.status_label.config(text="状态: 启动中...", fg="orange")
        
        # 在新线程启动，避免卡死UI
        threading.Thread(target=self._run_uvicorn, daemon=True).start()

    def _run_uvicorn(self):
        cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", str(self.port)]
        
        try:
            # 创建不显示窗口的启动信息
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, # 不显示黑框
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            self.is_running = True
            self.root.after(0, self._update_ui_running)
            
            # 监控进程输出（可选，这里简化处理，只监控结束）
            self.process.wait()
            
            if self.stopping_by_user:
                self.stopping_by_user = False
                return

            if self.is_running: 
                err_msg = ""
                try:
                    _, stderr_text = self.process.communicate(timeout=0.2)
                    if stderr_text:
                        err_msg = stderr_text.strip()[:300]
                except Exception:
                    pass
                self.is_running = False
                self.root.after(0, self._update_ui_stopped)
                if err_msg:
                    self.root.after(0, lambda: messagebox.showerror("启动失败", f"服务异常退出：\n{err_msg}"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("启动失败", str(e)))
            self.is_running = False
            self.root.after(0, self._update_ui_stopped)

    def _update_ui_running(self):
        self.status_label.config(text="状态: 运行中", fg="green")
        self.stop_btn.config(state=tk.NORMAL, bg="#f44336")
        
        lan_ip = self.get_lan_ip()
        self.local_url_var.set(f"http://127.0.0.1:{self.port}/")
        self.lan_url_var.set(f"http://{lan_ip}:{self.port}/")

    def _update_ui_stopped(self):
        self.status_label.config(text="状态: 未运行", fg="red")
        self.start_btn.config(state=tk.NORMAL, bg="#4CAF50")
        self.stop_btn.config(state=tk.DISABLED, bg="#ef9a9a")
        self.local_url_var.set("-")
        self.lan_url_var.set("-")

    def copy_url(self, value):
        if not value or value == "-":
            messagebox.showinfo("复制地址", "当前没有可复制地址。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.status_label.config(text="状态: 地址已复制到剪贴板", fg="#1976d2")

    def stop_server(self):
        if not self.process:
            return
            
        self.status_label.config(text="状态: 正在停止...", fg="orange")
        self.stop_btn.config(state=tk.DISABLED)
        self.stopping_by_user = True
        
        try:
            if psutil is not None:
                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                parent.terminate()
                self.process.wait(timeout=3)
            else:
                self.process.terminate()
                self.process.wait(timeout=3)
        except:
            pass
            
        self.is_running = False
        self._update_ui_stopped()
        self.process = None

    def on_close(self):
        if self.is_running:
            if messagebox.askokcancel("退出", "服务正在运行，确定要停止并退出吗？"):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WebAppLauncher(root)
    root.mainloop()
