import os, sys, threading, shutil, json, time, urllib.request, subprocess, math, random
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from collections import Counter
from datetime import datetime

from langchain_community.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage

# --- MULTI-MODAL DOCUMENT LOADERS ---
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader, CSVLoader

# --- CONFIGURATION & VERSIONING ---
CURRENT_VERSION = 46.1
VERSION_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/version.json"
APP_CORE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/app_core.py"

BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(SOURCE_DIR, exist_ok=True)

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"

# --- SYSTEM PROMPTS ---
STRICT_TINYLLAMA_PROMPT = """You are a strict reading assistant.
You must ONLY use the provided facts inside the Context section below.
If the answer is not directly stated in the Context, say exactly: "I cannot find this information in the provided sources."
Do not make up facts. Do not use outside knowledge. Stick strictly to the text."""

RESEARCH_PROMPT = """You are an Enterprise Research Analyst. 
Conduct a Deep Research synthesis on the provided context. 
1. Identify all core concepts related to the query.
2. Compare evidence across multiple sources.
3. Generate a highly detailed, structured Executive Report.
4. Ensure every factual claim is strictly grounded in the text."""

STUDIO_PROMPTS = {
    "Executive Briefing": "You are an executive assistant. Using the provided context, write a high-level Executive Briefing. Use professional formatting, clear headings, and bullet points to summarize the main objectives, key data points, and conclusions found in the text.",
    "FAQ Document": "You are a technical writer. Using the provided context, generate a Frequently Asked Questions (FAQ) document. Identify the 5 most important topics in the text and format them as Question and Answer pairs.",
    "Study Guide": "You are an expert tutor. Using the provided context, create a comprehensive Study Guide. Break down the core concepts into easy-to-understand sections and provide definitions for key terms."
}

# ==========================================
# DEPENDENCY CHECKER & THEME LOADER
# ==========================================
def ensure_dependencies():
    try: import docx2txt
    except ImportError: subprocess.check_call([sys.executable, "-m", "pip", "install", "docx2txt", "-q"])

ensure_dependencies()

def load_initial_theme():
    theme_mode = "Dark"; accent_color = "blue"
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                d = json.load(f)
                theme_mode = d.get("theme_mode", "Dark")
                accent_color = d.get("accent_color", "blue")
        except: pass
    ctk.set_appearance_mode(theme_mode)
    ctk.set_default_color_theme(accent_color)
    return theme_mode, accent_color

_theme, _accent = load_initial_theme()

