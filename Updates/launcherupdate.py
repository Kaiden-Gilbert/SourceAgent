import os, sys, subprocess, threading, time, venv, urllib.request, json
import tkinter as tk
from tkinter import ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
ENV_FILE = os.path.join(BASE_DIR, ".env")
APP_FILE = os.path.join(BASE_DIR, "app.py")
VERSION_FILE = os.path.join(BASE_DIR, "latest_version.txt")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")

GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

def get_venv_python(): return os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(VENV_DIR, "bin", "python")

class LauncherUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SourceAgent Pro v4.0 Cloud Bootloader")
        self.root.geometry("520x550")
        self.root.configure(bg="#1e1e1e") 
        
        ttk.Style().theme_use('clam')
        ttk.Style().configure("TProgressbar", thickness=10, background="#2ecc71", troughcolor="#2b2b2b", bordercolor="#1e1e1e")

        self.main_frame = tk.Frame(root, bg="#1e1e1e", padx=30, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.main_frame, text="SourceAgent Pro", font=("Segoe UI", 22, "bold"), bg="#1e1e1e", fg="#ffffff").pack(pady=(0, 5))
        self.subtitle = tk.Label(self.main_frame, text="Synchronizing with Cloud...", font=("Segoe UI", 12), bg="#1e1e1e", fg="#aaaaaa")
        self.subtitle.pack(pady=(0, 15))
        
        self.status = tk.Label(self.main_frame, text="Checking for OTA updates...", font=("Segoe UI", 10, "italic"), bg="#1e1e1e", fg="#dddddd")
        self.status.pack()

        self.content_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        threading.Thread(target=self.check_cloud_updates, daemon=True).start()

    def get_local_version(self):
        try: return float(open(VERSION_FILE, "r").read().strip()) if os.path.exists(VERSION_FILE) else 3.0
        except: return 3.0

    def check_cloud_updates(self):
        try:
            with urllib.request.urlopen(urllib.request.Request(GITHUB_RAW_BASE_URL + "version.json", headers={'Cache-Control': 'no-cache'}), timeout=5) as response:
                cloud_data = json.loads(response.read().decode('utf-8'))
            if float(cloud_data.get("version", 0.0)) > self.get_local_version():
                self.root.after(0, lambda: self.show_update_prompt(float(cloud_data.get("version", 0.0)), cloud_data.get("changelog", "Minor fixes.")))
            else: self.root.after(0, self.run_local_diagnostics)
        except Exception as e: self.root.after(0, self.run_local_diagnostics)

    def show_update_prompt(self, new_version, changelog):
        self.subtitle.config(text="Update Available!", fg="#2ecc71")
        self.status.config(text="A newer version is ready for installation.")
        for widget in self.content_frame.winfo_children(): widget.destroy()
        
        update_box = tk.Frame(self.content_frame, bg="#2b2b2b", padx=15, pady=15)
        update_box.pack(fill=tk.BOTH, expand=True)
        tk.Label(update_box, text=f"Version {new_version} Changelog:", font=("Segoe UI", 12, "bold"), bg="#2b2b2b", fg="#ffffff", anchor="w").pack(fill=tk.X, pady=(0, 10))
        
        changelog_text = tk.Text(update_box, height=8, bg="#1e1e1e", fg="#dddddd", font=("Segoe UI", 10), relief="flat", padx=10, pady=10)
        changelog_text.insert(tk.END, changelog); changelog_text.config(state="disabled"); changelog_text.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(self.content_frame, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        tk.Button(btn_frame, text="Update Application Now", bg="#2ecc71", fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=10, command=lambda: self.execute_update(new_version)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        tk.Button(btn_frame, text="Skip", bg="#444444", fg="white", font=("Segoe UI", 11), relief="flat", padx=10, pady=10, command=self.run_local_diagnostics).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))

    def execute_update(self, new_version):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        self.subtitle.config(text="Downloading OTA Update...", fg="#aaaaaa")
        self.progress = ttk.Progressbar(self.content_frame, length=350, mode='determinate'); self.progress.pack(pady=30)
        self.percent_label = tk.Label(self.content_frame, text="0%", font=("Segoe UI", 24, "bold"), bg="#1e1e1e", fg="#2ecc71"); self.percent_label.pack()
        threading.Thread(target=self.download_files, args=(new_version,), daemon=True).start()

    def update_ui(self, text, value):
        self.status.config(text=text); self.progress['value'] = value
        if hasattr(self, 'percent_label'): self.percent_label.config(text=f"{int(value)}%")

    def download_files(self, new_version):
        try:
            self.root.after(0, self.update_ui, "Downloading appupdate.py...", 20)
            with urllib.request.urlopen(urllib.request.Request(GITHUB_RAW_BASE_URL + "appupdate.py", headers={'Cache-Control': 'no-cache'})) as response:
                with open(APP_FILE, "wb") as f: f.write(response.read())

            self.root.after(0, self.update_ui, "Downloading launcherupdate.py...", 40)
            try:
                with urllib.request.urlopen(urllib.request.Request(GITHUB_RAW_BASE_URL + "launcherupdate.py", headers={'Cache-Control': 'no-cache'})) as response:
                    with open(__file__, "wb") as f: f.write(response.read())
            except urllib.error.HTTPError: pass 

            self.root.after(0, self.update_ui, "Downloading dependencies...", 60)
            try:
                with urllib.request.urlopen(urllib.request.Request(GITHUB_RAW_BASE_URL + "requirements.txt", headers={'Cache-Control': 'no-cache'})) as response:
                    with open(os.path.join(BASE_DIR, "requirements.txt"), "wb") as f: f.write(response.read())
            except urllib.error.HTTPError: pass

            with open(VERSION_FILE, "w") as f: f.write(str(new_version))
            self.root.after(0, self.update_ui, "Update complete! Initializing...", 100); time.sleep(1)
            self.root.after(0, self.run_local_diagnostics)
        except Exception as e:
            self.root.after(0, lambda: self.status.config(text=f"Update failed: {e}", fg="#e74c3c"))
            self.root.after(0, lambda: self.percent_label.config(text="ERROR", fg="#e74c3c")); self.root.after(0, lambda: self.progress.stop())

    def run_local_diagnostics(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        self.subtitle.config(text="System Diagnostics", fg="#aaaaaa")
        if not os.path.exists(VERSION_FILE): open(VERSION_FILE, "w").write("3.0")
        if not (os.path.exists(ENV_FILE) and "OPENROUTER_API_KEY=" in open(ENV_FILE, "r").read()): self.show_api_screen()
        else: self.show_install_screen()

    def show_api_screen(self):
        self.status.config(text="Action Required")
        tk.Label(self.content_frame, text="Enter your OpenRouter API Key:", font=("Segoe UI", 11), bg="#1e1e1e", fg="#ffffff").pack(pady=10)
        self.entry = tk.Entry(self.content_frame, width=45, show="*", font=("Segoe UI", 12), bg="#2b2b2b", fg="#ffffff", insertbackground="white", relief="flat")
        self.entry.pack(pady=10, ipady=5)
        tk.Button(self.content_frame, text="Save & Initialize", command=self.save_key, bg="#2ecc71", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=10, pady=15).pack(pady=15)

    def save_key(self):
        if key := self.entry.get().strip(): open(ENV_FILE, "a").write(f"\nOPENROUTER_API_KEY={key}\n"); self.run_local_diagnostics() 

    def show_install_screen(self):
        self.status.config(text="Verifying Virtual Environment...")
        self.progress = ttk.Progressbar(self.content_frame, length=350, mode='determinate'); self.progress.pack(pady=20)
        self.percent_label = tk.Label(self.content_frame, text="0%", font=("Segoe UI", 24, "bold"), bg="#1e1e1e", fg="#2ecc71"); self.percent_label.pack()
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
            self.root.after(0, self.update_ui, "System Ready!", 100); time.sleep(0.8)
            subprocess.Popen([py, APP_FILE])
            self.root.after(0, self.root.destroy)
        except subprocess.CalledProcessError as e:
            self.root.after(0, lambda: self.status.config(text="❌ Error: Dependency installation failed.", fg="#e74c3c"))
            self.root.after(0, lambda: self.percent_label.config(text="ERROR", fg="#e74c3c")); self.root.after(0, lambda: self.progress.stop())

if __name__ == "__main__":
    root = tk.Tk()
    LauncherUI(root)
    root.mainloop()
