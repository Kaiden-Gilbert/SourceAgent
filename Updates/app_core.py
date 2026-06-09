import os, sys, threading, shutil, json, time, urllib.request, subprocess, math, random, queue, re
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
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader, CSVLoader

# --- INFRASTRUCTURE CONFIGURATION ---
CURRENT_VERSION = 50.0
BASE_DIR = os.getcwd()
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
CHATS_FILE = os.path.join(BASE_DIR, "chat_sessions.json")
RECOVERY_FILE = os.path.join(BASE_DIR, "recovery.json")

os.makedirs(SOURCE_DIR, exist_ok=True)

ui_queue = queue.Queue()
audio_queue = queue.Queue()

# --- DEFAULT SETTINGS ARCHITECTURE ---
DEFAULT_CONFIG = {
    "theme_mode": "Dark",
    "accent_color": "blue",
    "ai_model": "tinyllama",
    "max_tokens": 512,
    "temperature": 0.2,
    "repeat_penalty": 1.2,
    "chunk_depth": 5,
    "vault_summary": "No active documents compiled in library vault."
}

def load_app_config():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                user_conf = json.load(f)
                # Merge user choices over base defaults safely
                return {**DEFAULT_CONFIG, **user_conf}
        except: pass
    return DEFAULT_CONFIG.copy()

APP_CONFIG = load_app_config()

# --- AUDIO HARDWARE SYNC LOOP ---
def tts_worker_loop():
    try:
        if os.name == 'nt':
            import pythoncom
            pythoncom.CoInitialize()
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 165)
        while True:
            text = audio_queue.get()
            if text is None: break
            clean_text = re.sub(r'[*#`\-]', '', text)
            clean_text = re.sub(r'\[Verified Sources:.*?\]', '', clean_text)
            engine.say(clean_text)
            engine.runAndWait()
            audio_queue.task_done()
    except: pass

threading.Thread(target=tts_worker_loop, daemon=True).start()

# ====================================================================
# PERSISTENT SESSION DATABASE MANAGER
# ====================================================================
class ChatSessionManager:
    def __init__(self):
        self.sessions = {}
        self.active_id = None
        self.load_all_sessions()

    def load_all_sessions(self):
        if os.path.exists(CHATS_FILE):
            try:
                with open(CHATS_FILE, "r") as f:
                    self.sessions = json.load(f)
                    if self.sessions:
                        self.active_id = list(self.sessions.keys())[0]
                        return
            except: pass
        self.create_new_session("Initial Investigation Link")

    def save_all_sessions(self):
        try:
            with open(CHATS_FILE, "w") as f:
                json.dump(self.sessions, f, indent=4)
        except Exception as e: print(f"Session serialize error: {e}")

    def create_new_session(self, title=None):
        s_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        if not title:
            title = f"Inquiry Axis Thread ({datetime.now().strftime('%H:%M:%S')})"
        self.sessions[s_id] = {
            "title": title,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }
        self.active_id = s_id
        self.save_all_sessions()
        return s_id

    def add_message(self, role, text, sources=None):
        if self.active_id in self.sessions:
            self.sessions[self.active_id]["messages"].append({
                "role": role,
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "sources": sources or []
            })
            self.save_all_sessions()

    def get_active_messages(self):
        if self.active_id in self.sessions:
            return self.sessions[self.active_id]["messages"]
        return []

    def delete_session(self, s_id):
        if s_id in self.sessions:
            del self.sessions[s_id]
            if self.active_id == s_id:
                self.active_id = list(self.sessions.keys())[0] if self.sessions else self.create_new_session("Workspace Link Alpha")
            self.save_all_sessions()

SESSION_DB = ChatSessionManager()

