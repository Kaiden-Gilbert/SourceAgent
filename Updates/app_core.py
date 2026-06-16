import os, sys, threading, time, urllib.request, subprocess, math, random, json
from urllib.error import HTTPError, URLError

try:
    import tkinter as tk
    import customtkinter as ctk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "-q"])
    import tkinter as tk
    import customtkinter as ctk

# --- CONSTANTS & PATHS ---
BASE_DIR = os.getcwd()
CORE_FILE = os.path.join(BASE_DIR, "app_core.py")
VERSION_FILE = os.path.join(BASE_DIR, "local_version.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOOP_GUARD_FILE = os.path.join(BASE_DIR, "loop_guard.tmp")

VERSION_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/version.json"
CORE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/app_core.py"

ctk.set_appearance_mode("Dark")

# ==========================================
# CIRCUIT BREAKER (BOOT LOOP SHIELD)
# ==========================================
def check_boot_loop_circuit():
    """Prevents infinite loops if scripts accidentally cross-trigger."""
    now = time.time()
    if os.path.exists(LOOP_GUARD_FILE):
        try:
            with open(LOOP_GUARD_FILE, "r") as f:
                last_boot = float(f.read().strip())
            # If launched twice in less than 4 seconds, trip the breaker
            if now - last_boot < 4.0:
                print("[0xCRIT] Boot loop detected! Tripping circuit breaker.")
                return True
        except: pass
    
    try:
        with open(LOOP_GUARD_FILE, "w") as f:
            f.write(str(now))
    except: pass
    return False

# ==========================================
# SEED SYSTEM FILESYSTEM
# ==========================================
if not os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, "w") as f: json.dump({"version": 51.0}, f)

# ==========================================
# RUNTIME HUD UI
# ==========================================
class DecoupledBootloader(ctk.CTk):
    def __init__(self, bypass_update=False):
        super().__init__()
        self.title("Source Agent Launcher")
        self.geometry("600x350")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)
        self.configure(fg_color="#090d16")
        
        # Center Window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 300
        y = (self.winfo_screenheight() // 2) - 175
        self.geometry(f"+{x}+{y}")
        
        self.canvas = tk.Canvas(self, width=600, height=350, bg="#090d16", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # UI Elements
        self.canvas.create_text(300, 120, text="Source Agent", font=("Segoe UI", 48, "bold"), fill="#ffffff")
        self.canvas.create_text(300, 170, text="DECOUPLED LOCAL RUNTIME V53", font=("Segoe UI", 10, "bold"), fill="#10b981")
        self.console_id = self.canvas.create_text(50, 275, text="Initializing localized core...", font=("Consolas", 11), fill="#9ca3af", anchor="w")
        
        self.canvas.create_rectangle(50, 305, 530, 308, fill="#1f2937", width=0)
        self.bar_fill = self.canvas.create_rectangle(50, 305, 50, 308, fill="#10b981", width=0)
        
        self.alpha_step = 0.0
        self.target_prog = 0.0
        self.current_prog = 0.0
        
        self.fade_in()
        self.animate_progress()
        
        if bypass_update:
            threading.Thread(target=self.pure_local_launch, daemon=True).start()
        else:
            threading.Thread(target=self.run_updater_sequence, daemon=True).start()

    def fade_in(self):
        if self.alpha_step < 1.0:
            self.alpha_step += 0.08
            self.attributes("-alpha", self.alpha_step)
            self.after(15, self.fade_in)

    def animate_progress(self):
        if self.current_prog < self.target_prog:
            self.current_prog += 0.02
            end_x = 50 + int(480 * self.current_prog)
            self.canvas.coords(self.bar_fill, 50, 305, end_x, 308)
        self.after(15, self.animate_progress)

    def log(self, text, color="#9ca3af", progress=None, delay=0.4):
        self.canvas.itemconfig(self.console_id, text=text, fill=color)
        if progress is not None: self.target_prog = progress
        time.sleep(delay)

    def pure_local_launch(self):
        self.log("[0xBRK] CIRCUIT BREAKER ACTIVE: BYPASSING ONLINE CHECK", "#f59e0b", 0.5, 1.0)
        self.log("Launching local workspace environment...", "#10b981", 1.0, 0.5)
        self.after(0, self.boot_local_core)

    def run_updater_sequence(self):
        time.sleep(0.5)
        self.log("Checking local system files...", "#6b7280", 0.2, 0.4)
        
        # Read local validation metrics
        local_v = 51.0
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, "r") as f: local_v = float(json.load(f).get("version", 51.0))
            except: pass

        self.log(f"Local version: V{local_v} | Pinging update node...", "#3b82f6", 0.5, 0.3)
        
        cloud_v = 0.0
        try:
            req = urllib.request.Request(VERSION_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=2.5) as r:
                cloud_v = float(json.loads(r.read().decode('utf-8')).get('app_version', 0.0))
        except:
            # Silently catch all timeouts, 404s, and offline states
            self.log("Update server unreachable. Running local instance.", "#eab308", 0.8, 0.8)

        # Only pull if GitHub explicitly hosts a newer certified core build
        if cloud_v > local_v and cloud_v > 51.0:
            self.log(f"New patch detected: V{cloud_v}. Downloading assets...", "#10b981", 0.7, 0.5)
            try:
                req = urllib.request.Request(CORE_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    payload = r.read().decode('utf-8')
                with open(CORE_FILE, "w", encoding="utf-8") as f:
                    f.write(payload)
                with open(VERSION_FILE, "w") as f:
                    json.dump({"version": cloud_v}, f)
                self.log("Patch successfully applied.", "#10b981", 0.9, 0.4)
            except Exception as e:
                self.log("Download interrupted. Defaulting to local workspace.", "#f43f5e", 0.8, 1.0)
        else:
            self.log("Local workspace is fully optimized.", "#10b981", 0.9, 0.4)

        self.log("Booting system shell...", "#10b981", 1.0, 0.3)
        self.after(0, self.boot_local_core)

    def boot_local_core(self):
        self.withdraw()
        if os.path.exists(LOOP_GUARD_FILE):
            try: os.remove(LOOP_GUARD_FILE)
            except: pass
            
        if os.path.exists(CORE_FILE):
            if sys.platform.startswith('win'):
                subprocess.Popen([sys.executable, CORE_FILE, "--launched-by-bootloader"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen([sys.executable, CORE_FILE, "--launched-by-bootloader"])
        else:
            ctk.CTkMessageBox(title="Missing Component", message="Critical Error: app_core.py not found in directory.")
        sys.exit()

if __name__ == "__main__":
    is_looping = check_boot_loop_circuit()
    app = DecoupledBootloader(bypass_update=is_looping)
    app.mainloop()