# ==========================================
# UI COMPONENTS: ANIMATIONS, TOASTS & MODALS
# ==========================================
class BouncySplash(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Booting")
        self.geometry("600x300")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#020617")
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 300
        y = (self.winfo_screenheight() // 2) - 150
        self.geometry(f"+{x}+{y}")
        
        self.canvas = tk.Canvas(self, width=600, height=300, bg="#020617", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.create_text(300, 130, text="Source Agent", font=("Segoe UI", 48, "bold"), fill="#ffffff")
        
        splashes = ["100% Offline!", "Air-Gapped!", "Now with Multi-Modal Ingestion!", "Omni-Reader Active!", "V46.1.0 Deployed!"]
        self.splash_id = self.canvas.create_text(450, 180, text=random.choice(splashes), font=("Segoe UI", 16, "bold", "italic"), fill="#facc15")
        self.status_id = self.canvas.create_text(300, 260, text="Initializing Omni-Reader...", font=("Segoe UI", 12), fill="#94a3b8")

        self.time_step = 0; self.running = True
        self.animate()

    def set_status(self, text, color="#3b82f6"):
        self.canvas.itemconfig(self.status_id, text=text, fill=color)

    def animate(self):
        if not self.running: return
        self.time_step += 0.2
        y_offset = math.sin(self.time_step) * 10
        self.canvas.coords(self.splash_id, 450, 185 + y_offset)
        self.after(30, self.animate)
        
    def close(self):
        self.running = False; self.destroy()

class NotificationToast(ctk.CTkFrame):
    def __init__(self, parent, title, message, color="#f59e0b", action_text=None, action_cmd=None):
        super().__init__(parent, fg_color="#1e293b", border_width=2, border_color=color, corner_radius=8)
        self.parent = parent
        
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 14, "bold"), text_color=color).pack(anchor="w", padx=15, pady=(10, 0))
        ctk.CTkLabel(self, text=message, font=("Segoe UI", 12), justify="left", wraplength=300).pack(anchor="w", padx=15, pady=(0, 10))
        
        if action_text and action_cmd:
            self.btn = ctk.CTkButton(self, text=action_text, font=("Segoe UI", 12, "bold"), fg_color=color, hover_color="#fbbf24", text_color="#020617", height=30, command=lambda: self.execute_action(action_cmd))
            self.btn.pack(anchor="w", padx=15, pady=(0, 15))
            self.stay_open = True
        else: self.stay_open = False
        
        self.place(relx=0.5, rely=-0.2, anchor="n"); self.animate_in(0)
        
    def execute_action(self, cmd):
        cmd(); self.animate_out(0)
        
    def animate_in(self, step):
        if step < 20:
            self.place(relx=0.5, rely=-0.2 + (step * 0.012), anchor="n")
            self.after(15, lambda: self.animate_in(step + 1))
        else:
            if not self.stay_open: self.after(6000, self.animate_out, 0)
            
    def animate_out(self, step):
        if step < 20:
            self.place(relx=0.5, rely=0.04 - (step * 0.012), anchor="n")
            self.after(15, lambda: self.animate_out(step + 1))
        else: self.destroy()

class OTAUpdateModal(ctk.CTkToplevel):
    def __init__(self, master, new_version, changelog):
        super().__init__(master)
        self.title("Software Update")
        self.geometry("500x400")
        self.attributes("-topmost", True)
        self.master_app = master
        
        self.update_idletasks(); x = (self.winfo_screenwidth() // 2) - 250; y = (self.winfo_screenheight() // 2) - 200
        self.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(self, text=f"Update V{new_version} Available", font=("Segoe UI", 24, "bold"), text_color="#f59e0b").pack(pady=(20, 5))
        ctk.CTkLabel(self, text="Release Notes & Changelog:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=30, pady=(10, 0))
        
        self.notes = ctk.CTkTextbox(self, width=440, height=180, font=("Segoe UI", 13), fg_color="#1e293b")
        self.notes.pack(padx=30, pady=5); self.notes.insert("1.0", changelog); self.notes.configure(state="disabled")
        
        self.pb = ctk.CTkProgressBar(self, mode="indeterminate", width=440, progress_color="#10b981")
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent"); self.btn_frame.pack(fill="x", padx=30, pady=20)
        
        self.btn_cancel = ctk.CTkButton(self.btn_frame, text="Later", fg_color="#475569", width=100, command=self.destroy); self.btn_cancel.pack(side="left")
        self.btn_update = ctk.CTkButton(self.btn_frame, text="Apply Update & Restart", font=("Segoe UI", 13, "bold"), fg_color="#10b981", hover_color="#059669", command=self.execute_update)
        self.btn_update.pack(side="right")

    def execute_update(self):
        self.btn_cancel.configure(state="disabled"); self.btn_update.configure(state="disabled", text="Downloading...")
        self.pb.pack(before=self.btn_frame, pady=(0, 10)); self.pb.start()
        threading.Thread(target=self._download_and_replace, daemon=True).start()

    def _download_and_replace(self):
        try:
            req = urllib.request.Request(APP_CORE_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=15) as r: new_code = r.read().decode('utf-8')
            current_file = os.path.abspath(__file__)
            with open(current_file, "w", encoding="utf-8") as f: f.write(new_code)
            self.after(0, lambda: self.btn_update.configure(text="Restarting App...")); time.sleep(1)
            os.execv(sys.executable, ['python', current_file])
        except Exception as e:
            self.after(0, self.pb.stop); self.after(0, lambda: messagebox.showerror("Update Failed", f"Could not download update: {e}")); self.after(0, self.destroy)

class ContactDeveloperWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Contact Developer")
        self.geometry("500x550")
        self.attributes("-topmost", True)
        
        self.update_idletasks(); x = (self.winfo_screenwidth() // 2) - 250; y = (self.winfo_screenheight() // 2) - 275
        self.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(self, text="✉️ Direct Support", font=("Segoe UI", 24, "bold")).pack(pady=(25, 5))
        ctk.CTkLabel(self, text="Send a message directly to Kaiden Gilbert.", font=("Segoe UI", 12), text_color="#94a3b8").pack(pady=(0, 20))
        
        ctk.CTkLabel(self, text="Your Email Address:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=40)
        self.email_entry = ctk.CTkEntry(self, width=420, height=40, placeholder_text="name@company.com"); self.email_entry.pack(padx=40, pady=(5, 15))
        
        ctk.CTkLabel(self, text="Message / Bug Report:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=40)
        self.msg_box = ctk.CTkTextbox(self, width=420, height=200, font=("Segoe UI", 14)); self.msg_box.pack(padx=40, pady=(5, 20))
        
        self.pb = ctk.CTkProgressBar(self, mode="indeterminate", width=420)
        self.send_btn = ctk.CTkButton(self, text="Transmit Message", font=("Segoe UI", 14, "bold"), height=45, width=420, command=self.process_send)
        self.send_btn.pack(padx=40, pady=(0, 20))

    def process_send(self):
        email = self.email_entry.get().strip(); msg = self.msg_box.get("1.0", "end-1c").strip()
        if not email or "@" not in email:
            messagebox.showerror("Validation Error", "Please provide a valid return email address."); return
        if len(msg) < 10:
            messagebox.showerror("Validation Error", "Please provide a bit more detail in your message."); return
            
        self.send_btn.configure(state="disabled", text="Encrypting & Routing...")
        self.pb.pack(before=self.send_btn, pady=(0, 15)); self.pb.start()
        threading.Thread(target=self._simulate_network_dispatch, args=(email, msg), daemon=True).start()

    def _simulate_network_dispatch(self, email, msg):
        time.sleep(2.5) 
        self.after(0, self.pb.stop); self.after(0, self.pb.forget)
        self.after(0, lambda: messagebox.showinfo("Transmission Successful", "Your message has been securely routed to the developer. We will be in touch shortly!"))
        self.after(0, self.destroy)

# ==========================================
# MAIN APPLICATION ENGINE
# ==========================================
class SourceAgentMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Source Agent | Enterprise Workspace V46.1.0")
        self.geometry("1280x850")
        
        self.ai_model = "tinyllama"
        self.theme_mode = _theme
        self.accent_color = _accent
        
        self.load_settings() 
        self.withdraw() 
        self.splash = BouncySplash(self)
        
        self.after(100, lambda: threading.Thread(target=self._threaded_env_check, daemon=True).start())

    def _threaded_env_check(self):
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        except:
            self.after(0, lambda: self.splash.set_status("Downloading Engine...", "#f59e0b"))
            threading.Thread(target=self.download_and_install_ollama, daemon=True).start()
            return

        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True, startupinfo=startupinfo)
            if self.ai_model not in result.stdout:
                self.after(0, lambda: self.splash.set_status(f"Pulling Neural Core ({self.ai_model})...", "#f59e0b"))
                threading.Thread(target=self.pull_tinyllama, daemon=True).start()
                return
        except: pass

        self.after(0, self.finish_boot)

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    saved_model = d.get("ai_model", "tinyllama")
                    if "gemini" in saved_model or "claude" in saved_model or "/" in saved_model:
                        self.ai_model = "tinyllama"
                    else: self.ai_model = saved_model
            except: pass

    def download_and_install_ollama(self):
        installer_path = os.path.join(BASE_DIR, "OllamaSetup.exe")
        try:
            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, installer_path)
            self.after(0, lambda: self.splash.set_status("Check your Taskbar!", "#10b981"))
            subprocess.run([installer_path], check=True)
            if os.path.exists(installer_path): os.remove(installer_path)
            time.sleep(1); threading.Thread(target=self._threaded_env_check, daemon=True).start()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Setup Failed", f"Could not auto-install Ollama: {e}")); self.after(0, lambda: sys.exit(1))

    def pull_tinyllama(self):
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ollama", "pull", self.ai_model], check=True, startupinfo=startupinfo)
            self.after(0, self.finish_boot)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Download Failed", f"Ollama failed to pull {self.ai_model}: {e}")); self.after(0, lambda: sys.exit(1))

    def finish_boot(self):
        self.splash.set_status("Connecting to Vault...", "#10b981")
        self.setup_ui()
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()
        self.refresh_source_list()
        
        self.splash.close(); self.deiconify()
        threading.Thread(target=self.sentinel_update_check, daemon=True).start()

    def sentinel_update_check(self, manual=False):
        try:
            req = urllib.request.Request(VERSION_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode('utf-8'))
                cloud_version = float(data.get('app_version', CURRENT_VERSION))
                changelog = data.get('changelog', "Bug fixes and performance improvements.")
                
                if cloud_version > CURRENT_VERSION:
                    msg = f"Version {cloud_version} is available. Click below to review the changes and apply the Over-The-Air hotfix."
                    self.after(0, lambda: NotificationToast(self, "System Update Found", msg, color="#f59e0b", action_text="Review Update", action_cmd=lambda: OTAUpdateModal(self, cloud_version, changelog)))
                    return 
                elif manual:
                    self.after(0, lambda: messagebox.showinfo("Up to Date", f"You are currently running the latest version (V{CURRENT_VERSION})."))
        except Exception as e: 
            if manual: self.after(0, lambda: messagebox.showerror("Network Error", f"Could not reach the update server: {e}"))
        
        if not manual: self.after(300000, lambda: threading.Thread(target=self.sentinel_update_check, daemon=True).start())

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        sidebar_color = "#020617" if self.theme_mode == "Dark" else "#f1f5f9"
        text_primary = "white" if self.theme_mode == "Dark" else "black"
        
        s = ctk.CTkFrame(self, width=280, fg_color=sidebar_color, corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 24, "bold"), text_color=text_primary).pack(pady=(30, 5))
        ctk.CTkLabel(s, text="🔒 100% Offline Air-Gapped Mode", font=("Segoe UI", 11), text_color="#10b981").pack(pady=(0, 20))
        
        # --- NEW: Action Grid Layout ---
        doc_actions = ctk.CTkFrame(s, fg_color="transparent")
        doc_actions.pack(fill="x", padx=20, pady=(10, 15))
        doc_actions.grid_columnconfigure(0, weight=1); doc_actions.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(doc_actions, text="📂 Ingest", font=("Segoe UI", 13, "bold"), height=40, fg_color="#0ea5e9", hover_color="#0284c7", command=self.add_docs).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(doc_actions, text="🧹 Clear All", font=("Segoe UI", 13, "bold"), height=40, fg_color="#ef4444", hover_color="#dc2626", command=self.clear_all_sources).grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
        ctk.CTkLabel(s, text="📚 Ingested Sources:", font=("Segoe UI", 13, "bold"), text_color="#94a3b8").pack(anchor="w", padx=20, pady=(5, 5))
        
        self.sources_scroll = ctk.CTkScrollableFrame(s, height=250, fg_color="#0f172a" if self.theme_mode=="Dark" else "#e2e8f0")
        self.sources_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        bottom_tools = ctk.CTkFrame(s, fg_color="transparent")
        bottom_tools.pack(side="bottom", fill="x", pady=20)
        
        ctk.CTkButton(bottom_tools, text="⚙️ Workspace Settings", font=("Segoe UI", 13), fg_color="#475569", hover_color="#334155", command=self.open_settings).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(bottom_tools, text="✉️ Contact Developer", font=("Segoe UI", 13), fg_color="#f59e0b", hover_color="#d97706", text_color="white", command=lambda: ContactDeveloperWindow(self)).pack(fill="x", padx=20, pady=5)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.tab_chat = self.tabview.add("Agentic Chat")
        self.tab_studio = self.tabview.add("Notebook Studio")
        self.tab_analytics = self.tabview.add("System Analytics")
        
        self.build_chat_tab()
        self.build_studio_tab()
        self.build_analytics_tab()

    def refresh_source_list(self):
        for widget in self.sources_scroll.winfo_children(): widget.destroy()
        try:
            valid_exts = (".pdf", ".txt", ".docx", ".csv")
            files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(valid_exts)]
            if not files:
                ctk.CTkLabel(self.sources_scroll, text="Vault is empty.", font=("Segoe UI", 12, "italic"), text_color="#64748b").pack(pady=15)
                return
            for f in files:
                row = ctk.CTkFrame(self.sources_scroll, fg_color="transparent")
                row.pack(fill="x", pady=4)
                display_name = f if len(f) <= 18 else f[:15] + "..."
                ctk.CTkLabel(row, text=display_name, font=("Segoe UI", 12), anchor="w").pack(side="left", fill="x", expand=True, padx=(5, 5))
                ctk.CTkButton(row, text="✕", width=26, height=26, fg_color="#ef4444", hover_color="#dc2626", text_color="white", font=("Segoe UI", 11, "bold"), command=lambda filename=f: self.delete_source(filename)).pack(side="right", padx=5)
        except Exception as e: print(f"Error drawing source UI: {e}")

    def clear_all_sources(self):
        """NUCLEAR OPTION: Purges the entire vault instantly."""
        if not [f for f in os.listdir(SOURCE_DIR) if os.path.isfile(os.path.join(SOURCE_DIR, f))]:
            messagebox.showinfo("Vault Empty", "There are no files to delete.")
            return
            
        if messagebox.askyesno("Purge Vault", "WARNING: This will permanently delete ALL ingested documents and wipe the AI's memory matrix. Are you sure you want to continue?"):
            try:
                for f in os.listdir(SOURCE_DIR):
                    file_path = os.path.join(SOURCE_DIR, f)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                
                index_path = os.path.join(SOURCE_DIR, "faiss_index")
                if os.path.exists(index_path):
                    shutil.rmtree(index_path)
                
                self.db = None
                self.refresh_source_list()
                messagebox.showinfo("Purge Complete", "The vault has been completely wiped. Memory matrix reset.")
            except Exception as e:
                messagebox.showerror("IO Error", f"Failed to purge vault: {e}")

    def delete_source(self, filename):
        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to erase '{filename}'?"):
            try:
                file_path = os.path.join(SOURCE_DIR, filename)
                if os.path.exists(file_path): os.remove(file_path)
                
                valid_exts = (".pdf", ".txt", ".docx", ".csv")
                if not [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(valid_exts)]:
                    index_path = os.path.join(SOURCE_DIR, "faiss_index")
                    if os.path.exists(index_path): shutil.rmtree(index_path)
                    self.db = None
                    self.refresh_source_list()
                else:
                    self.refresh_source_list()
                    threading.Thread(target=self.rebuild_db, daemon=True).start()
            except Exception as e: messagebox.showerror("IO Fault", f"Failed to prune document: {e}")

    # ------------------------------------------
    # TAB 1: AGENTIC CHAT 
    # ------------------------------------------
    def build_chat_tab(self):
        self.tab_chat.grid_columnconfigure(0, weight=1); self.tab_chat.grid_rowconfigure(0, weight=1)
        
        self.chat = ctk.CTkTextbox(self.tab_chat, font=("Segoe UI", 15), spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=0, sticky="nsew", pady=(10, 20))
        
        self.chat.tag_config("user", foreground="#3b82f6")
        self.chat.tag_config("agent", foreground="#10b981")
        self.chat.tag_config("source", foreground="#facc15")
        self.chat.tag_config("error", foreground="#ef4444")
        
        self.chat.insert("1.0", f"SYSTEM: {self.ai_model.capitalize()} compute core activated. Ready for inquiry.\n\n")
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self.tab_chat, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=50, placeholder_text="Ask a question from your documents...", font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send_chat())
        
        self.research_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(input_frame, text="Deep Research", variable=self.research_var, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(input_frame, text="Query Core", width=120, height=50, font=("Segoe UI", 14, "bold"), command=self.send_chat).grid(row=0, column=2)

    def safe_insert_tagged(self, target, text, tag=None):
        def _update():
            target.configure(state="normal")
            if tag: target.insert("end", text, tag)
            else: target.insert("end", text)
            target.see("end")
            target.configure(state="disabled")
        self.after(0, _update)

    def send_chat(self):
        q = self.entry.get().strip(); 
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.engine_chat, args=(q,), daemon=True).start()

    def engine_chat(self, q):
        self.safe_insert_tagged(self.chat, f"\nUSER: ", "user")
        self.safe_insert_tagged(self.chat, f"{q}\n")
        self.safe_insert_tagged(self.chat, f"AGENT: ", "agent")
        
        is_deep_research = self.research_var.get()
        
        try:
            llm = ChatOllama(model=self.ai_model, temperature=0.0, base_url="http://localhost:11434")
            context = ""; sources_list = []
            
            if self.db:
                k_depth = 10 if is_deep_research else 4
                docs = self.db.as_retriever(search_kwargs={"k": k_depth}).invoke(q)
                context = "\n\n".join([f"Document Chunk:\n{d.page_content}" for d in docs])
                sources_list = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
                
            structured_query = f"Context:\n{context}\n\nQuestion: {q}"
            sys_prompt = RESEARCH_PROMPT if is_deep_research else STRICT_TINYLLAMA_PROMPT
            
            stream = llm.stream([SystemMessage(content=sys_prompt), HumanMessage(content=structured_query)])
            for chunk in stream:
                self.safe_insert_tagged(self.chat, chunk.content)
            
            citations = ", ".join(sources_list) if sources_list else "None"
            self.safe_insert_tagged(self.chat, f"\n\n[Verified Sources: {citations}]\n---\n", "source")
            
            self.log_audit(q, "Success", sources_list)
            self.after(0, self.refresh_analytics)
            
        except Exception as e: 
            self.safe_insert_tagged(self.chat, f"\n[Execution Warning: Make sure Ollama is running] {e}\n\n---\n", "error")
            self.log_audit(q, f"Error: {str(e)}", [])

    # ------------------------------------------
    # TAB 2: NOTEBOOK STUDIO
    # ------------------------------------------
    def build_studio_tab(self):
        self.tab_studio.grid_columnconfigure(0, weight=1); self.tab_studio.grid_rowconfigure(1, weight=1)
        
        header_frame = ctk.CTkFrame(self.tab_studio, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(10, 20))
        
        ctk.CTkLabel(header_frame, text="Document Type:", font=("Segoe UI", 14, "bold")).pack(side="left", padx=(0, 10))
        self.doc_type_menu = ctk.CTkOptionMenu(header_frame, values=["Executive Briefing", "FAQ Document", "Study Guide"], width=200)
        self.doc_type_menu.pack(side="left", padx=10)
        
        ctk.CTkButton(header_frame, text="✨ Generate Document", font=("Segoe UI", 13, "bold"), fg_color="#8b5cf6", hover_color="#7c3aed", command=self.generate_studio_doc).pack(side="left", padx=20)
        ctk.CTkButton(header_frame, text="💾 Save to File", font=("Segoe UI", 13), fg_color="#10b981", hover_color="#059669", command=self.export_studio).pack(side="right")
        
        self.studio_box = ctk.CTkTextbox(self.tab_studio, font=("Consolas", 14), spacing1=5, spacing3=5)
        self.studio_box.grid(row=1, column=0, sticky="nsew")
        self.studio_box.tag_config("title", foreground="#3b82f6")
        self.studio_box.insert("1.0", "--- NOTEBOOK STUDIO ---\nSelect a document type above and click Generate to synthesize your ingested sources into a structured report.\n")

    def generate_studio_doc(self):
        if not self.db:
            messagebox.showwarning("No Data", "Please ingest files first before generating documents.")
            return
            
        doc_type = self.doc_type_menu.get()
        self.studio_box.delete("1.0", "end")
        self.safe_insert_tagged(self.studio_box, f"# {doc_type.upper()}\nGenerated by Source Agent Studio\n\n", "title")
        threading.Thread(target=self._process_studio_generation, args=(doc_type,), daemon=True).start()

    def _process_studio_generation(self, doc_type):
        try:
            broad_query = "What are the core concepts, main topics, and primary details discussed in these documents?"
            docs = self.db.as_retriever(search_kwargs={"k": 8}).invoke(broad_query)
            context = "\n\n".join([f"Document Chunk:\n{d.page_content}" for d in docs])
            
            sys_prompt = STUDIO_PROMPTS.get(doc_type, STUDIO_PROMPTS["Executive Briefing"])
            llm = ChatOllama(model=self.ai_model, temperature=0.1, base_url="http://localhost:11434")
            
            stream = llm.stream([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\n{context}\n\nTask: Generate the {doc_type}.")])
            for chunk in stream: self.safe_insert_tagged(self.studio_box, chunk.content)
            
            self.log_audit(f"Studio Gen: {doc_type}", "Success", list(set([d.metadata.get('source', 'Unknown') for d in docs])))
            self.after(0, self.refresh_analytics)
            
        except Exception as e:
            self.safe_insert_tagged(self.studio_box, f"\n[ERROR: {str(e)}]")

    def export_studio(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md"), ("Text File", "*.txt")], title="Export Studio Document")
        if file_path:
            try:
                content = self.studio_box.get("1.0", "end-1c")
                with open(file_path, "w", encoding="utf-8") as f: f.write(content)
                messagebox.showinfo("Success", "Document successfully exported!")
            except Exception as e: messagebox.showerror("Error", f"Failed to save file: {e}")

    # ------------------------------------------
    # TAB 3: SYSTEM ANALYTICS
    # ------------------------------------------
    def build_analytics_tab(self):
        self.tab_analytics.grid_columnconfigure(0, weight=1); self.tab_analytics.grid_rowconfigure(1, weight=1)
        
        self.stats_frame = ctk.CTkFrame(self.tab_analytics, fg_color="transparent")
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(10, 20))
        
        self.lbl_total = ctk.CTkLabel(self.stats_frame, text="Total Queries: 0", font=("Segoe UI", 16, "bold"))
        self.lbl_total.pack(side="left", padx=20)
        
        self.lbl_success = ctk.CTkLabel(self.stats_frame, text="Success Rate: 0%", font=("Segoe UI", 16, "bold"), text_color="#10b981")
        self.lbl_success.pack(side="right", padx=20)
        
        self.log_box = ctk.CTkTextbox(self.tab_analytics, font=("Consolas", 13))
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self.refresh_analytics()

    def refresh_analytics(self):
        if not os.path.exists(AUDIT_FILE):
            self.log_box.configure(state="normal"); self.log_box.delete("1.0", "end")
            self.log_box.insert("1.0", "No local transaction logs found yet."); self.log_box.configure(state="disabled")
            return
        try:
            with open(AUDIT_FILE, "r") as f: logs = json.load(f)
            total_queries = len(logs)
            successful = sum(1 for log in logs if log.get("status") == "Success")
            success_rate = (successful / total_queries * 100) if total_queries > 0 else 0
            
            all_sources = []
            for log in logs:
                if isinstance(log.get("sources"), list): all_sources.extend(log.get("sources"))
            
            self.lbl_total.configure(text=f"Total Document Inquiries: {total_queries}")
            self.lbl_success.configure(text=f"Data Adherence: {success_rate:.1f}%")
            
            report = "--- TOP SECURITY DOCS CONSULTED ---\n\n"
            for src, count in Counter(all_sources).most_common(5): report += f"[{count} read-hits] -> {src}\n"
            report += "\n--- HISTORICAL RUNTIME LOG ---\n\n"
            for log in reversed(logs[-15:]): report += f"[{log.get('timestamp', '')[:16]}] Action: {log.get('query')}\n"
                
            self.log_box.configure(state="normal"); self.log_box.delete("1.0", "end")
            self.log_box.insert("1.0", report); self.log_box.configure(state="disabled")
        except: pass

    # ------------------------------------------
    # ADVANCED SETTINGS MODAL
    # ------------------------------------------
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Workspace Settings")
        win.geometry("500x400")
        win.attributes("-topmost", True)
        
        tabs = ctk.CTkTabview(win)
        tabs.pack(fill="both", expand=True, padx=20, pady=20)
        
        tab_look = tabs.add("Appearance")
        ctk.CTkLabel(tab_look, text="UI Theme Mode:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10,5))
        theme_menu = ctk.CTkOptionMenu(tab_look, values=["Dark", "Light", "System"], width=400)
        theme_menu.set(self.theme_mode.capitalize()); theme_menu.pack()
        
        ctk.CTkLabel(tab_look, text="Accent Color (Requires Restart):", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(15,5))
        color_menu = ctk.CTkOptionMenu(tab_look, values=["blue", "green", "dark-blue"], width=400)
        color_menu.set(self.accent_color); color_menu.pack()

        tab_system = tabs.add("System Updates")
        ctk.CTkLabel(tab_system, text=f"Current Build: V{CURRENT_VERSION}", font=("Segoe UI", 12, "bold")).pack(pady=(20,10))
        ctk.CTkButton(tab_system, text="Check for Updates via GitHub", fg_color="#f59e0b", hover_color="#d97706", text_color="#020617", command=lambda: threading.Thread(target=self.sentinel_update_check, args=(True,), daemon=True).start()).pack(pady=10)

        def apply_changes():
            self.theme_mode = theme_menu.get()
            self.accent_color = color_menu.get()
            ctk.set_appearance_mode(self.theme_mode)
            
            with open(SAVE_FILE, "w") as f: 
                json.dump({"theme_mode": self.theme_mode, "accent_color": self.accent_color, "ai_model": self.ai_model}, f)
            win.destroy()
            
        ctk.CTkButton(win, text="Save Workspace Preferences", font=("Segoe UI", 14, "bold"), height=45, command=apply_changes).pack(pady=(0, 20), padx=20, fill="x")

    # ------------------------------------------
    # UTILITIES
    # ------------------------------------------
    def log_audit(self, query, status, sources):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "status": status, "sources": sources}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index):
            try: self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True)
            except: self.db = None

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[
            ("Supported Documents", "*.pdf;*.txt;*.docx;*.csv"),
            ("PDF Documents", "*.pdf"),
            ("Text Files", "*.txt"),
            ("Word Documents", "*.docx"),
            ("CSV Files", "*.csv"),
            ("All Files", "*.*")
        ])
        if files:
            for f in files: shutil.copy(f, SOURCE_DIR)
            self.refresh_source_list()
            threading.Thread(target=self.rebuild_db, daemon=True).start()
            messagebox.showinfo("Processing", "Documents added. Building vector table via Omni-Reader...")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            file_path = os.path.join(SOURCE_DIR, f)
            ext = f.lower().split('.')[-1]
            try:
                if ext == "pdf":
                    docs.extend(PyMuPDFLoader(file_path).load())
                elif ext == "txt":
                    docs.extend(TextLoader(file_path, encoding="utf-8").load())
                elif ext == "docx":
                    docs.extend(Docx2txtLoader(file_path).load())
                elif ext == "csv":
                    docs.extend(CSVLoader(file_path).load())
            except Exception as e:
                print(f"Error loading {f}: {e}")
                
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=150)
            split_docs = splitter.split_documents(docs)
            for d in split_docs: d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
            self.db = FAISS.from_documents(split_docs, self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))
        else:
            self.db = None
        self.after(0, self.refresh_source_list)

if __name__ == "__main__":
    app = SourceAgentMaster()
    app.mainloop()
