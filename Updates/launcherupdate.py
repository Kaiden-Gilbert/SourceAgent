import os, sys, subprocess, threading, time, venv, urllib.request, json
import tkinter as tk
from tkinter import ttk

# --- BOOTLOADER CONFIGURATION ---
LAUNCHER_VERSION = 2.1  
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
ENV_FILE = os.path.join(BASE_DIR, ".env")
APP_FILE = os.path.join(BASE_DIR, "app.py")
VERSION_FILE = os.path.join(BASE_DIR, "latest_version.txt")

def get_venv_python(): 
    return os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(VENV_DIR, "bin", "python")

class LauncherUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SourceAgent Bootloader v{LAUNCHER_VERSION}")
        self.root.geometry("520x550")
        self.root.configure(bg="#0b0b12")
        
        ttk.Style().theme_use('clam')
        ttk.Style().configure("TProgressbar", thickness=10, background="#6366f1", troughcolor="#161622", bordercolor="#0b0b12")

        self.main_frame = tk.Frame(root, bg="#0b0b12", padx=30, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.main_frame, text="SourceAgent Pro", font=("Segoe UI", 24, "bold"), bg="#0b0b12", fg="#ffffff").pack(pady=(0, 5))
        self.status = tk.Label(self.main_frame, text="Synchronizing with Cloud...", font=("Segoe UI", 10, "italic"), bg="#0b0b12", fg="#f8fafc")
        self.status.pack()

        self.content_frame = tk.Frame(self.main_frame, bg="#0b0b12")
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        threading.Thread(target=self.run_dual_sync, daemon=True).start()

    def run_dual_sync(self):
        try:
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + "version.json", headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            
            cloud_app_v = float(data.get("app_version", 0.0))
            cloud_launcher_v = float(data.get("launcher_version", LAUNCHER_VERSION))
            local_app_v = float(open(VERSION_FILE, "r").read()) if os.path.exists(VERSION_FILE) else 0.0

            if cloud_launcher_v > LAUNCHER_VERSION:
                self.root.after(0, lambda: self.prompt_update("Launcher", cloud_launcher_v, True))
            elif cloud_app_v > local_app_v:
                self.root.after(0, lambda: self.prompt_update("Application", cloud_app_v, False))
            else:
                self.root.after(0, self.run_local_diagnostics)
        except: self.root.after(0, self.run_local_diagnostics)

    def prompt_update(self, name, ver, is_l):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        tk.Label(self.content_frame, text=f"{name} Update v{ver} Found!", font=("Segoe UI", 12, "bold"), bg="#0b0b12", fg="#2ecc71").pack(pady=20)
        
        btn = tk.Button(self.content_frame, text="Sync Now", bg="#6366f1", fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=20, pady=10, 
                         command=lambda: self.start_download(is_l, ver))
        btn.pack(pady=10)
        tk.Button(self.content_frame, text="Skip", bg="#333333", fg="white", relief="flat", command=self.run_local_diagnostics).pack()

    def start_download(self, is_l, ver):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        self.pb = ttk.Progressbar(self.content_frame, length=300, mode='determinate'); self.pb.pack(pady=30)
        threading.Thread(target=self.downloader, args=(is_l, ver), daemon=True).start()

    def downloader(self, is_l, ver):
        try:
            file_name = "launcherupdate.py" if is_l else "appupdate.py"
            local_name = __file__ if is_l else APP_FILE
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + file_name, headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req) as resp:
                with open(local_name, "wb") as f: f.write(resp.read())
            
            if not is_l: open(VERSION_FILE, "w").write(str(ver))
            
            if is_l:
                subprocess.Popen([sys.executable, __file__])
                self.root.after(0, self.root.destroy)
            else:
                self.root.after(0, self.run_local_diagnostics)
        except: pass

    def run_local_diagnostics(self):
        if not os.path.exists(VENV_DIR): venv.create(VENV_DIR, with_pip=True)
        py = get_venv_python()
        if os.path.exists(os.path.join(BASE_DIR, "requirements.txt")):
            subprocess.check_call([py, "-m", "pip", "install", "-r", os.path.join(BASE_DIR, "requirements.txt"), "--quiet"])
        subprocess.Popen([py, APP_FILE])
        self.root.after(0, self.root.destroy)

if __name__ == "__main__":
    root = tk.Tk(); LauncherUI(root); root.mainloop()
