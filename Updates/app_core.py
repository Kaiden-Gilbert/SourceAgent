import os, sys, threading, time, urllib.request, subprocess, math, random, json
from urllib.error import HTTPError, URLError

# --- ENVIRONMENT SEED PROTOCOLS ---
try:
    import tkinter as tk
    import customtkinter as ctk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "-q"])
    import tkinter as tk
    import customtkinter as ctk

# --- CONFIGURATION & PATHS ---
BASE_DIR = os.getcwd()
CORE_FILE = os.path.join(BASE_DIR, "app_core.py")
VERSION_FILE = os.path.join(BASE_DIR, "local_version.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")

VERSION_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/version.json"
CORE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/app_core.py"

ctk.set_appearance_mode("Dark")

# ==========================================
# SELF-HEALING FILESYSTEM ROUTINE
# ==========================================
def ensure_local_ecosystem():
    """Builds the necessary directories and config files if the folder is empty."""
    os.makedirs(SOURCE_DIR, exist_ok=True)
    
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "theme_mode": "Dark", 
                "accent_color": "blue", 
                "ai_model": "tinyllama",
                "chunk_depth": 5,
                "temperature": 0.2,
                "repeat_penalty": 1.2,
                "max_tokens": 512,
                "vault_summary": "No active documents compiled in library vault."
            }, f, indent=4)
            
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "w") as f:
            json.dump({"version": 0.0}, f)

ensure_local_ecosystem()

