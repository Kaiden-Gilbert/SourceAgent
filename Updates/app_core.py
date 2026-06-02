import os, threading, shutil, json, time
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
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
ENV_FILE = os.path.join(BASE_DIR, ".env")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(SOURCE_DIR, exist_ok=True)

# --- STRICT VERIFICATION PROMPTS ---
EVALUATOR_PROMPT = """You are a RAG Verification Agent.
Evaluate if the provided context contains sufficient evidence to answer the user's query.
Respond ONLY with "SUFFICIENT" or "INSUFFICIENT"."""

GENERATOR_PROMPT = """You are "Source Agent 2026." 
CORE PRINCIPLE: Source Truth Policy.
1. Answer ONLY using information found in the provided context.
2. NEVER invent, guess, or hallucinate.
3. If information is missing, explicitly state: "I cannot find information regarding this topic within the provided sources."
4. Every factual claim must be verifiable from the text."""

# ==========================================
# WINDOW CLASS: DEDICATED CHAT & EVIDENCE VIEWER
# ==========================================
class DedicatedChatWindow(ctk.CTkToplevel):
    def __init__(self, master, app_core):
        super().__init__(master)
        self.parent = app_core
        self.title("Agentic Session Terminal")
        self.geometry("850x600")
        self.current_evidence = ""
        
        # Layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), fg_color="#020617", spacing1=5, spacing3=5)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.chat.insert("1.0", "SYSTEM: Agentic retrieval loop active. Strict grounding enforced.\n\n")
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=45, placeholder_text="Ask a grounded question...")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send())
        
        ctk.CTkButton(input_frame, text="🔍 View Evidence", width=120, height=45, fg_color="#475569", hover_color="#334155", command=self.show_evidence).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(input_frame, text="Submit", width=100, height=45, fg_color="#3b82f6", command=self.send).grid(row=0, column=2)
    
    def send(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.parent.agentic_generate, args=(q, self.chat, self), daemon=True).start()

    def show_evidence(self):
        if not self.current_evidence:
            messagebox.showinfo("Evidence Viewer", "No evidence currently loaded in memory.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Raw Evidence Viewer")
        win.geometry("650x500")
        win.attributes("-topmost", True)
        box = ctk.CTkTextbox(win, font=("Consolas", 12), fg_color="#0f172a", text_color="#34d399")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", "--- RAW RETRIEVAL DATA ---\n\n" + self.current_evidence)
        box.configure(state="disabled")

