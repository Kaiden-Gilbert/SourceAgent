import os, sys, subprocess, threading, time, venv, webbrowser
import tkinter as tk
from tkinter import ttk

# --- ABSOLUTE PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
ENV_FILE = os.path.join(BASE_DIR, ".env")
APP_FILE = os.path.join(BASE_DIR, "app.py")
VERSION_FILE = os.path.join(BASE_DIR, "latest_version.txt")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")

# --- MASTER REQUIREMENTS LIST (AUDIO REMOVED) ---
REQUIREMENTS = [
    "langchain", 
    "langchain-openai",         
    "langchain-community", 
    "langchain-huggingface",    
    "sentence-transformers",    
    "langchain-text-splitters", 
    "python-dotenv",            
    "customtkinter",            
    "pymupdf",                  
    "docx2txt",                 
    "faiss-cpu"
]

def get_venv_python():
    return os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(VENV_DIR, "bin", "python")

class LauncherUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SourceAgent Pro v3.0 Bootloader")
        self.root.geometry("520x500")
        self.root.configure(bg="#1e1e1e") 
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=10, background="#2ecc71", troughcolor="#2b2b2b", bordercolor="#1e1e1e")

        self.main_frame = tk.Frame(root, bg="#1e1e1e", padx=30, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.main_frame, text="SourceAgent Pro v3.0", font=("Segoe UI", 22, "bold"), bg="#1e1e1e", fg="#ffffff").pack(pady=(0, 5))
        tk.Label(self.main_frame, text="Multi-Agent Diagnostics & Initialization", font=("Segoe UI", 12), bg="#1e1e1e", fg="#aaaaaa").pack(pady=(0, 15))
        
        # --- PRE-FLIGHT CHECKLIST UI ---
        self.diagnostic_frame = tk.Frame(self.main_frame, bg="#2b2b2b", padx=15, pady=15)
        self.diagnostic_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.api_status_lbl = tk.Label(self.diagnostic_frame, text="API Key: Checking...", font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#dddddd", anchor="w")
        self.api_status_lbl.pack(fill=tk.X, pady=2)
        
        self.db_status_lbl = tk.Label(self.diagnostic_frame, text="Chat Database: Checking...", font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#dddddd", anchor="w")
        self.db_status_lbl.pack(fill=tk.X, pady=2)
        
        self.ota_status_lbl = tk.Label(self.diagnostic_frame, text="OTA Updates: Checking...", font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#dddddd", anchor="w")
        self.ota_status_lbl.pack(fill=tk.X, pady=2)
        # -------------------------------

        self.status = tk.Label(self.main_frame, text="Awaiting sequence...", font=("Segoe UI", 10, "italic"), bg="#1e1e1e", fg="#dddddd")
        self.status.pack()

        self.percent_label = tk.Label(self.main_frame, text="", font=("Segoe UI", 36, "bold"), bg="#1e1e1e", fg="#2ecc71")
        self.percent_label.pack(pady=10)

        self.content_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        self.run_diagnostics()

    def run_diagnostics(self):
        api_ready = self.has_openrouter_key()
        db_ready = os.path.exists(HISTORY_DIR)
        
        if not os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, "w") as f:
                    f.write("3.0")
            except Exception as e:
                print(f"Failed to create version file: {e}")

        if api_ready:
            self.api_status_lbl.config(text="✅ API Key: Detected", fg="#2ecc71")
        else:
            self.api_status_lbl.config(text="❌ API Key: Missing", fg="#e74c3c")

        if db_ready:
            self.db_status_lbl.config(text="✅ Database: 'chat_storage' Active", fg="#2ecc71")
        else:
            self.db_status_lbl.config(text="⚠️ Database: Will be created on boot", fg="#f39c12")
            
        if os.path.exists(VERSION_FILE):
            self.ota_status_lbl.config(text="✅ OTA Updates: Scanner Armed", fg="#2ecc71")
        else:
            self.ota_status_lbl.config(text="❌ OTA Updates: Scanner Offline", fg="#e74c3c")

        if not api_ready:
            self.show_api_screen()
        else:
            self.percent_label.config(text="0%")
            self.show_install_screen()

    def has_openrouter_key(self):
        if not os.path.exists(ENV_FILE):
            return False
        try:
            with open(ENV_FILE, "r") as f:
                content = f.read()
                if "OPENROUTER_API_KEY=" in content:
                    return True
        except Exception:
            pass
        return False

    def show_api_screen(self):
        self.status.config(text="Action Required")
        tk.Label(self.content_frame, text="Enter your OpenRouter API Key:", font=("Segoe UI", 11), bg="#1e1e1e", fg="#ffffff").pack(pady=10)
        self.entry = tk.Entry(self.content_frame, width=45, show="*", font=("Segoe UI", 12), bg="#2b2b2b", fg="#ffffff", insertbackground="white", relief="flat")
        self.entry.pack(pady=10, ipady=5)
        tk.Button(self.content_frame, text="Save & Initialize", command=self.save_key, bg="#2ecc71", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=10, pady=15).pack(pady=15)

    def save_key(self):
        key = self.entry.get().strip()
        if key:
            with open(ENV_FILE, "a") as f:
                f.write(f"\nOPENROUTER_API_KEY={key}\n")
            for widget in self.content_frame.winfo_children(): widget.destroy()
            self.run_diagnostics() 

    def show_install_screen(self):
        self.status.config(text="Verifying Virtual Environment...")
        self.progress = ttk.Progressbar(self.content_frame, length=350, mode='determinate')
        self.progress.pack(pady=20)
        threading.Thread(target=self.run_setup, daemon=True).start()

    def update_ui(self, text, value):
        self.status.config(text=text)
        self.progress['value'] = value
        self.percent_label.config(text=f"{int(value)}%")

    def run_setup(self):
        try:
            if not os.path.exists(VENV_DIR):
                venv.create(VENV_DIR, with_pip=True)
            
            py = get_venv_python()
            
            self.root.after(0, self.update_ui, "Updating Core Build Tools...", 5)
            subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "--quiet"])
            
            total_libs = len(REQUIREMENTS)
            for i, lib in enumerate(REQUIREMENTS):
                progress_val = 10 + (i / total_libs) * 85
                self.root.after(0, self.update_ui, f"Installing {lib}...", progress_val)
                subprocess.check_call([py, "-m", "pip", "install", f"{lib}", "--quiet"])
            
            self.root.after(0, self.update_ui, "System Ready!", 100)
            time.sleep(0.8)
            subprocess.Popen([py, APP_FILE])
            self.root.after(0, self.root.destroy)

        except subprocess.CalledProcessError as e:
            failed_package = e.cmd[-2] if len(e.cmd) > 2 else "Unknown Library"
            error_msg = f"❌ Error: Failed to install '{failed_package}'. Check internet connection."
            self.root.after(0, lambda: self.status.config(text=error_msg, fg="#e74c3c"))
            self.root.after(0, lambda: self.percent_label.config(text="ERROR", fg="#e74c3c"))
            self.root.after(0, lambda: self.progress.stop())

if __name__ == "__main__":
    root = tk.Tk()
    LauncherUI(root)
    root.mainloop()