# ==========================================
# UNIVERSAL HYBRID BOOTLOADER UI
# ==========================================
class UniversalBootloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent Bootloader")
        self.geometry("600x350")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)
        self.configure(fg_color="#090d16")
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 300
        y = (self.winfo_screenheight() // 2) - 175
        self.geometry(f"+{x}+{y}")
        
        self.canvas = tk.Canvas(self, width=600, height=350, bg="#090d16", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.draw_cyber_grid_geometry()
        
        self.canvas.create_text(300, 115, text="Source Agent", font=("Segoe UI", 50, "bold"), fill="#ffffff")
        self.canvas.create_text(300, 165, text="UNIVERSAL HYBRID WORKSTATION", font=("Segoe UI", 10, "bold"), fill="#3b82f6")
        
        bouncy_phrases = ["HYBRID BOOT ACTIVE", "CROSS-PLATFORM NODE", "OTA READY OR AIR-GAPPED", "FAILSAFE PROTOCOLS ENGAGED"]
        self.splash_id = self.canvas.create_text(440, 195, text=random.choice(bouncy_phrases), font=("Segoe UI", 12, "bold", "italic"), fill="#facc15")
        
        self.console_id = self.canvas.create_text(50, 275, text="[0x0000] COLD_LOAD_SEQUENCE_START...", font=("Consolas", 11), fill="#10b981", anchor="w")
        
        self.canvas.create_rectangle(50, 305, 530, 308, fill="#1f2937", width=0)
        self.bar_fill = self.canvas.create_rectangle(50, 305, 50, 308, fill="#3b82f6", width=0)
        self.pct_id = self.canvas.create_text(555, 306, text="0%", font=("Consolas", 12, "bold"), fill="#3b82f6")

        self.animation_tick = 0.0
        self.alpha_step = 0.0
        self.target_prog = 0.0
        self.current_prog = 0.0
        
        self.execute_fade_in_loop()
        self.execute_bounce_loop()
        self.execute_progress_step_loop()
        
        threading.Thread(target=self.process_hybrid_verification, daemon=True).start()

    def draw_cyber_grid_geometry(self):
        self.canvas.create_line(12, 12, 35, 12, fill="#1e293b", width=2)
        self.canvas.create_line(12, 12, 12, 35, fill="#1e293b", width=2)
        self.canvas.create_line(588, 12, 565, 12, fill="#1e293b", width=2)
        self.canvas.create_line(588, 12, 588, 35, fill="#1e293b", width=2)
        self.canvas.create_line(12, 338, 35, 338, fill="#1e293b", width=2)
        self.canvas.create_line(12, 338, 12, 315, fill="#1e293b", width=2)
        self.canvas.create_line(588, 338, 565, 338, fill="#1e293b", width=2)
        self.canvas.create_line(588, 338, 588, 315, fill="#1e293b", width=2)

    def execute_fade_in_loop(self):
        if self.alpha_step < 1.0:
            self.alpha_step += 0.06
            self.attributes("-alpha", self.alpha_step)
            self.after(15, self.execute_fade_in_loop)

    def execute_bounce_loop(self):
        self.animation_tick += 0.14
        offset = math.sin(self.animation_tick) * 6
        self.canvas.coords(self.splash_id, 440, 195 + offset)
        self.after(20, self.execute_bounce_loop)

    def execute_progress_step_loop(self):
        if self.current_prog < self.target_prog:
            self.current_prog += 0.02
            if self.current_prog > self.target_prog: 
                self.current_prog = self.target_prog
            
            end_x = 50 + int(480 * self.current_prog)
            self.canvas.coords(self.bar_fill, 50, 305, end_x, 308)
            
            pct = int(self.current_prog * 100)
            self.canvas.itemconfig(self.pct_id, text=f"{pct}%")
            
        self.after(12, self.execute_progress_step_loop)

    def update_console_log(self, text, color="#10b981", step_val=None, delay=0.5):
        self.canvas.itemconfig(self.console_id, text=text, fill=color)
        if step_val: self.target_prog = step_val
        time.sleep(delay)

    def process_hybrid_verification(self):
        time.sleep(0.8)
        
        self.update_console_log("[0x8F1C] VERIFYING_LOCAL_ECOSYSTEM...", step_val=0.20)
        self.update_console_log("[0x4B3A] PINGING_GITHUB_FOR_OTA_PAYLOAD...", step_val=0.40)
        
        # 1. PING GITHUB FOR LATEST VERSION (SAFE HYBRID CHECK)
        cloud_v = 0.0
        try:
            r_req = urllib.request.Request(VERSION_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(r_req, timeout=3.0) as response_stream:
                cloud_v = float(json.loads(response_stream.read().decode('utf-8')).get('app_version', 0.0))
        except HTTPError as e:
            if e.code == 404:
                self.update_console_log(f"[0xWARN] GITHUB 404: REPOSITORY MISSING OR PRIVATE. FALLING BACK.", "#f59e0b", delay=1.5)
        except URLError:
            self.update_console_log("[0xWARN] NETWORK OFFLINE. LOCAL AIR-GAP MODE ENGAGED.", "#f59e0b", delay=1.5)
        except Exception as e:
            self.update_console_log(f"[0xWARN] SYNC ERROR: {e}. IGNORING.", "#f59e0b", delay=1.5)

        # 2. READ LOCAL VERSION
        local_v = 0.0
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, "r") as v_file: local_v = float(json.load(v_file).get("version", 0.0))
            except: pass

        core_exists = os.path.exists(CORE_FILE)

        # 3. DOWNLOAD APP_CORE.PY IF CLOUD IS HIGHER OR LOCAL IS MISSING
        if cloud_v > local_v or (cloud_v > 0.0 and not core_exists):
            self.update_console_log("[0xDL00] SYNC_OUT_OF_DATE! PULLING_REMOTE_CORE...", "#3b82f6", step_val=0.60)
            try:
                r_req = urllib.request.Request(CORE_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
                with urllib.request.urlopen(r_req, timeout=12) as response_stream:
                    downloaded_payload = response_stream.read().decode('utf-8')
                with open(CORE_FILE, "w", encoding="utf-8") as core_out:
                    core_out.write(downloaded_payload)
                with open(VERSION_FILE, "w") as v_out:
                    json.dump({"version": cloud_v}, v_out)
                self.update_console_log("[0xDL01] CORE_UPDATED_SUCCESSFULLY.", "#10b981", delay=0.5)
                core_exists = True
            except Exception as e:
                self.update_console_log(f"[0xERR] DOWNLOAD FAILED: {e}", "#ef4444", delay=1.5)

        # 4. FINAL FATAL CHECK
        if not core_exists:
            self.update_console_log("[0xFATAL] NO LOCAL CORE FOUND AND DOWNLOAD FAILED. ABORTING.", "#ef4444", step_val=1.0, delay=4.0)
            self.after(0, self.destroy)
            return

        self.update_console_log("[0x1F8B] COMPILING_RUNTIME_SANDBOX...", step_val=0.85)
        self.update_console_log("[0x0000] LAUNCHING_CROSS_PLATFORM_MATRIX...", step_val=1.0)
        
        self.after(0, self.dispatch_main_engine_app)

    def dispatch_main_engine_app(self):
        self.withdraw()
        # Cross-platform safe execution
        if sys.platform.startswith('win'):
            subprocess.Popen([sys.executable, CORE_FILE], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            # Mac and Linux execution
            subprocess.Popen([sys.executable, CORE_FILE])
        sys.exit()

if __name__ == "__main__":
    boot_sequence = UniversalBootloader()
    boot_sequence.mainloop()