# ==========================================
# MAIN APPLICATION ENGINE
# ==========================================
class PolicyAdvisorMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Native Apex V29")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        self.ai_model = "google/gemini-1.5-flash:free"
        self.app_password = ""
        self.load_settings()
        
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        
        self.setup_ui()
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        s = ctk.CTkFrame(self, width=260, fg_color="#020617")
        s.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 20, "bold")).pack(pady=(25, 20))
        ctk.CTkButton(s, text="⧉ Agentic Chat", font=("Segoe UI", 13, "bold"), fg_color="#10b981", hover_color="#059669", command=lambda: DedicatedChatWindow(self, self)).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="📂 Ingest Sources", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="⚙️ Security & API", font=("Segoe UI", 13), fg_color="#334155", command=self.open_settings).pack(fill="x", padx=15, pady=8)
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#0f172a", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat.insert("1.0", "SYSTEM: Native RAG Pipeline initialized. Awaiting queries...\n\n")
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, height=50, placeholder_text="Ask a grounded question...", font=("Segoe UI", 14))
        self.entry.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.entry.bind("<Return>", lambda e: self.send_main())

    def send_main(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.agentic_generate, args=(q, self.chat, None), daemon=True).start()

    def log_audit(self, query, status):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "status": status}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

    # --- THREAD-SAFE UI UPDATER ---
    def safe_insert(self, target, text, replace_thinking=False):
        def _update():
            target.configure(state="normal")
            if replace_thinking:
                target.delete("end-30c", "end") # Rough estimate to clear the 'Thinking...' line
            target.insert("end", text)
            target.see("end")
            target.configure(state="disabled")
        self.after(0, _update)

    # --- THE AGENTIC RETRIEVAL LOOP ---
    def agentic_generate(self, q, target, chat_window_instance=None):
        self.safe_insert(target, f"\nUSER: {q}\n")
        
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model, temperature=0.0)
            
            # STEP 1: Initial Retrieval
            self.safe_insert(target, "AGENT: Searching sources...\n")
            docs = self.db.as_retriever(search_kwargs={"k": 5}).invoke(q) if self.db else []
            context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')} | Page: {d.metadata.get('page', 'N/A')}\n{d.page_content}" for d in docs])
            sources_list = list(set([d.metadata.get('source', 'Unknown Document') for d in docs]))
            
            # STEP 2: Evaluation Loop
            eval_resp = llm.invoke([SystemMessage(content=EVALUATOR_PROMPT), HumanMessage(content=f"Context:\n{context}\n\nQuery: {q}")]).content
            
            if "INSUFFICIENT" in eval_resp.upper() and self.db:
                self.safe_insert(target, "AGENT: Evidence insufficient. Triggering Deep Search...\n")
                # Expand search scope
                docs = self.db.as_retriever(search_kwargs={"k": 12}).invoke(q)
                context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')} | Page: {d.metadata.get('page', 'N/A')}\n{d.page_content}" for d in docs])
                sources_list = list(set([d.metadata.get('source', 'Unknown Document') for d in docs]))

            if chat_window_instance:
                chat_window_instance.current_evidence = context if context else "No evidence found."

            # STEP 3: Verified Generation
            self.safe_insert(target, "AGENT: Synthesizing verified response...\n")
            
            final_resp = llm.invoke([SystemMessage(content=GENERATOR_PROMPT), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]).content
            
            # Format Citations
            citations = ", ".join(sources_list) if sources_list else "None"
            final_output = f"\n{final_resp}\n\n[Sources Referenced: {citations}]\n---\n"
            
            self.safe_insert(target, final_output)
            self.log_audit(q, "Success")
            
        except Exception as e: 
            self.safe_insert(target, f"\nSystem Error: {e}\n\n---\n")
            self.log_audit(q, f"Error: {str(e)}")

    # --- ADVANCED INGESTION & METADATA CHUNKING ---
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
            messagebox.showinfo("Processing", "Documents added. Deep indexing in background...")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): 
                loader = PyMuPDFLoader(os.path.join(SOURCE_DIR, f))
                docs.extend(loader.load())
        
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=250, separators=["\n\n", "\n", ".", " "])
            split_docs = splitter.split_documents(docs)
            for d in split_docs:
                d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
                
            self.db = FAISS.from_documents(split_docs, self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

    # --- SETTINGS ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Security & Credentials")
        win.geometry("450x300")
        win.attributes("-topmost", True)
        win.configure(fg_color="#0f172a")
        
        ctk.CTkLabel(win, text="OpenRouter API Key:", font=("Segoe UI", 12)).pack(pady=(20, 5))
        api_entry = ctk.CTkEntry(win, width=370, show="*"); api_entry.insert(0, self.api_key); api_entry.pack()

        ctk.CTkLabel(win, text="App Vault Password:", font=("Segoe UI", 12)).pack(pady=(15, 5))
        pwd_entry = ctk.CTkEntry(win, width=370, show="*"); pwd_entry.insert(0, self.app_password); pwd_entry.pack()

        def apply_changes():
            self.app_password = pwd_entry.get()
            with open(SAVE_FILE, "w") as f: json.dump({"app_password": self.app_password}, f)
            new_key = api_entry.get().strip()
            if new_key != self.api_key:
                with open(ENV_FILE, "w") as f: f.write(f"OPENROUTER_API_KEY={new_key}\n")
                self.api_key = new_key
                os.environ["OPENROUTER_API_KEY"] = new_key
            win.destroy()
            
        ctk.CTkButton(win, text="Apply", fg_color="#3b82f6", command=apply_changes).pack(pady=30)

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.app_password = d.get("app_password", "")
            except: pass

if __name__ == "__main__":
    app = PolicyAdvisorMaster()
    app.mainloop()
