import os, sys, urllib.request, time, threading, subprocess, json
import tkinter as tk
from tkinter import messagebox, ttk

# --- SINGLE INSTANCE LOCK ---
if os.environ.get("SA_BOOTLOADER") == "1":
    sys.exit(0)
os.environ["SA_BOOTLOADER"] = "1"

APP_DIR = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), "SourceAgentPro")
os.makedirs(APP_DIR, exist_ok=True)
ENGINE_FILE = os.path.join(APP_DIR, "app_core.py")
GITHUB_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/app_core.py"
VERSION_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/version.json"

class Bootloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent Initialization")
        self.geometry("400x160")
        self.configure(bg="#020617")
        self.overrideredirect(True)
        
        # Center Window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.winfo_screenheight() // 2) - (160 // 2)
        self.geometry(f"+{x}+{y}")

        self.lbl = tk.Label(self, text="Verifying Environment...", bg="#020617", fg="#3b82f6", font=("Segoe UI", 12, "bold"))
        self.lbl.pack(pady=(35, 15))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("Blue.Horizontal.TProgressbar", background='#3b82f6', thickness=4)
        self.pb = ttk.Progressbar(self, mode='indeterminate', length=300, style="Blue.Horizontal.TProgressbar")
        self.pb.pack()
        self.pb.start(15)

        self.ready_to_launch = False
        threading.Thread(target=self.process_boot, daemon=True).start()

    def update_text(self, text, color="#3b82f6"):
        self.after(0, lambda: self.lbl.config(text=text, fg=color))

    def process_boot(self):
        # 1. Dependency Check
        required = ["customtkinter", "langchain-openai", "langchain-huggingface", "langchain-community", "faiss-cpu", "pymupdf", "python-dotenv", "sentence-transformers"]
        try:
            import customtkinter, langchain_openai, faiss, fitz
            self.update_text("Environment Verified.", "#10b981")
        except ImportError:
            self.update_text("Installing Dependencies...", "#f59e0b")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + required)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Setup Error", f"Failed to install dependencies:\n{e}"))
                self.after(0, lambda: sys.exit(1))

        # 2. Sync Engine with strict Cache-Busting
        self.update_text("Syncing with Cloud Engine...")
        try:
            req = urllib.request.Request(
                GITHUB_URL + "?t=" + str(time.time()), 
                headers={'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache'}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                code = r.read().decode('utf-8')
            with open(ENGINE_FILE, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            if not os.path.exists(ENGINE_FILE):
                self.after(0, lambda: messagebox.showerror("Network Error", "Cannot reach GitHub and no local cache exists."))
                self.after(0, lambda: sys.exit(1))

        time.sleep(0.5)
        self.ready_to_launch = True
        self.after(0, self.finish)

    def finish(self):
        self.pb.stop()
        self.destroy()

def run_poller_and_app():
    """Runs the main app in an isolated subprocess and polls for cloud updates."""
    current_process = None
    current_version = None

    # Fetch initial version
    try:
        req = urllib.request.Request(VERSION_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, timeout=5) as r:
            current_version = json.loads(r.read().decode('utf-8')).get('app_version')
    except:
        pass

    # Inject vault directory into the subprocess environment
    env = os.environ.copy()
    env['VAULT_DIR'] = APP_DIR

    # Launch the isolated CustomTkinter Engine
    current_process = subprocess.Popen([sys.executable, ENGINE_FILE], env=env)

    # Background Poller Loop
    while True:
        time.sleep(60) # Ping every 60s
        
        # If the user closed the main application window, shut down the bootloader completely
        if current_process.poll() is not None:
            sys.exit(0)

        try:
            req = urllib.request.Request(VERSION_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as r:
                new_v = json.loads(r.read().decode('utf-8')).get('app_version')

            if current_version and new_v and new_v != current_version:
                # Update detected!
                current_version = new_v
                
                # Download new code
                req_code = urllib.request.Request(GITHUB_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
                with urllib.request.urlopen(req_code, timeout=15) as rc:
                    with open(ENGINE_FILE, "w", encoding="utf-8") as f:
                        f.write(rc.read().decode('utf-8'))
                
                # Gracefully kill the old window and launch the new one
                current_process.terminate()
                current_process.wait()
                current_process = subprocess.Popen([sys.executable, ENGINE_FILE], env=env)
        except:
            pass

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    app = Bootloader()
    app.mainloop()

    # Once the UI is completely dead, spawn the subprocess
    if app.ready_to_launch:
        run_poller_and_app()
