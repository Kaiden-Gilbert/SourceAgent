import os, threading, time, shutil, math, uuid, json, queue
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# --- VAULT CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are "Policy Advisor 2026", an enterprise compliance AI.
You have ONE job: Answer questions using ONLY the provided policy documents.
1. NEVER invent or guess. Say "I cannot find a policy regarding this" if it's missing.
2. Quote the exact policy name, section, and text verbatim.
3. Separate plain English explanations from quotes.
4. Keep tone clinical, professional, and precise."""

# ==========================================
# CUSTOM AUTHENTICATION DIALOG
# ==========================================
class AuthDialog(ctk.CTkToplevel):
    def __init__(self, parent, password, success_callback):
        super().__init__(parent)
        self.title("Authentication Required")
        self.geometry("350x220")
        self.configure(fg_color="#0f172a")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (350 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (220 // 2)
        self.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(self, text="🔒 Secure Session", font=("Segoe UI", 18, "bold"), text_color="#f8fafc").pack(pady=(25, 10))
        ctk.CTkLabel(self, text="Enter Vault Password to decrypt.", text_color="#94a3b8", font=("Segoe UI", 12)).pack(pady=(0, 15))
        
        self.pwd = ctk.CTkEntry(self, show="*", placeholder_text="Password...", width=250, height=40, fg_color="#020617", border_color="#334155")
        self.pwd.pack(pady=5)
        self.pwd.bind("<Return>", lambda e: self.check())
        
        ctk.CTkButton(self, text="Unlock", fg_color="#3b82f6", font=("Segoe UI", 14, "bold"), height=40, width=250, command=self.check).pack(pady=15)
        
        self.password = password
        self.success_callback = success_callback
        self.pwd.focus()
        
    def check(self):
        if self.pwd.get() == self.password:
            self.destroy()
            self.success_callback()
        else:
            self.pwd.configure(border_color="#ef4444")
            self.pwd.delete(0, "end")

# ==========================================
# DEDICATED CHAT WINDOW (PERSISTENT)
# ==========================================
class DedicatedChatWindow(ctk.CTkToplevel):
    def __init__(self, master, app_core):
        super().__init__(master)
        self.app_core = app_core
        self.session_id = str(uuid.uuid4())
        self.title(f"Dedicated Session | {self.session_id[:8]}")
        self.geometry("800x600")
        self.configure(fg_color="#0f172a")
        
        self.text_queue = queue.Queue()
        
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#020617", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.chat.insert("1.0", "SYSTEM: Dedicated window established. Ready for isolated inquiry.\n\n")
        self.chat.configure(state="disabled")
        
        input_bar = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=10)
        input_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        input_bar.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_bar, height=50, placeholder_text="Ask a question...", fg_color="transparent", border_width=0, font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=10)
        self.entry.bind("<Return>", lambda e: self.send())
        
        ctk.CTkButton(input_bar, text="Submit", width=100, height=40, font=("Segoe UI", 14, "bold"), fg_color="#3b82f6", command=self.send).grid(row=0, column=1, padx=10, pady=5)
        
        # Register new session in main app
        self.app_core.session_history.insert(0, {'id': self.session_id, 'title': "New Dedicated Session"})
        self.app_core.save_settings()
        self.app_core.update_sidebar_history()
        
        self.process_queue()

    def append_to_history(self, text):
        with open(os.path.join(HISTORY_DIR, f"{self.session_id}.txt"), "a", encoding="utf-8") as f:
            f.write(text)

    def process_queue(self):
        try:
            while True:
                chunk = self.text_queue.get_nowait()
                self.chat.configure(state="normal")
                self.chat.insert("end", chunk)
                self.chat.see("end")
                self.chat.configure(state="disabled")
                self.append_to_history(chunk)
        except queue.Empty: pass
        self.after(50, self.process_queue)

    def safe_ui_update(self, text): 
        self.text_queue.put(text)

    def send(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        
        # Update title in sidebar dynamically
        for item in self.app_core.session_history:
            if item['id'] == self.session_id and item['title'] == "New Dedicated Session":
                item['title'] = q[:22] + "..." if len(q) > 22 else q
                self.app_core.save_settings()
                self.app_core.update_sidebar_history()
                
        self.safe_ui_update(f"\nUSER: {q}\n\nADVISOR: ")
        threading.Thread(target=self.generate_response, args=(q,), daemon=True).start()

    def generate_response(self, q):
        try:
            context = ""
            if self.app_core.db:
                docs = self.app_core.db.as_retriever(search_kwargs={"k": 5}).invoke(q)
                context = "\n".join([d.page_content for d in docs])
            msgs = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]
            for chunk in self.app_core.llm.stream(msgs):
                self.safe_ui_update(chunk.content)
            self.safe_ui_update("\n\n---\n")
        except Exception as e:
            self.safe_ui_update(f"\n[ERROR: {str(e)}]\n\n---\n")

# ==========================================
# MAIN APPLICATION ENGINE
# ==========================================
class PolicyAdvisorV19(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise Edition")
        self.geometry("1250x800")
        
        self.bg_deep = "#020617"
        self.bg_surface = "#0f172a"
        self.accent = "#3b82f6"
        self.text_queue = queue.Queue()
        self.current_session_id = str(uuid.uuid4())
        
        self.load_settings()
        ctk.set_appearance_mode("Dark")
        self.draw_kinetic_background()
        
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()
        self.build_ai_engine()
        
        if hasattr(self, 'app_password') and self.app_password != "":
            self.show_login_screen()
        else:
            self.setup_main_ui()

    def show_login_screen(self):
        self.login_frame = ctk.CTkFrame(self, fg_color=self.bg_surface, corner_radius=15, width=400, height=300)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(self.login_frame, text="🔒 System Locked", font=("Segoe UI", 24, "bold")).pack(pady=(40, 10))
        ctk.CTkLabel(self.login_frame, text="Enter administrative password to access database.", text_color="#94a3b8").pack(pady=(0, 20))
        
        pwd_entry = ctk.CTkEntry(self.login_frame, show="*", width=250, height=45, placeholder_text="Password...", fg_color="#020617", border_color="#334155")
        pwd_entry.pack(pady=10)
        
        def attempt_login(e=None):
            if pwd_entry.get() == self.app_password:
                self.login_frame.destroy()
                self.setup_main_ui()
            else:
                pwd_entry.configure(border_color="#ef4444")
                pwd_entry.delete(0, "end")
                
        pwd_entry.bind("<Return>", attempt_login)
        ctk.CTkButton(self.login_frame, text="Unlock Engine", font=("Segoe UI", 14, "bold"), fg_color=self.accent, height=45, width=250, command=attempt_login).pack(pady=(10, 40))

    def draw_kinetic_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg=self.bg_deep)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.orbs = [
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#1e3a8a"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#172554")
        ]
        self.anim_step = 0
        self.animate_bg()

    def animate_bg(self):
        if not hasattr(self, 'bg_canvas') or not self.bg_canvas.winfo_exists(): return
        w, h = self.winfo_width(), self.winfo_height()
        if w > 100:
            self.anim_step += 0.015 
            x1 = (math.sin(self.anim_step) * (w/3)) + (w/2); y1 = (math.cos(self.anim_step * 0.7) * (h/3)) + (h/2)
            self.bg_canvas.coords(self.orbs[0], x1-700, y1-700, x1+700, y1+700)
            x2 = (math.cos(self.anim_step * 0.5) * (w/4)) + (w/2); y2 = (math.sin(self.anim_step * 0.8) * (h/4)) + (h/2)
            self.bg_canvas.coords(self.orbs[1], x2-500, y2-500, x2+500, y2+500)
        self.bg_canvas.lower("all")
        self.after(35, self.animate_bg)

    def fade_in(self, win, target=1.0):
        if win.attributes("-alpha") < target:
            win.attributes("-alpha", win.attributes("-alpha") + 0.08)
            self.after(20, lambda: self.fade_in(win, target))

    def setup_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=300, fg_color="transparent")
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        header_box = ctk.CTkFrame(self.sidebar, fg_color=self.bg_surface, corner_radius=12)
        header_box.pack(fill="x", pady=10)
        ctk.CTkLabel(header_box, text="🏛️ Policy Advisor", font=("Segoe UI", 20, "bold")).pack(pady=20)
        
        ctk.CTkButton(self.sidebar, text="+ New Dashboard Inquiry", font=("Segoe UI", 13, "bold"), fg_color=self.accent, height=40, command=self.start_new_session).pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkButton(self.sidebar, text="⧉ Launch Dedicated Chat", font=("Segoe UI", 13, "bold"), fg_color="#10b981", hover_color="#059669", height=40, command=lambda: DedicatedChatWindow(self, self)).pack(fill="x", padx=10, pady=(0, 10))
        
        # History Scroll
        self.history_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color=self.bg_surface, corner_radius=12, height=250)
        self.history_scroll.pack(fill="x", pady=10)
        
        tools_box = ctk.CTkFrame(self.sidebar, fg_color=self.bg_surface, corner_radius=12)
        tools_box.pack(fill="x", pady=10)
        ctk.CTkButton(tools_box, text="📁 Upload Policy Docs", fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkButton(tools_box, text="🗄️ Database Manager", fg_color="#334155", command=self.open_manager).pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(tools_box, text="⚙️ Advanced Settings", fg_color="#334155", command=self.open_settings).pack(fill="x", padx=15, pady=(5, 15))
        
        self.status_lbl = ctk.CTkLabel(self.sidebar, text="● Engine Online", text_color="#10b981", font=("Segoe UI", 12, "bold"))
        self.status_lbl.pack(side="bottom", pady=20)

        work_area = ctk.CTkFrame(self, fg_color=self.bg_surface, corner_radius=15)
        work_area.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        work_area.grid_rowconfigure(0, weight=1); work_area.grid_columnconfigure(0, weight=1)

        self.chat = ctk.CTkTextbox(work_area, font=("Segoe UI", 15), fg_color="transparent", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.chat.configure(state="disabled")
        
        input_bar = ctk.CTkFrame(work_area, fg_color="#1e293b", corner_radius=10)
        input_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        input_bar.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_bar, height=50, placeholder_text="Ask a compliance question...", fg_color="transparent", border_width=0, font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=10)
        self.entry.bind("<Return>", lambda e: self.send())
        ctk.CTkButton(input_bar, text="Submit", width=100, height=40, font=("Segoe UI", 14, "bold"), fg_color=self.accent, command=self.send).grid(row=0, column=1, padx=10, pady=5)
        
        self.update_sidebar_history()
        self.load_active_chat()
        self.process_queue()

    def build_ai_engine(self):
        if not self.api_key: return
        try: self.llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model, temperature=self.ai_temp, max_tokens=self.ai_max_tokens, top_p=0.85, streaming=True)
        except: pass

    # --- SESSION MANAGEMENT & AUTHENTICATION ---
    def start_new_session(self):
        self.current_session_id = str(uuid.uuid4())
        self.load_active_chat()

    def auth_switch_session(self, session_id):
        # If password exists, demand it before switching memory context
        if hasattr(self, 'app_password') and self.app_password != "":
            AuthDialog(self, self.app_password, success_callback=lambda: self.execute_switch(session_id))
        else:
            self.execute_switch(session_id)

    def execute_switch(self, session_id):
        self.current_session_id = session_id
        self.load_active_chat()

    def update_sidebar_history(self):
        if not hasattr(self, 'history_scroll'): return
        for w in self.history_scroll.winfo_children(): w.destroy()
        if not self.session_history:
            ctk.CTkLabel(self.history_scroll, text="No saved sessions.", text_color="#64748b").pack(pady=20)
            return
        for item in self.session_history: 
            btn = ctk.CTkButton(self.history_scroll, text=item['title'], fg_color="transparent", hover_color="#1e293b", text_color="#f8fafc", font=("Segoe UI", 12), anchor="w", height=35, command=lambda sid=item['id']: self.auth_switch_session(sid))
            btn.pack(fill="x", pady=2)

    def append_to_history(self, text):
        with open(os.path.join(HISTORY_DIR, f"{self.current_session_id}.txt"), "a", encoding="utf-8") as f: f.write(text)

    def load_active_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        hf = os.path.join(HISTORY_DIR, f"{self.current_session_id}.txt")
        if os.path.exists(hf):
            with open(hf, "r", encoding="utf-8") as f: self.chat.insert("end", f.read())
        else:
            self.chat.insert("1.0", "SYSTEM: Main Dashboard Online. Ready for inquiry.\n\n")
        self.chat.configure(state="disabled")

    def process_queue(self):
        try:
            while True:
                chunk = self.text_queue.get_nowait()
                self.chat.configure(state="normal")
                self.chat.insert("end", chunk)
                self.chat.see("end")
                self.chat.configure(state="disabled")
                self.append_to_history(chunk)
        except queue.Empty: pass
        self.after(50, self.process_queue)

    def safe_ui_update(self, text): self.text_queue.put(text)

    def send(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        
        if len(self.session_history) == 0 or self.session_history[0]['id'] != self.current_session_id:
            self.session_history.insert(0, {'id': self.current_session_id, 'title': q[:22] + "..." if len(q) > 22 else q})
            self.save_settings()
            self.update_sidebar_history()
            
        self.safe_ui_update(f"\nUSER: {q}\n\nADVISOR: ")
        self.status_lbl.configure(text="● Auditing Database...", text_color="#f59e0b")
        threading.Thread(target=self.generate_response, args=(q,), daemon=True).start()

    def generate_response(self, q):
        try:
            context = ""
            if self.db:
                docs = self.db.as_retriever(search_kwargs={"k": 5}).invoke(q)
                context = "\n".join([d.page_content for d in docs])
            msgs = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]
            for chunk in self.llm.stream(msgs):
                self.safe_ui_update(chunk.content)
            self.safe_ui_update("\n\n---\n")
            self.after(0, lambda: self.status_lbl.configure(text="● Engine Online", text_color="#10b981"))
        except Exception as e:
            self.safe_ui_update(f"\n[ERROR: {str(e)}]\n\n---\n")
            self.after(0, lambda: self.status_lbl.configure(text="● Engine Error", text_color="#ef4444"))

    # --- DATABASE MANAGER ---
    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True) if os.path.exists(index) else None

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDFs", "*.pdf")])
        if not files: return
        self.status_lbl.configure(text="● Indexing...", text_color="#3b82f6")
        for f in files: shutil.copy(f, SOURCE_DIR)
        threading.Thread(target=self.rebuild_db, daemon=True).start()

    def open_manager(self):
        win = ctk.CTkToplevel(self)
        win.title("Database Manager")
        win.geometry("500x450")
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0); self.fade_in(win)
        win.configure(fg_color=self.bg_surface)
        
        ctk.CTkLabel(win, text="Manage Active Policies", font=("Segoe UI", 20, "bold")).pack(pady=20)
        scroll = ctk.CTkScrollableFrame(win, fg_color=self.bg_deep)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        def refresh():
            for w in scroll.winfo_children(): w.destroy()
            files = [f for f in os.listdir(SOURCE_DIR) if f.endswith(".pdf")]
            if not files:
                ctk.CTkLabel(scroll, text="No policies loaded.", text_color="#94a3b8").pack(pady=20)
                return
            for f in files:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=5)
                ctk.CTkLabel(row, text=f, font=("Segoe UI", 12)).pack(side="left", padx=10)
                ctk.CTkButton(row, text="🗑 Delete", width=60, fg_color="#ef4444", hover_color="#dc2626", command=lambda filename=f: delete_file(filename)).pack(side="right", padx=10)

        def delete_file(filename):
            os.remove(os.path.join(SOURCE_DIR, filename))
            refresh()
            self.status_lbl.configure(text="● Re-indexing...", text_color="#f59e0b")
            threading.Thread(target=self.rebuild_db, daemon=True).start()

        refresh()

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            self.db = FAISS.from_documents(RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs), self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))
        else:
            self.db = None
            if os.path.exists(os.path.join(SOURCE_DIR, "faiss_index")): shutil.rmtree(os.path.join(SOURCE_DIR, "faiss_index"))
        self.after(0, lambda: self.status_lbl.configure(text="● Engine Online", text_color="#10b981"))

    # --- ADVANCED SETTINGS ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Advanced Configuration")
        win.geometry("450x600")
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0); self.fade_in(win)
        win.configure(fg_color=self.bg_surface)
        
        ctk.CTkLabel(win, text="Engine Configuration", font=("Segoe UI", 22, "bold")).pack(pady=20)
        
        ctk.CTkLabel(win, text="AI Core Model:", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        models = ["google/gemini-1.5-flash:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-lite-preview-02-05:free"]
        model_menu = ctk.CTkOptionMenu(win, values=models, width=370)
        model_menu.set(self.ai_model); model_menu.pack(pady=(5, 15))
        
        ctk.CTkLabel(win, text="Creativity (Locked Max 0.7):", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        temp_val = ctk.CTkLabel(win, text=str(self.ai_temp), font=("Segoe UI", 12, "bold"), text_color=self.accent)
        temp_val.pack()
        temp_slider = ctk.CTkSlider(win, from_=0.0, to=0.7, number_of_steps=14, width=370)
        temp_slider.set(self.ai_temp); temp_slider.pack(pady=(5, 15))
        temp_slider.configure(command=lambda v: temp_val.configure(text=f"{v:.2f}"))
        
        ctk.CTkLabel(win, text="Response Length (Max Tokens):", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        tok_val = ctk.CTkLabel(win, text=str(self.ai_max_tokens), font=("Segoe UI", 12, "bold"), text_color=self.accent)
        tok_val.pack()
        tok_slider = ctk.CTkSlider(win, from_=256, to=4096, number_of_steps=15, width=370)
        tok_slider.set(self.ai_max_tokens); tok_slider.pack(pady=(5, 15))
        tok_slider.configure(command=lambda v: tok_val.configure(text=f"{int(v)}"))

        ctk.CTkLabel(win, text="App Vault Password (Leave blank to disable):", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        pwd_entry = ctk.CTkEntry(win, width=370, placeholder_text="Set a password...", show="*", fg_color="#020617", border_color="#334155")
        if hasattr(self, 'app_password'): pwd_entry.insert(0, self.app_password)
        pwd_entry.pack(pady=5)

        def apply_changes():
            self.ai_model = model_menu.get()
            self.ai_temp = float(temp_slider.get())
            self.ai_max_tokens = int(tok_slider.get())
            self.app_password = pwd_entry.get()
            self.save_settings()
            self.build_ai_engine() 
            win.destroy()
            
        ctk.CTkButton(win, text="Apply & Reboot Engine", fg_color=self.accent, height=40, font=("Segoe UI", 14, "bold"), command=apply_changes).pack(pady=20)

    def load_settings(self):
        self.session_history = []
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.ai_model = d.get("ai_model", "google/gemini-1.5-flash:free")
                    self.ai_temp = d.get("ai_temp", 0.1) 
                    self.ai_max_tokens = d.get("ai_max_tokens", 1024)
                    self.app_password = d.get("app_password", "")
                    self.session_history = d.get("history", [])
            except: pass

    def save_settings(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({
                "ai_model": self.ai_model,
                "ai_temp": self.ai_temp,
                "ai_max_tokens": self.ai_max_tokens,
                "app_password": getattr(self, 'app_password', ""),
                "history": self.session_history
            }, f)

if __name__ == "__main__":
    app = PolicyAdvisorV19()
    app.mainloop()
