import os, sys, subprocess, time, uuid, threading, json, datetime, urllib.request, math
import tkinter as tk 

# --- BOOTSTRAP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe") if os.name == 'nt' else os.path.join(BASE_DIR, ".venv", "bin", "python")

if sys.executable.lower() != VENV_PYTHON.lower() and os.path.exists(VENV_PYTHON):
    subprocess.Popen([VENV_PYTHON] + sys.argv)
    sys.exit()

import shutil
import customtkinter as ctk
from tkinter import filedialog
from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage") 

for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# --- APP CONFIGURATION ---
APP_VERSION = "4.6" 
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

# --- UI SETTINGS ---
BG_SIDEBAR = "#050508"    
BG_SURFACE = "#0f0f1a"    
ACCENT_PRIMARY = "#6366f1" 
ACCENT_HOVER = "#4f46e5"  
TEXT_MAIN = "#f8fafc"     
TEXT_MUTED = "#64748b"    
FONT_MAIN = "Segoe UI"

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"SourceAgent Pro v{APP_VERSION} - Live Cloud Sync")
        self.geometry("1300x850")
        
        self.cached_vectorstore = None
        self.cached_docs_hash = ""
        self.update_alert_shown = False # Prevent spamming alerts
        
        self.load_save_data()
        ctk.set_appearance_mode(self.app_theme)
        self.draw_dynamic_background()

        if self.user_name: self.show_welcome_back_screen()
        else: self.show_boot_screen()

        # START THE REAL-TIME PING ENGINE
        self.start_cloud_heartbeat()

    # ==========================================
    # 0. REAL-TIME CLOUD HEARTBEAT
    # ==========================================
    def start_cloud_heartbeat(self):
        # Initial check after 5 seconds, then every 5 minutes
        self.after(5000, self.perform_background_ping)

    def perform_background_ping(self):
        if not self.update_alert_shown:
            threading.Thread(target=self.check_for_updates, kwargs={"manual": False}, daemon=True).start()
        # Schedule next ping in 5 minutes (300,000 ms)
        self.after(300000, self.perform_background_ping)

    # ==========================================
    # 1. VISUAL ENGINE (NEBULA)
    # ==========================================
    def draw_dynamic_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg="#020205")
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.orbs = [
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#1e1b4b"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#312e81"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#1e1b4b")
        ]
        self.anim_step = 0
        self.animate_bg()

    def animate_bg(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w > 100:
            self.anim_step += 0.012
            x1 = (math.sin(self.anim_step) * (w/3)) + (w/2)
            y1 = (math.cos(self.anim_step * 0.7) * (h/3)) + (h/2)
            self.bg_canvas.coords(self.orbs[0], x1-500, y1-500, x1+500, y1+500)
            x2 = (math.cos(self.anim_step * 1.1) * (w/4)) + (w/2)
            y2 = (math.sin(self.anim_step * 0.8) * (h/4)) + (h/2)
            self.bg_canvas.coords(self.orbs[1], x2-400, y2-400, x2+400, y2+400)
        self.bg_canvas.lower("all")
        self.after(40, self.animate_bg)

    # ==========================================
    # 2. UPDATE SYSTEM
    # ==========================================
    def check_for_updates(self, manual=False):
        try:
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + "version.json", headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                cloud_v = float(data.get("app_version", 0.0))
            
            if cloud_v > float(APP_VERSION):
                if manual: self.update_status_lbl.configure(text=f"New version v{cloud_v} found!", text_color="#2ecc71")
                else: 
                    self.update_alert_shown = True
                    self.after(0, lambda: self.show_notification(f"🚀 Live Update Detected: v{cloud_v} is ready!"))
            else:
                if manual: self.update_status_lbl.configure(text="System up to date.", text_color=TEXT_MUTED)
        except: pass

    def show_notification(self, msg):
        banner = ctk.CTkFrame(self, fg_color=ACCENT_PRIMARY, corner_radius=12)
        banner.place(relx=0.5, rely=0.06, anchor="center")
        ctk.CTkLabel(banner, text=msg, font=(FONT_MAIN, 13, "bold"), text_color="white").pack(side="left", padx=20, pady=12)
        ctk.CTkButton(banner, text="Dismiss", width=60, fg_color="transparent", border_color="white", border_width=1, command=banner.destroy).pack(side="right", padx=15)

    # ==========================================
    # 3. ANTI-HALLUCINATION WORKFLOW
    # ==========================================
    def run_agentic_workflow(self, query):
        try:
            self.after(0, lambda: self.status_indicator.configure(text="🔍 Searching Knowledge Base...", text_color=ACCENT_PRIMARY))
            vs = self.get_cached_vectorstore()
            context = "No documents provided."
            if vs:
                relevant_docs = vs.as_retriever(search_kwargs={"k": 5}).invoke(query)
                context = "\n\n".join([f"[Doc: {d.metadata.get('source')}] {d.page_content}" for d in relevant_docs])

            # STAGE 1: THE RESEARCHER (Fact Extractor)
            self.after(0, lambda: self.status_indicator.configure(text="🧠 Verifying Facts (No-Hallucination)...", text_color="#2ecc71"))
            facts = self.researcher_engine.invoke(f"Extract raw facts from: {context}\nTo answer: {query}\nIf not found, say [NO_DATA].").content

            # STAGE 2: THE EDITOR (Final Polish)
            self.after(0, lambda: self.status_indicator.configure(text="✨ Streaming Grounded Response...", text_color="#ffffff"))
            self.after(0, lambda: self.chat_display.configure(state="normal"))
            self.after(0, lambda: self.chat_display.insert("end", "🤖 Agent:\n"))
            
            full_resp = ""
            for chunk in self.editor_engine.stream(f"Answer query: {query}\nUse ONLY these verified facts: {facts}\nIf facts say [NO_DATA], inform the user honestly."):
                token = self.format_ui_text(chunk.content)
                full_resp += chunk.content
                self.after(0, lambda t=token: self.chat_display.insert("end", t))
                self.after(0, lambda: self.chat_display.see("end"))

            FileChatMessageHistory(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json")).add_user_message(query)
            FileChatMessageHistory(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json")).add_ai_message(full_resp)

            self.after(0, lambda: self.chat_display.insert("end", "\n\n"))
            self.after(0, lambda: self.chat_display.configure(state="disabled"))
            self.after(0, lambda: self.status_indicator.configure(text="🟢 System Ready", text_color=TEXT_MUTED))
        except Exception as e:
            self.after(0, lambda: self.status_indicator.configure(text=f"❌ Error: {str(e)}", text_color="#e74c3c"))
        self.after(0, lambda: self.user_input.configure(state="normal"))

    # --- STANDARD APP METHODS (HISTORY, UI BUILDER, ETC) ---
    def load_save_data(self):
        self.user_name, self.current_session_id, self.session_history, self.app_theme = None, str(uuid.uuid4()), [], "Dark"
        if os.path.exists(SAVE_FILE):
            try:
                data = json.load(open(SAVE_FILE, "r"))
                self.user_name, self.current_session_id, self.session_history, self.app_theme = data.get("user_name"), data.get("session_id"), data.get("history_list", []), data.get("app_theme", "Dark")
            except: pass

    def save_current_state(self):
        json.dump({"user_name": self.user_name, "session_id": self.current_session_id, "history_list": self.session_history, "app_theme": self.app_theme}, open(SAVE_FILE, "w"), indent=4)

    def show_boot_screen(self):
        self.boot_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.boot_frame.pack(fill="both", expand=True)
        box = ctk.CTkFrame(self.boot_frame, fg_color=BG_SURFACE, corner_radius=20, border_width=1, border_color="#1a1a2e")
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="SourceAgent Pro", font=(FONT_MAIN, 32, "bold"), text_color=ACCENT_PRIMARY).pack(pady=(50, 10), padx=60)
        self.name_entry = ctk.CTkEntry(box, placeholder_text="Name...", width=320, height=50)
        self.name_entry.pack(pady=35, padx=50)
        ctk.CTkButton(box, text="Connect", height=45, command=self.first_time_launch).pack(pady=(0, 50))

    def first_time_launch(self):
        if self.name_entry.get().strip(): self.user_name = self.name_entry.get().strip(); self.save_current_state()
        self.boot_frame.destroy(); self.show_welcome_back_screen()

    def show_welcome_back_screen(self):
        f = ctk.CTkFrame(self, fg_color="transparent"); f.pack(fill="both", expand=True)
        ctk.CTkLabel(f, text=f"Welcome back, {self.user_name}.", font=(FONT_MAIN, 42, "bold"), text_color="white").place(relx=0.5, rely=0.5, anchor="center")
        self.after(1500, lambda: [f.destroy(), self.launch_workspace()])

    def launch_workspace(self):
        self.build_main_ui(); threading.Thread(target=self.setup_ai, daemon=True).start()

    def build_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=320, fg_color=BG_SIDEBAR); self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="📚 SourceAgent", font=(FONT_MAIN, 22, "bold")).pack(pady=30, padx=20, anchor="w")
        ctk.CTkButton(self.sidebar, text="+ New Session", fg_color=ACCENT_PRIMARY, command=self.start_new_session).pack(fill="x", padx=20, pady=10)
        self.history_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=200); self.history_list.pack(fill="x", padx=10, pady=10)
        self.source_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=150); self.source_list.pack(fill="x", padx=10, pady=10)
        
        f_btns = ctk.CTkFrame(self.sidebar, fg_color="transparent"); f_btns.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(f_btns, text="Upload", width=125, command=self.upload_files, fg_color=BG_SURFACE).pack(side="left", expand=True)
        ctk.CTkButton(f_btns, text="Manage", width=125, command=self.open_manage_sources_menu, fg_color="transparent", border_width=1, border_color="#e74c3c").pack(side="right", expand=True)
        ctk.CTkButton(self.sidebar, text="Settings", command=self.open_settings_menu, fg_color="transparent", border_width=1).pack(side="bottom", fill="x", padx=20, pady=20)

        self.chat_container = ctk.CTkFrame(self, fg_color=BG_SURFACE, corner_radius=15, border_width=1, border_color="#1a1a2e")
        self.chat_container.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
        self.chat_container.grid_rowconfigure(0, weight=1); self.chat_container.grid_columnconfigure(0, weight=1)
        self.chat_display = ctk.CTkTextbox(self.chat_container, state="disabled", font=(FONT_MAIN, 16), wrap="word", fg_color="transparent")
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=15, pady=20)
        self.status_indicator = ctk.CTkLabel(self.chat_container, text="🟢 System Ready", text_color=TEXT_MUTED, font=(FONT_MAIN, 12, "italic"))
        self.status_indicator.grid(row=1, column=0, sticky="w", padx=20, pady=(0,8))
        
        w_in = ctk.CTkFrame(self.chat_container, fg_color="#050508", corner_radius=12); w_in.grid(row=2, column=0, sticky="ew", padx=15, pady=15); w_in.grid_columnconfigure(0, weight=1)
        self.user_input = ctk.CTkEntry(w_in, placeholder_text="Ask...", height=60, border_width=0, fg_color="transparent")
        self.user_input.grid(row=0, column=0, sticky="ew", padx=15); self.user_input.bind("<Return>", lambda e: self.send_message())
        ctk.CTkButton(w_in, text="Send", width=90, command=self.send_message).grid(row=0, column=1, padx=10)
        self.update_sidebar_history(); self.update_source_list(); self.load_active_chat_to_display()

    def setup_ai(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.researcher_engine = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="meta-llama/llama-3.1-405b-instruct:free")
        self.editor_engine = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="meta-llama/llama-3.3-70b-instruct:free", streaming=True)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    def get_cached_vectorstore(self):
        h = str(sorted(os.listdir(SOURCE_DIR)))
        if self.cached_vectorstore and self.cached_docs_hash == h: return self.cached_vectorstore
        docs = []
        for f in os.listdir(SOURCE_DIR):
            p = os.path.join(SOURCE_DIR, f); ext = f.lower()
            if ext.endswith(".pdf"): docs.extend(PyMuPDFLoader(p).load())
            elif ext.endswith(".txt"): docs.extend(TextLoader(p, encoding="utf-8").load())
            elif ext.endswith(".docx"): docs.extend(Docx2txtLoader(p).load())
        if docs:
            self.cached_vectorstore = FAISS.from_documents(RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs), self.embeddings)
            self.cached_docs_hash = h; return self.cached_vectorstore
        return None

    def format_ui_text(self, t):
        for r in [("**", ""), ("* ", "• "), ("### ", ""), ("## ", "")]: t = t.replace(*r)
        return t

    def send_message(self):
        q = self.user_input.get().strip()
        if q: self.user_input.delete(0, "end"); self.user_input.configure(state="disabled"); self.append_chat_to_ui(f"👤 You:\n{q}\n\n"); threading.Thread(target=self.run_agentic_workflow, args=(q,), daemon=True).start()

    def append_chat_to_ui(self, t):
        self.chat_display.configure(state="normal"); self.chat_display.insert("end", t); self.chat_display.configure(state="disabled"); self.chat_display.see("end")

    def update_sidebar_history(self):
        for w in self.history_list.winfo_children(): w.destroy()
        for e in reversed(self.session_history):
            f = ctk.CTkFrame(self.history_list, fg_color="transparent"); f.pack(fill="x", pady=2)
            ctk.CTkButton(f, text=e['title'], anchor="w", fg_color="transparent", command=lambda s=e['id']: self.switch_to_session(s)).pack(side="left", fill="x", expand=True)

    def switch_to_session(self, sid): self.current_session_id = sid; self.save_current_state(); self.load_active_chat_to_display()

    def load_active_chat_to_display(self):
        self.chat_display.configure(state="normal"); self.chat_display.delete("1.0", "end")
        p = os.path.join(HISTORY_DIR, f"{self.current_session_id}.json")
        if os.path.exists(p):
            for m in json.load(open(p, "r")): self.chat_display.insert("end", f"{'👤 You' if m['type'] == 'human' else '🤖 Agent'}:\n{self.format_ui_text(m['data']['content'])}\n\n")
        self.chat_display.configure(state="disabled"); self.chat_display.see("end")

    def start_new_session(self):
        sid = str(uuid.uuid4()); self.session_history.append({"id": sid, "title": f"Chat {datetime.datetime.now().strftime('%H:%M')}"})
        self.current_session_id = sid; self.save_current_state(); self.update_sidebar_history(); self.load_active_chat_to_display()

    def upload_files(self):
        fs = filedialog.askopenfilenames()
        if fs: [shutil.copy(f, SOURCE_DIR) for f in fs]; self.update_source_list(); self.cached_vectorstore = None

    def update_source_list(self):
        for w in self.source_list.winfo_children(): w.destroy()
        for f in os.listdir(SOURCE_DIR): ctk.CTkLabel(self.source_list, text=f"• {f}", font=(FONT_MAIN, 12)).pack(anchor="w", padx=5)

    def open_manage_sources_menu(self):
        win = ctk.CTkToplevel(self); win.title("Manage"); win.geometry("400x500"); win.attributes("-topmost", True); win.grab_set()
        sc = ctk.CTkScrollableFrame(win, fg_color="transparent"); sc.pack(fill="both", expand=True, padx=20, pady=20)
        cbs = {}
        for f in os.listdir(SOURCE_DIR): v = tk.BooleanVar(); ctk.CTkCheckBox(sc, text=f, variable=v).pack(anchor="w", pady=5); cbs[f] = v
        def delete():
            for f, v in cbs.items():
                if v.get(): os.remove(os.path.join(SOURCE_DIR, f))
            self.update_source_list(); self.cached_vectorstore = None; win.destroy()
        ctk.CTkButton(win, text="Delete", fg_color="#e74c3c", command=delete).pack(pady=20)

    def open_settings_menu(self):
        win = ctk.CTkToplevel(self); win.title("Settings"); win.geometry("350x250"); win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="Build v4.6", font=(FONT_MAIN, 18)).pack(pady=20)
        self.update_status_lbl = ctk.CTkLabel(win, text="Checking Cloud...", text_color=TEXT_MUTED); self.update_status_lbl.pack()
        ctk.CTkButton(win, text="Force Check", command=lambda: self.check_for_updates(True)).pack(pady=10)

if __name__ == "__main__":
    ChatApp().mainloop()