# ====================================================================
# SYSTEM INTERFACE HUD (ENTERPRISE REWRITE)
# ====================================================================
class SourceAgentMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Source Agent Pro | Deep Research Terminal V{CURRENT_VERSION}")
        self.geometry("1300x880")
        
        # Apply strict visual palette matrix 
        ctk.set_appearance_mode(APP_CONFIG["theme_mode"])
        ctk.set_default_color_theme(APP_CONFIG["accent_color"])
        
        self.configure(fg_color="#090d16" if APP_CONFIG["theme_mode"] == "Dark" else "#f8fafc")
        
        # Async background components
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()
        
        self.setup_ui_layout()
        self.process_ui_queue()
        self.refresh_session_sidebar()
        self.reload_active_chat_canvas()

    def process_ui_queue(self):
        try:
            while True:
                action, target, text, tag = ui_queue.get_nowait()
                if action == "insert":
                    target.configure(state="normal")
                    target.insert("end", text, tag) if tag else target.insert("end", text)
                    target.see("end")
                    target.configure(state="disabled")
                elif action == "clear":
                    target.configure(state="normal")
                    target.delete("1.0", "end")
                    target.configure(state="disabled")
        except queue.Empty: pass
        self.after(30, self.process_ui_queue)

    def setup_ui_layout(self):
        self.grid_columnconfigure(0, weight=0) # Sidebar Threads
        self.grid_columnconfigure(1, weight=1) # Focus Workspace Workspace
        self.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------------------
        # PANE 1: CONTROL AXIS SIDEBAR
        # ----------------------------------------------------------------
        sb = ctk.CTkFrame(self, width=300, fg_color="#111827" if APP_CONFIG["theme_mode"]=="Dark" else "#e2e8f0", corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(sb, text="Source Agent Pro", font=("Segoe UI", 22, "bold")).pack(pady=(25, 2))
        ctk.CTkLabel(sb, text="Offline Intelligence Vault", font=("Segoe UI", 11, "bold"), text_color="#10b981").pack(pady=(0, 20))

        # Core Vault Management Card
        v_card = ctk.CTkFrame(sb, fg_color="#1f2937" if APP_CONFIG["theme_mode"]=="Dark" else "#cbd5e1", corner_radius=10)
        v_card.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(v_card, text="SYSTEM DOCUMENT VAULT", font=("Segoe UI", 11, "bold"), text_color="#9ca3af").pack(pady=(8,2))
        
        btn_f = ctk.CTkFrame(v_card, fg_color="transparent")
        btn_f.pack(fill="x", padx=10, pady=(5,10))
        btn_f.grid_columnconfigure(0, weight=1); btn_f.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(btn_f, text="📥 Ingest", font=("Segoe UI", 12, "bold"), fg_color="#2563eb", height=34, command=self.add_docs).grid(row=0, column=0, padx=(0,4), sticky="ew")
        ctk.CTkButton(btn_f, text="🗑️ Clear", font=("Segoe UI", 12, "bold"), fg_color="#dc2626", height=34, command=self.clear_all_sources).grid(row=0, column=1, padx=(4,0), sticky="ew")

        # Ingested items display panel
        ctk.CTkLabel(sb, text="COMPILED KNOWLEDGE BASIS:", font=("Segoe UI", 11, "bold"), text_color="#6b7280").pack(anchor="w", padx=20, pady=(15, 2))
        self.sources_scroll = ctk.CTkScrollableFrame(sb, height=160, fg_color="#030712" if APP_CONFIG["theme_mode"]=="Dark" else "#f1f5f9")
        self.sources_scroll.pack(fill="x", padx=15, pady=0)
        self.refresh_source_list()

        # Chat Sessions Segment Divider
        ctk.CTkLabel(sb, text="HISTORICAL CONVERSATIONS:", font=("Segoe UI", 11, "bold"), text_color="#6b7280").pack(anchor="w", padx=20, pady=(15, 2))
        
        ctk.CTkButton(sb, text="➕ Initialize New Chat", font=("Segoe UI", 13, "bold"), fg_color="#059669", hover_color="#10b981", height=36, command=self.trigger_brand_new_chat).pack(fill="x", padx=15, pady=5)
        
        self.session_scroll = ctk.CTkScrollableFrame(sb, fg_color="#030712" if APP_CONFIG["theme_mode"]=="Dark" else "#f1f5f9")
        self.session_scroll.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        # Technical Footer
        ft = ctk.CTkFrame(sb, fg_color="transparent")
        ft.pack(side="bottom", fill="x", pady=15, padx=15)
        ctk.CTkButton(ft, text="⚙️ Operational Parameters", font=("Segoe UI", 12, "bold"), fg_color="#4b5563", command=self.open_advanced_settings).pack(fill="x", pady=2)

        # ----------------------------------------------------------------
        # PANE 2: FOCUS INTERACTIVE TAB ARCHITECTURE
        # ----------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self, fg_color="#111827" if APP_CONFIG["theme_mode"]=="Dark" else "#ffffff")
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=15)
        
        self.tab_chat = self.tabview.add("Terminal Chat Platform")
        self.tab_studio = self.tabview.add("Executive Summary Studio")
        
        self.research_var = ctk.BooleanVar(value=False)
        self.audio_var = ctk.BooleanVar(value=False)
        
        self.build_chat_interface()
        self.build_studio_interface()

    # ====================================================================
    # COMPONENT GENERATORS & LOGIC ROUTINES
    # ====================================================================
    def build_chat_interface(self):
        self.tab_chat.grid_columnconfigure(0, weight=1); self.tab_chat.grid_rowconfigure(0, weight=1)
        
        self.chat = ctk.CTkTextbox(self.tab_chat, font=("Segoe UI", 15), spacing1=6, spacing3=6, border_width=1, border_color="#1e293b")
        self.chat.grid(row=0, column=0, sticky="nsew", pady=(5, 15), padx=5)
        
        self.chat.tag_config("user", foreground="#60a5fa", font=("Segoe UI", 15, "bold"))
        self.chat.tag_config("agent", foreground="#34d399", font=("Segoe UI", 15))
        self.chat.tag_config("source", foreground="#fbbf24", font=("Segoe UI", 12, "italic"))
        self.chat.tag_config("system", foreground="#9ca3af", font=("Consolas", 12, "italic"))
        
        # Interactive Control Dash
        ctrl_b = ctk.CTkFrame(self.tab_chat, fg_color="transparent")
        ctrl_b.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        ctrl_b.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(ctrl_b, height=48, placeholder_text="Transmit inquiry to system memory register...", font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.fire_chat_query())
        
        t_f = ctk.CTkFrame(ctrl_b, fg_color="transparent")
        t_f.grid(row=0, column=1, padx=(0,10))
        ctk.CTkSwitch(t_f, text="Deep Vector Mapping", variable=self.research_var, font=("Segoe UI", 11, "bold")).pack(pady=1)
        ctk.CTkSwitch(t_f, text="🔊 Vocal Synthesis", variable=self.audio_var, font=("Segoe UI", 11, "bold"), progress_color="#a855f7").pack(pady=1)
        
        ctk.CTkButton(ctrl_b, text="QUERY CORE", width=130, height=48, font=("Segoe UI", 13, "bold"), command=self.fire_chat_query).grid(row=0, column=2)

    def build_studio_interface(self):
        self.tab_studio.grid_columnconfigure(0, weight=1); self.tab_studio.grid_rowconfigure(1, weight=1)
        
        head = ctk.CTkFrame(self.tab_studio, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=10, padx=5)
        
        ctk.CTkLabel(head, text="Target Document Matrix:", font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 8))
        self.studio_mode = ctk.CTkOptionMenu(head, values=["Executive Intelligence Brief", "Technical QA Log", "System Domain Map"], width=220)
        self.studio_mode.pack(side="left", padx=5)
        
        ctk.CTkButton(head, text="✨ Synthesize Model Report", font=("Segoe UI", 12, "bold"), fg_color="#7c3aed", command=self.run_studio_generation).pack(side="left", padx=15)
        ctk.CTkButton(head, text="💾 Export MD", font=("Segoe UI", 12), fg_color="#059669", command=self.export_studio_markdown).pack(side="right")
        
        self.studio_box = ctk.CTkTextbox(self.tab_studio, font=("Consolas", 14), spacing1=4, spacing3=4, border_width=1, border_color="#1e293b")
        self.studio_box.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 10))
        self.studio_box.insert("1.0", "--- INTEL WORKSPACE TERMINAL ---\nSelect an processing layout configuration file mapping and run compilation above.")

    # ====================================================================
    # FILE SYSTEM VAULT MANAGEMENT ENGINE
    # ====================================================================
    def refresh_source_list(self):
        for w in self.sources_scroll.winfo_children(): w.destroy()
        valid = (".pdf", ".txt", ".docx", ".csv")
        try:
            files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(valid)]
            if not files:
                ctk.CTkLabel(self.sources_scroll, text="No local files mounted.", font=("Segoe UI", 12, "italic"), text_color="#4b5563").pack(pady=12)
                return
            for f in files:
                r = ctk.CTkFrame(self.sources_scroll, fg_color="transparent")
                r.pack(fill="x", pady=2)
                lbl = f if len(f) <= 22 else f[:19] + "..."
                ctk.CTkLabel(r, text=f"• {lbl}", font=("Segoe UI", 12)).pack(side="left", anchor="w", padx=5)
                ctk.CTkButton(r, text="✕", width=22, height=22, fg_color="#ef4444", text_color="white", font=("Segoe UI", 10, "bold"), command=lambda nm=f: self.purge_single_source(nm)).pack(side="right", padx=5)
        except: pass

    def add_docs(self):
        f_paths = filedialog.askopenfilenames(filetypes=[("Enterprise Documents", "*.pdf;*.txt;*.docx;*.csv")])
        if f_paths:
            for p in f_paths: shutil.copy(p, SOURCE_DIR)
            self.refresh_source_list()
            threading.Thread(target=self.rebuild_vector_matrix, daemon=True).start()
            messagebox.showinfo("Vault Processing", "Knowledge ingestion protocol active. Compiling document vector layers...")

    def purge_single_source(self, filename):
        if messagebox.askyesno("Erase Source", f"Confirm removal of {filename} from target vector alignment?"):
            try:
                os.remove(os.path.join(SOURCE_DIR, filename))
                self.refresh_source_list()
                threading.Thread(target=self.rebuild_vector_matrix, daemon=True).start()
            except Exception as e: messagebox.showerror("IO Fault", str(e))

    def clear_all_sources(self):
        if messagebox.askyesno("Purge Storage Grid", "WARNING: This completely erases the offline analytical cache. Continue?"):
            for f in os.listdir(SOURCE_DIR):
                p = os.path.join(SOURCE_DIR, f)
                if os.path.isfile(p): os.remove(p)
                elif os.path.isdir(p) and f == "faiss_index": shutil.rmtree(p)
            self.db = None
            APP_CONFIG["vault_summary"] = "No active documents compiled in library vault."
            with open(SAVE_FILE, "w") as config_f: json.dump(APP_CONFIG, config_f)
            self.refresh_source_list()
            messagebox.showinfo("System Matrix Cleared", "Analytical storage arrays reset successfully.")

    def rebuild_vector_matrix(self):
        loaded_chunks = []
        file_profiles = []
        for f in os.listdir(SOURCE_DIR):
            p = os.path.join(SOURCE_DIR, f)
            ext = f.lower().split('.')[-1]
            try:
                if ext == "pdf": chunks = PyMuPDFLoader(p).load()
                elif ext == "txt": chunks = TextLoader(p, encoding="utf-8").load()
                elif ext == "docx": chunks = Docx2txtLoader(p).load()
                elif ext == "csv": chunks = CSVLoader(p).load()
                else: continue
                loaded_chunks.extend(chunks)
                file_profiles.append(f"File: {f} (Char Count: {sum(len(c.page_content) for c in chunks)})")
            except: pass
                
        if loaded_chunks:
            split = RecursiveCharacterTextSplitter(chunk_size=650, chunk_overlap=120)
            processed_docs = split.split_documents(loaded_chunks)
            for d in processed_docs:
                d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
            self.db = FAISS.from_documents(processed_docs, self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))
            
            # Formulate local context profile to make the AI smarter
            summary_str = "Active Data Vault Context Profile:\n" + "\n".join(file_profiles[:6])
            APP_CONFIG["vault_summary"] = summary_str
        else:
            self.db = None
            APP_CONFIG["vault_summary"] = "No active documents compiled in library vault."
            
        with open(SAVE_FILE, "w") as config_f:
            json.dump(APP_CONFIG, config_f)

    def load_db(self):
        idx_path = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(idx_path):
            try: self.db = FAISS.load_local(idx_path, self.embeddings, allow_dangerous_deserialization=True)
            except: self.db = None

    # ====================================================================
    # ADVANCED SESSION WORKSPACE BACKEND INTERACTION
    # ====================================================================
    def refresh_session_sidebar(self):
        for w in self.session_scroll.winfo_children(): w.destroy()
        for s_id, data in SESSION_DB.sessions.items():
            f = ctk.CTkFrame(self.session_scroll, fg_color="#1f2937" if s_id == SESSION_DB.active_id else "transparent", corner_radius=6)
            f.pack(fill="x", pady=2, padx=2)
            
            trunc_title = data["title"] if len(data["title"]) <= 24 else data["title"][:21] + "..."
            
            # Selection handler wrapper
            btn = ctk.CTkButton(f, text=trunc_title, font=("Segoe UI", 12, "bold" if s_id == SESSION_DB.active_id else "normal"),
                                anchor="w", fg_color="transparent", text_color="#f3f4f6" if s_id == SESSION_DB.active_id else "#9ca3af",
                                hover_color="#374151", command=lambda idx=s_id: self.switch_active_session_channel(idx))
            btn.pack(side="left", fill="x", expand=True, padx=4, pady=2)
            
            if len(SESSION_DB.sessions) > 1:
                del_b = ctk.CTkButton(f, text="🗑️", width=24, height=24, fg_color="transparent", text_color="#9ca3af", hover_color="#4b5563",
                                      command=lambda idx=s_id: self.remove_session_channel(idx))
                del_b.pack(side="right", padx=4)

    def trigger_brand_new_chat(self):
        new_id = SESSION_DB.create_new_session()
        self.switch_active_session_channel(new_id)

    def switch_active_session_channel(self, s_id):
        SESSION_DB.active_id = s_id
        SESSION_DB.save_all_sessions()
        self.refresh_session_sidebar()
        self.reload_active_chat_canvas()

    def remove_session_channel(self, s_id):
        SESSION_DB.delete_session(s_id)
        self.refresh_session_sidebar()
        self.reload_active_chat_canvas()

    def reload_active_chat_canvas(self):
        ui_queue.put(("clear", self.chat, "", ""))
        messages = SESSION_DB.get_active_messages()
        
        ui_queue.put(("insert", self.chat, f"[SYSTEM DATA NODE REGISTERED — LOGGED TRACKS AVAILABLE]\n\n", "system"))
        for msg in messages:
            if msg["role"] == "user":
                ui_queue.put(("insert", self.chat, "USER: ", "user"))
                ui_queue.put(("insert", self.chat, f"{msg['text']}\n\n", ""))
            else:
                ui_queue.put(("insert", self.chat, "AGENT: ", "agent"))
                ui_queue.put(("insert", self.chat, f"{msg['text']}\n", ""))
                if msg.get("sources"):
                    citations = ", ".join(msg["sources"])
                    ui_queue.put(("insert", self.chat, f"[Verified Sources: {citations}]\n", "source"))
                ui_queue.put(("insert", self.chat, "---\n\n", "system"))

    def fire_chat_query(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        
        # If thread name is generic timestamp, rename it to user's first query context 
        if "Inquiry Axis Thread" in SESSION_DB.sessions[SESSION_DB.active_id]["title"] and len(q) < 30:
            SESSION_DB.sessions[SESSION_DB.active_id]["title"] = q
            self.refresh_session_sidebar()

        SESSION_DB.add_message("user", q)
        ui_queue.put(("insert", self.chat, "USER: ", "user"))
        ui_queue.put(("insert", self.chat, f"{q}\n\n", ""))
        ui_queue.put(("insert", self.chat, "AGENT: ", "agent"))
        
        threading.Thread(target=self.async_inference_engine, args=(q,), daemon=True).start()

    # ====================================================================
    # ADVANCED NEURAL CORE INFERENCE PROCESSOR (ANTI-DOT MATRIX ENGINE)
    # ====================================================================
    def async_inference_engine(self, query):
        is_deep = self.research_var.get()
        context_chunks = []
        source_tags = []
        
        if self.db:
            depth = int(APP_CONFIG["chunk_depth"] * 2 if is_deep else APP_CONFIG["chunk_depth"])
            docs = self.db.as_retriever(search_kwargs={"k": depth}).invoke(query)
            context_chunks = [d.page_content for d in docs]
            source_tags = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
            
        context_block = "\n\n".join(context_chunks)
        vault_profile = APP_CONFIG.get("vault_summary", "No documents loaded.")
        
        # Strict defensive architectural layout construction for model orchestration prompt mapping
        base_system_prompt = (
            "You are Source Agent Pro, a secure terminal parsing system.\n"
            f"Vault Profile Overview:\n{vault_profile}\n\n"
            "Execution Protocols:\n"
            "1. Rely strictly upon text facts compiled under the contextual reference fields below.\n"
            "2. Critical Rule: Avoid cycling text structures. Do not output repetitive lines, phrases, or blocks of text/punctuation.\n"
            "3. If details are not in context, state: 'Information missing from target vault logs.'"
        )
        
        payload_input = f"Context Material Blocks:\n{context_block}\n\nUser Operational Request: {query}"
        
        try:
            # We enforce temperature and repetition penalty configurations directly into the local host model instantiation matrix
            llm = ChatOllama(
                model=APP_CONFIG["ai_model"],
                temperature=float(APP_CONFIG["temperature"]),
                num_predict=int(APP_CONFIG["max_tokens"]),
                base_url="http://localhost:11434",
                model_kwargs={
                    "repeat_penalty": float(APP_CONFIG["repeat_penalty"]),
                    "stop": ["USER:", "AGENT:", "SYSTEM:"]
                }
            )
            
            stream = llm.stream([SystemMessage(content=base_system_prompt), HumanMessage(content=payload_input)])
            generation_accumulator = ""
            
            for stream_packet in stream:
                content_segment = stream_packet.content
                # Active defense filter targeting looping generation anomalies
                if content_segment == "." and generation_accumulator.endswith("..."):
                    continue
                ui_queue.put(("insert", self.chat, content_segment, ""))
                generation_accumulator += content_segment
                
            ui_queue.put(("insert", self.chat, "\n", ""))
            if source_tags:
                ui_queue.put(("insert", self.chat, f"[Verified Sources: {', '.join(source_tags)}]\n", "source"))
            ui_queue.put(("insert", self.chat, "---\n\n", "system"))
            
            SESSION_DB.add_message("agent", generation_accumulator, source_tags)
            
            if self.audio_var.get():
                audio_queue.put(generation_accumulator)
                
        except Exception as err:
            ui_queue.put(("insert", self.chat, f"\n[Core Connection Fault — Check Ollama Operational Diagnostics Instance]\nError: {str(err)}\n\n", "system"))

    # ====================================================================
    # EXECUTIVE NOTEBOOK COMPILATION RAG STUDIO
    # ====================================================================
    def run_studio_generation(self):
        if not self.db:
            messagebox.showwarning("Data Index Void", "Vault must contain documents to generate custom reports.")
            return
        layout_style = self.studio_mode.get()
        self.studio_box.delete("1.0", "end")
        self.studio_box.insert("1.0", f"# ANALYSIS MANIFEST: {layout_style.upper()}\n# Generated on: {datetime.now().strftime('%Y-%m-%d')}\n\n")
        threading.Thread(target=self.async_studio_processor, args=(layout_style,), daemon=True).start()

    def async_studio_processor(self, layout):
        try:
            exploration_query = "Core strategic technical operations overview architecture blueprint data data elements details summary."
            docs = self.db.as_retriever(search_kwargs={"k": 8}).invoke(exploration_query)
            consolidated_text = "\n\n".join([d.page_content for d in docs])
            
            studio_prompt = (
                f"You are a technical document writer. Output a comprehensive {layout} formatted directly using professional raw markdown structures.\n"
                "Break concepts cleanly down into core components, high priority operational elements, structural outlines, and factual summaries."
            )
            
            llm = ChatOllama(
                model=APP_CONFIG["ai_model"],
                temperature=0.3,
                base_url="http://localhost:11434",
                model_kwargs={"repeat_penalty": 1.2}
            )
            
            stream = llm.stream([SystemMessage(content=studio_prompt), HumanMessage(content=f"Data Layers:\n{consolidated_text}")])
            for chunk in stream:
                ui_queue.put(("insert", self.studio_box, chunk.content, ""))
        except Exception as e:
            ui_queue.put(("insert", self.studio_box, f"\n[Studio Processing Fault]: {str(e)}", ""))

    def export_studio_markdown(self):
        p = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown Document", "*.md")])
        if p:
            try:
                txt = self.studio_box.get("1.0", "end-1c")
                with open(p, "w", encoding="utf-8") as f: f.write(txt)
                messagebox.showinfo("Export Confirmed", "Report compiled successfully to filesystem location.")
            except Exception as ex: messagebox.showerror("IO Write Error", str(ex))

    # ====================================================================
    # ADVANCED QUANTUM SETTINGS CONTROL INTERFACE
    # ====================================================================
    def open_advanced_settings(self):
        w = ctk.CTkToplevel(self)
        w.title("Workspace Execution Parameters")
        w.geometry("540x550")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        
        p = ctk.CTkTabview(w)
        p.pack(fill="both", expand=True, padx=15, pady=15)
        
        t1 = p.add("Model Orchestration")
        t2 = p.add("Workspace Interface")
        
        # --- TAB 1: MODEL CONTROLS ---
        ctk.CTkLabel(t1, text="Maximum Predictive Length (Tokens):", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15,2))
        s_tok = ctk.CTkSlider(t1, from_=128, to=2048, number_of_steps=15)
        s_tok.set(APP_CONFIG["max_tokens"])
        s_tok.pack(fill="x", padx=15, pady=2)
        lbl_tok = ctk.CTkLabel(t1, text=f"Current Output Limit: {int(s_tok.get())} tokens", font=("Segoe UI", 11, "italic"))
        lbl_tok.pack(anchor="w", padx=20)
        s_tok.configure(command=lambda v: lbl_tok.configure(text=f"Current Output Limit: {int(float(v))} tokens"))

        ctk.CTkLabel(t1, text="Operational Variance Temperature (Creativity):", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15,2))
        s_temp = ctk.CTkSlider(t1, from_=0.0, to=1.2, number_of_steps=24)
        s_temp.set(APP_CONFIG["temperature"])
        s_temp.pack(fill="x", padx=15, pady=2)
        lbl_temp = ctk.CTkLabel(t1, text=f"Variance Index: {s_temp.get():.2f}", font=("Segoe UI", 11, "italic"))
        lbl_temp.pack(anchor="w", padx=20)
        s_temp.configure(command=lambda v: lbl_temp.configure(text=f"Variance Index: {float(v):.2f}"))

        ctk.CTkLabel(t1, text="Structural Repetition Penalty Engine Filter:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15,2))
        s_rep = ctk.CTkSlider(t1, from_=1.0, to=1.8, number_of_steps=16)
        s_rep.set(APP_CONFIG["repeat_penalty"])
        s_rep.pack(fill="x", padx=15, pady=2)
        lbl_rep = ctk.CTkLabel(t1, text=f"Penalty Scalar: {s_rep.get():.2f}", font=("Segoe UI", 11, "italic"))
        lbl_rep.pack(anchor="w", padx=20)
        s_rep.configure(command=lambda v: lbl_rep.configure(text=f"Penalty Scalar: {float(v):.2f}"))

        ctk.CTkLabel(t1, text="Vector Ingestion Chunk Pull Limit (K-Depth):", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15,2))
        s_dep = ctk.CTkSlider(t1, from_=2, to=12, number_of_steps=10)
        s_dep.set(APP_CONFIG["chunk_depth"])
        s_dep.pack(fill="x", padx=15, pady=2)
        lbl_dep = ctk.CTkLabel(t1, text=f"Context Block Target Count: {int(s_dep.get())} sections", font=("Segoe UI", 11, "italic"))
        lbl_dep.pack(anchor="w", padx=20)
        s_dep.configure(command=lambda v: lbl_dep.configure(text=f"Context Block Target Count: {int(float(v))} sections"))

        # --- TAB 2: INTERFACE CONTROLS ---
        ctk.CTkLabel(t2, text="Interface Structural Theme Color Mode:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15,2))
        m_theme = ctk.CTkOptionMenu(t2, values=["Dark", "Light"], width=420)
        m_theme.set(APP_CONFIG["theme_mode"])
        m_theme.pack(padx=15, pady=5)

        ctk.CTkLabel(t2, text="Visual UI Highlights Accent Mapping Palette:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15,2))
        m_color = ctk.CTkOptionMenu(t2, values=["blue", "green", "dark-blue"], width=420)
        m_color.set(APP_CONFIG["accent_color"])
        m_color.pack(padx=15, pady=5)

        def save_and_apply_workspace_parameters():
            APP_CONFIG["max_tokens"] = int(s_tok.get())
            APP_CONFIG["temperature"] = round(s_temp.get(), 2)
            APP_CONFIG["repeat_penalty"] = round(s_rep.get(), 2)
            APP_CONFIG["chunk_depth"] = int(s_dep.get())
            APP_CONFIG["theme_mode"] = m_theme.get()
            APP_CONFIG["accent_color"] = m_color.get()
            
            with open(SAVE_FILE, "w") as config_out:
                json.dump(APP_CONFIG, config_out, indent=4)
            
            ctk.set_appearance_mode(APP_CONFIG["theme_mode"])
            w.destroy()
            messagebox.showinfo("Matrix Synced", "Workspace preferences updated across active runtime segments.")

        ctk.CTkButton(w, text="COMMIT RADIAL VALUES & APPLY SETUP", font=("Segoe UI", 13, "bold"), height=42, command=save_and_apply_workspace_parameters).pack(side="bottom", fill="x", padx=20, pady=15)

if __name__ == "__main__":
    app = SourceAgentMaster()
    app.mainloop()
