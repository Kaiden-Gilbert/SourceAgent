import os, sys, subprocess, threading, time, venv, urllib.request, json
import tkinter as tk
from tkinter import ttk

# --- BOOTLOADER CONFIGURATION ---
LAUNCHER_VERSION = 2.0  # The version of this specific launcher script
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

# --- PATHS ---
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
        self.root.configure(bg="#0b0b12") # Matched to the new cinematic UI
        
        ttk.Style().theme_use('clam')
        ttk.Style().configure("TProgressbar", thickness=10, background="#6366f1", troughcolor="#161622", bordercolor="#0b0b12")

        self.main_frame = tk.Frame(root, bg="#0b0b12", padx=30, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.main_frame, text="SourceAgent Pro", font=("Segoe UI", 24, "bold"), bg="#0b0b12", fg="#ffffff").pack(pady=(0, 5))
        self.subtitle = tk.Label(self.main_frame, text="Checking Cloud Network...", font=("Segoe UI", 12), bg="#0b0b12", fg="#94a3b8")
        self.subtitle.pack(pady=(0, 15))
        
        self.status = tk.Label(self.main_frame, text="Establishing secure connection...", font=("Segoe UI", 10, "italic"), bg="#0b0b12", fg="#f8fafc")
        self.status.pack()

        self.content_frame = tk.Frame(self.main_frame, bg="#0b0b12")
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        threading.Thread(target=self.run_dual_sync, daemon=True).start()

    # ==========================================
    # 1. DUAL-SYNC ENGINE
    # ==========================================
    def get_local_app_version(self):
        try: return float(open(VERSION_FILE, "r").read().strip()) if os.path.exists(VERSION_FILE) else 3.0
        except: return 3.0

    def run_dual_sync(self):
        try:
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + "version.json", headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as response:
                cloud_data = json.loads(response.read().decode('utf-8'))
                
            cloud_app_v = float(cloud_data.get("app_version", 0.0))
            cloud_launcher_v = float(cloud_data.get("launcher_version", LAUNCHER_VERSION))
            changelog = cloud_data.get("changelog", "System optimizations.")
            local_app_v = self.get_local_app_version()

            # PRIORITY 1: Check if the Launcher itself needs an update
            if cloud_launcher_v > LAUNCHER_VERSION:
                self.root.after(0, lambda: self.show_update_prompt("Launcher", cloud_launcher_v, changelog, is_launcher=True))
            
            # PRIORITY 2: Check if the App needs an update
            elif cloud_app_v > local_app_v:
                self.root.after(0, lambda: self.show_update_prompt("Application", cloud_app_v, changelog, is_launcher=False))
            
            # PRIORITY 3: Everything is up to date
            else:
                self.root.after(0, self.run_local_diagnostics)

        except Exception as e:
            print(f"Cloud Sync failed: {e}")
            self.root.after(0, self.run_local_diagnostics)

    # ==========================================
    # 2. THE PROMPT UI
    # ==========================================
    def show_update_prompt(self, target_name, new_version, changelog, is_launcher):
        self.subtitle.config(text=f"{target_name} Update Found!", fg="#2ecc71")
        self.status.config(text="A critical system update is ready.")
        for widget in self.content_frame.winfo_children(): widget.destroy()
        
        update_box = tk.Frame(self.content_frame, bg="#161622", padx=15, pady=15)
        update_box.pack(fill=tk.BOTH, expand=True)
        tk.Label(update_box, text=f"v{new_version} Details:", font=("Segoe UI", 12, "bold"), bg="#161622", fg="#ffffff", anchor="w").pack(fill=tk.X, pady=(0, 10))
        
        changelog_text = tk.Text(update_box, height=8, bg="#0b0b12", fg="#dddddd", font=("Segoe UI", 10), relief="flat", padx=10, pady=10)
        changelog_text.insert(tk.END, changelog); changelog_text.config(state="disabled"); changelog_text.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(self.content_frame, bg="#0b0b12")
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        action = lambda: self.execute_launcher_update(new_version) if is_launcher else lambda: self.execute_app_update(new_version)
        tk.Button(btn_frame, text=f"Sync {target_name}", bg="#6366f1", fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=10, command=action).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        tk.Button(btn_frame, text="Skip", bg="#333333", fg="white", font=("Segoe UI", 11), relief="flat", padx=10, pady=10, command=self.run_local_diagnostics).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))

    # ==========================================
    # 3. DOWNLOAD ENGINES
    # ==========================================
    def build_progress_ui(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        self.progress = ttk.Progressbar(self.content_frame, length=350, mode='determinate'); self.progress.pack(pady=30)
        self.percent_label = tk.Label(self.content_frame, text="0%", font=("Segoe UI", 24, "bold"), bg="#0b0b12", fg="#6366f1"); self.percent_label.pack()

    def update_ui(self, text, value):
        self.status.config(text=text); self.progress['value'] = value
        if hasattr(self, 'percent_label'): self.percent_label.config(text=f"{int(value)}%")

    # --- THE LAUNCHER SELF-UPDATE METHOD ---
    def execute_launcher_update(self, new_version):
        self.subtitle.config(text="Updating Bootloader...", fg="#94a3b8")
        self.build_progress_ui()
        threading.Thread(target=self._download_launcher, daemon=True).start()

    def _download_launcher(self):
        try:
            self.root.after(0, self.update_ui, "Overwriting local launcher.py...", 50)
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + "launcherupdate.py", headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req) as response:
                with open(__file__, "wb") as f: # Overwrites itself!
                    f.write(response.read())
            
            self.root.after(0, self.update_ui, "Rebooting Launcher Engine...", 100)
            time.sleep(1)
            
            # The Magic Self-Restart Command
            subprocess.Popen([sys.executable, __file__] + sys.argv[1:])
            self.root.after(0, self.root.destroy)
            
        except Exception as e:
            self.root.after(0, lambda: self.status.config(text=f"Failed: {e}", fg="#e74c3c"))

    # --- THE APP UPDATE METHOD ---
    def execute_app_update(self, new_version):
        self.subtitle.config(text="Downloading App Code...", fg="#94a3b8")
        self.build_progress_ui()
        threading.Thread(target=self._download_app, args=(new_version,), daemon=True).start()

    def _download_app(self, new_version):
        try:
            self.root.after(0, self.update_ui, "Downloading appupdate.py...", 30)
            with urllib.request.urlopen(urllib.request.Request(GITHUB_RAW_BASE_URL + "appupdate.py", headers={'Cache-Control': 'no-cache'})) as response:
                with open(APP_FILE, "wb") as f: f.write(response.read())

            self.root.after(0, self.update_ui, "Syncing dependencies...", 70)
            try:
                with urllib.request.urlopen(urllib.request.Request(GITHUB_RAW_BASE_URL + "requirements.txt", headers={'Cache-Control': 'no-cache'})) as response:
                    with open(os.path.join(BASE_DIR, "requirements.txt"), "wb") as f: f.write(response.read())
            except: pass

            with open(VERSION_FILE, "w") as f: f.write(str(new_version))
            self.root.after(0, self.update_ui, "Update complete! Initializing...", 100); time.sleep(1)
            self.root.after(0, self.run_local_diagnostics)
            
        except Exception as e:
            self.root.after(0, lambda: self.status.config(text=f"Update failed: {e}", fg="#e74c3c"))
            self.root.after(0, lambda: self.percent_label.config(text="ERROR", fg="#e74c3c"))

    # ==========================================
    # 4. STANDARD BOOT SEQUENCE
    # ==========================================
    def run_local_diagnostics(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        self.subtitle.config(text="System Diagnostics", fg="#94a3b8")
        
        if not os.path.exists(VERSION_FILE): open(VERSION_FILE, "w").write("3.0")
        if not (os.path.exists(ENV_FILE) and "OPENROUTER_API_KEY=" in open(ENV_FILE, "r").read()): self.show_api_screen()
        else: self.show_install_screen()

    def show_api_screen(self):
        self.status.config(text="Action Required")
        tk.Label(self.content_frame, text="Enter your OpenRouter API Key:", font=("Segoe UI", 11), bg="#0b0b12", fg="#ffffff").pack(pady=10)
        self.entry = tk.Entry(self.content_frame, width=45, show="*", font=("Segoe UI", 12), bg="#161622", fg="#ffffff", insertbackground="white", relief="flat")
        self.entry.pack(pady=10, ipady=5)
        tk.Button(self.content_frame, text="Save & Initialize", command=self.save_key, bg="#6366f1", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=10, pady=15).pack(pady=15)

    def save_key(self):
        if key := self.entry.get().strip(): open(ENV_FILE, "a").write(f"\nOPENROUTER_API_KEY={key}\n"); self.run_local_diagnostics() 

    def show_install_screen(self):
        self.status.config(text="Verifying Sandbox Environment...")
        self.build_progress_ui()
        threading.Thread(target=self.run_setup, daemon=True).start()

    def run_setup(self):
        try:
            if not os.path.exists(VENV_DIR): venv.create(VENV_DIR, with_pip=True)
            py = get_venv_python()
            
            self.root.after(0, self.update_ui, "Updating Build Tools...", 10)
            subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "--quiet"])
            
            if os.path.exists(os.path.join(BASE_DIR, "requirements.txt")):
                self.root.after(0, self.update_ui, "Syncing Cloud Dependencies...", 50)
                subprocess.check_call([py, "-m", "pip", "install", "-r", os.path.join(BASE_DIR, "requirements.txt"), "--quiet"])
                
            self.root.after(0, self.update_ui, "System Ready!", 100); time.sleep(0.5)
            subprocess.Popen([py, APP_FILE])
            self.root.after(0, self.root.destroy)
            
        except subprocess.CalledProcessError as e:
            self.root.after(0, lambda: self.status.config(text="❌ Error: Dependency installation failed.", fg="#e74c3c"))
            self.root.after(0, lambda: self.percent_label.config(text="ERROR", fg="#e74c3c")); self.root.after(0, lambda: self.progress.stop())

if __name__ == "__main__":
    root = tk.Tk()
    LauncherUI(root)
    root.mainloop()
