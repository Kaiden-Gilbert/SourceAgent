import os, sys, threading, shutil, json, time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from collections import Counter

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# --- CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
ENV_FILE = os.path.join(BASE_DIR, ".env")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(SOURCE_DIR, exist_ok=True)

# --- PROMPT ARCHITECTURE ---
STANDARD_PROMPT = """You are Source Agent. Answer strictly using provided policy docs. Quote verbatim where applicable. If missing, state: 'I cannot find a policy regarding this.'"""

RESEARCH_PROMPT = """You are an Enterprise Research Analyst. 
Conduct a Deep Research synthesis on the provided context. 
1. Identify all core concepts related to the query.
2. Compare evidence across multiple sources if applicable.
3. Generate a highly detailed, structured Executive Report using headings and bullet points.
4. Ensure every factual claim is grounded in the text."""

# ==========================================
# WINDOW CLASS: ANALYTICS DASHBOARD
# ==========================================
class AnalyticsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Enterprise Analytics Dashboard")
        self.geometry("600x500")
        self.attributes("-topmost", True)
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="📊 System Analytics", font=("Segoe UI", 24, "bold"), text_color="#3b82f6").pack(pady=(20, 10))
        
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=10)
        
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 13), fg_color="#0f172a")
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.load_analytics()

    def load_analytics(self):
        if not os.path.exists(AUDIT_FILE):
            self.log_box.insert("1.0", "No audit data found. Start querying to generate analytics.")
            self.log_box.configure(state="disabled")
            return
            
        try:
            with open(AUDIT_FILE, "r") as f:
                logs = json.load(f)
                
            total_queries = len(logs)
            successful = sum(1 for log in logs if log.get("status") == "Success")
            success_rate = (successful / total_queries * 100) if total_queries > 0 else 0
            
            # Extract all sources used
            all_sources = []
            for log in logs:
                sources = log.get("sources", [])
                if isinstance(sources, list):
                    all_sources.extend(sources)
            
            top_sources = Counter(all_sources).most_common(5)
            
            # Display Top Stats
            ctk.CTkLabel(self.stats_frame, text=f"Total Queries: {total_queries}", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
            ctk.CTkLabel(self.stats_frame, text=f"Success Rate: {success_rate:.1f}%", font=("Segoe UI", 16, "bold"), text_color="#10b981").pack(side="right", padx=20)
            
            # Display Source Leaderboard
            report = "--- TOP REFERENCED DOCUMENTS ---\n\n"
            for src, count in top_sources:
                report += f"[{count} references] -> {src}\n"
                
            report += "\n--- RECENT AUDIT TRAIL ---\n\n"
            for log in reversed(logs[-10:]): # Show last 10
                report += f"[{log.get('timestamp', 'Unknown')[:16]}] Query: {log.get('query')}\n"
                
            self.log_box.insert("1.0", report)
            self.log_box.configure(state="disabled")
            
        except Exception as e:
            self.log_box.insert("1.0", f"Error loading analytics: {e}")

# ==========================================
# MAIN APPLICATION ENGINE
# ==========================================
class SourceAgentMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Enterprise Monolith V37")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        self.api_key = ""
        self.ai_model = "google/gemini-1.5-flash:free"
        self.load_settings()
        
        load_dotenv(ENV_FILE)
        if not self.api_key:
            self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
            
        self.setup_ui()
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        s = ctk.CTkFrame(self, width=280, fg_color="#020617", corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 20))
        
        ctk.CTkButton(s, text="📂 Ingest Documents", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(s, text="📊 View Analytics", font=("Segoe UI", 13), fg_color="#8b5cf6", hover_color="#7c3aed", command=lambda: AnalyticsWindow(self)).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(s, text="⚙️ API & Security", font=("Segoe UI", 13), fg_color="#334155", command=self.open_settings).pack(fill="x", padx=20, pady=10)
        
        # Main Dashboard Chat
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#0f172a", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=(20, 10))
        self.chat.insert("1.0", "SYSTEM: Enterprise Monolith Online. Awaiting inquiries...\n\n")
        self.chat.configure(state="disabled")
        
        # Input Area
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=50, placeholder_text="Ask a compliance or policy question...", font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send_main())
        
        # Deep Research Toggle
        self.research_var = ctk.BooleanVar(value=False)
        self.research_switch = ctk.CTkSwitch(input_frame, text="Deep Research Mode", variable=self.research_var, font=("Segoe UI", 12, "bold"), progress_color="#f59e0b")
        self.research_switch.grid(row=0, column=1, padx=(0, 10))
        
        ctk.CTkButton(input_frame, text="Submit", width=100, height=50, fg_color="#3b82f6", font=("Segoe UI", 14, "bold"), command=self.send_main).grid(row=0, column=2)

    def log_audit(self, query, status, sources):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "status": status, "sources": sources}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

    def safe_insert(self, target, text):
        def _update():
            target.configure(state="normal")
            target.insert("end", text)
            target.see("end")
            target.configure(state="disabled")
        self.after(0, _update)

    def send_main(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.engine_generate, args=(q,), daemon=True).start()

    def engine_generate(self, q):
        self.safe_insert(self.chat, f"\nUSER: {q}\n")
        
        if not self.api_key:
            self.safe_insert(self.chat, "CRITICAL: OpenRouter API key missing. Configure in settings.\n---\n")
            return
            
        is_deep_research = self.research_var.get()
        if is_deep_research:
            self.safe_insert(self.chat, "AGENT: Deep Research Initiated. Gathering expanded context...\n")
        else:
            self.safe_insert(self.chat, "AGENT: Thinking...\n")
        
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model, temperature=0.1)
            
            context = ""
            sources_list = []
            
            if self.db:
                # Dynamically adjust retrieval depth based on toggle
                k_depth = 12 if is_deep_research else 5
                docs = self.db.as_retriever(search_kwargs={"k": k_depth}).invoke(q)
                context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')} | Page: {d.metadata.get('page', 'N/A')}\n{d.page_content}" for d in docs])
                sources_list = list(set([d.metadata.get('source', 'Unknown Document') for d in docs]))
                
            sys_prompt = RESEARCH_PROMPT if is_deep_research else STANDARD_PROMPT
            
            final_resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]).content
            
            citations = ", ".join(sources_list) if sources_list else "None"
            final_output = f"\n{final_resp}\n\n[Sources Referenced: {citations}]\n---\n"
            
            self.safe_insert(self.chat, final_output)
            self.log_audit(q, "Success", sources_list)
            
        except Exception as e: 
            self.safe_insert(self.chat, f"\nSystem Error: {e}\n\n---\n")
            self.log_audit(q, f"Error: {str(e)}", [])

    # --- ADVANCED INGESTION ---
    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index):
            try: self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True)
            except: self.db = None

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Documents", "*.pdf")])
        if files:
            for f in files: shutil.copy(f, SOURCE_DIR)
            threading.Thread(target=self.rebuild_db, daemon=True).start()
            messagebox.showinfo("Processing", "Documents added. Indexing in background...")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): 
                loader = PyMuPDFLoader(os.path.join(SOURCE_DIR, f))
                docs.extend(loader.load())
        
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=250)
            split_docs = splitter.split_documents(docs)
            for d in split_docs:
                d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
                
            self.db = FAISS.from_documents(split_docs, self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

    # --- SETTINGS ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Security & Credentials")
        win.geometry("450x200")
        win.attributes("-topmost", True)
        
        ctk.CTkLabel(win, text="OpenRouter API Key:", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
        api_entry = ctk.CTkEntry(win, width=370, show="*")
        api_entry.insert(0, self.api_key)
        api_entry.pack()

        def apply_changes():
            self.api_key = api_entry.get().strip()
            with open(SAVE_FILE, "w") as f: json.dump({"api_key": self.api_key}, f)
            win.destroy()
            
        ctk.CTkButton(win, text="Save Configuration", fg_color="#3b82f6", command=apply_changes).pack(pady=30)

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.api_key = d.get("api_key", "")
            except: pass

if __name__ == "__main__":
    from datetime import datetime
    app = SourceAgentMaster()
    app.mainloop()
