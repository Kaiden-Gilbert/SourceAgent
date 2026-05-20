import os, sys, urllib.request, json, time, traceback, ssl, threading, re
import tkinter as tk
from tkinter import ttk, messagebox

# --- INVISIBLE DEPENDENCY BLOCK ---
if False:
    import langchain_openai, langchain_huggingface, langchain_community
    import langchain_text_splitters, langchain_core
    import customtkinter, cv2, dotenv, faiss, fitz, numpy

# We establish the AppData Vault ONLY to save the user's PDFs and Chat History.
LOCAL_APP_DATA = os.getenv('LOCALAPPDATA')
APP_DIR = os.path.join(LOCAL_APP_DATA, "SourceAgentPro")

if not os.path.exists(APP_DIR):
    try: os.makedirs(APP_DIR)
    except Exception: pass

GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

class Bootloader(tk.Tk):
    def __init__(self):
        super().__init__()
        print("[BOOT] Initializing UI...")
        self.title("SourceAgent Bootloader v9.3")
        self.geometry("520x400")
        self.configure(bg="#050508")
        self.overrideredirect(True) 
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (520 // 2)
        y = (self.winfo_screenheight() // 2) - (400 // 2)
        self.geometry(f"+{x}+{y}")

        tk.Label(self, text="SOURCEAGENT", font=("Segoe UI", 28, "bold"), bg="#050508", fg="#f8fafc").pack(pady=(80, 10))
        self.status = tk.Label(self, text="ESTABLISHING SECURE CONNECTION...", font=("Segoe UI", 9, "bold"), bg="#050508", fg="#6366f1")
        self.status.pack()
        
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Cyan.Horizontal.TProgressbar", background='#6366f1', trolleycolor='#6366f1', thickness=4)
        self.pb = ttk.Progressbar(self, length=300, mode='determinate', style="Cyan.Horizontal.TProgressbar")
        self.pb.pack(pady=40)
        
        self.streamed_code = None 
        
        print("[BOOT] Starting background thread...")
        threading.Thread(target=self.run_setup_sequence, daemon=True).start()

    def run_setup_sequence(self):
        print("[THREAD] Setting up folders...")
        for folder in ["source_docs", "chat_storage"]:
            path = os.path.join(APP_DIR, folder)
            if not os.path.exists(path): os.makedirs(path)
                
        print("[THREAD] Creating shortcut...")
        self.create_desktop_shortcut()
        time.sleep(0.5) 
        
        print("[THREAD] Initiating Cloud Stream...")
        self.stream_core() 

    def create_desktop_shortcut(self):
        try:
            if not getattr(sys, 'frozen', False): return 
            target_exe = sys.executable
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            shortcut_path = os.path.join(desktop, "Policy Advisor 2026.lnk")
            
            if not os.path.exists(shortcut_path):
                vbs_code = f"""
                Set ws = WScript.CreateObject("WScript.Shell")
                Set s = ws.CreateShortcut("{shortcut_path}")
                s.TargetPath = "{target_exe}"
                s.WorkingDirectory = "{APP_DIR}"
                s.Description = "Launch Policy Advisor"
                s.Save
                """
                vbs_path = os.path.join(os.environ['TEMP'], 'create_sa_shortcut.vbs')
                with open(vbs_path, 'w') as f: f.write(vbs_code)
                os.system(f'cscript.exe //Nologo "{vbs_path}"')
                os.remove(vbs_path)
        except Exception: pass 

    def stream_core(self):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            headers = {'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'}
            
            print("[STREAM] Fetching version...")
            self.after(0, lambda: self.status.config(text="CHECKING CLOUD VERSION..."))
            url = GITHUB_RAW_BASE_URL + "version.json?t=" + str(time.time())
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                raw_json_text = resp.read().decode('utf-8')
            
            # --- THE REGEX FIX ---
            # This rips the version number out, completely ignoring JSON syntax rules
            match = re.search(r'["\']app_version["\']\s*:\s*([\d\.]+)', raw_json_text)
            if match:
                cloud_v = float(match.group(1))
            else:
                cloud_v = 7.0 # Failsafe

            print(f"[STREAM] Streaming v{cloud_v}...")
            self.after(0, lambda: self.status.config(text=f"STREAMING ENGINE V{cloud_v} TO RAM...", fg="#2ecc71"))
            core_url = GITHUB_RAW_BASE_URL + "app_core.py?t=" + str(time.time())
            core_req = urllib.request.Request(core_url, headers=headers)
            
            with urllib.request.urlopen(core_req, timeout=15, context=ctx) as resp:
                self.streamed_code = resp.read().decode('utf-8')

            print("[STREAM] Success. Launching...")
            self.after(0, self.launch_core)
            
        except Exception as e:
            print(f"[STREAM ERROR] {e}")
            self.after(0, lambda err=str(e): self.show_error(
                "CLOUD STREAM FAILED", 
                f"Could not stream the app from GitHub.\n\nERROR:\n{err}"
            ))

    def launch_core(self):
        print("[LAUNCH] Hiding bootloader...")
        self.status.config(text="IGNITING MEMORY ENGINE...", fg="#f8fafc")
        for i in range(101):
            self.pb['value'] = i
            self.update()
            time.sleep(0.01)
        
        self.withdraw()
        
        if self.streamed_code:
            try:
                print("[LAUNCH] Executing code in RAM...")
                globals()['VAULT_DIR'] = APP_DIR 
                exec(self.streamed_code, globals())
            except Exception as e:
                print(f"[EXEC ERROR] {e}")
                self.show_error("CRITICAL MEMORY FAILURE", traceback.format_exc())
        else:
            self.show_error("CRITICAL FAILURE", "Code stream was empty.")

    def show_error(self, title, msg):
        print(f"[ERROR POPUP] {title} - {msg}")
        messagebox.showerror(title, msg, parent=self)
        self.destroy()
        sys.exit(1)

if __name__ == "__main__":
    print("[MAIN] Starting Bootloader...")
    app = Bootloader()
    app.mainloop()
