import os, threading, shutil, json, urllib.request
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
import math

# --- CONFIGURATION & PATHS ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
ENV_FILE = os.path.join(BASE_DIR, ".env")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(SOURCE_DIR, exist_ok=True)

# --- STRICT COMPLIANCE DIRECTIVE ---
SYSTEM_PROMPT = """You are "Policy Advisor 2026." 
1. Answer strictly using provided policy docs.
2. Quote verbatim where applicable. 
3. Separate quotes from your plain English explanation.
4. NO hallucinations. If the answer is missing, state: "I cannot find a policy regarding this."
5. Tone: Clinical, professional, precise."""

# ==========================================
# WINDOW CLASS: DEDICATED CHAT
# ==========================================
class DedicatedChatWindow(ctk.CTkToplevel):
    def __init__(self, master, app_core):
        super().__init__(master)
        self.parent = app_core
        self.title("Session Terminal")
        self.geometry("750x550")
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), fg_color="#020617", spacing1=5, spacing3=5)
        self.chat.pack(fill="both", expand=True, padx=15, pady=15)
        self.chat.insert("1.0", "SYSTEM: Dedicated isolated session established.\n\n")
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, height=45, placeholder_text="Ask a compliance question...")
        self.entry.pack(fill="x", padx=15, pady=(0, 15))
        self.entry.bind("<Return>", lambda e: self.send())
    
    def send(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.parent.ai_generate, args=(q, self.chat), daemon=True).start()

# ==========================================
# MAIN APPLICATION ENGINE
# ==========================================
class PolicyAdvisorMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise V25")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        # Core Engine Settings
        self.ai_model = "google/gemini-1.5-flash:free"
        self.app_password = ""
        self.load_settings()
        
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        
        self.setup_ui()
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()
        
        # ACTIVE API VALIDATION IN BACKGROUND
        threading.Thread(target=self.verify_api_key, daemon=True).start()

    def verify_api_key(self):
        """Actively ping OpenRouter authentication servers to ensure the key is live."""
        self.after(0, lambda: self.status_lbl.configure(text="● Verifying Credentials...", text_color="#f59e0b"))
        time.sleep(0.5) # Brief pause for UI fluidity
        
        if not self.api_key or len(self.api_key) < 10:
            self.after(0, self.trigger_key_failure, "● API Key Missing!")
            return

        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {self.api_key}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.getcode() == 200:
                    self.after(0, lambda: self.status_lbl.configure(text="● Engine Online", text_color="#10b981"))
                else:
                    self.after(0, self.trigger_key_failure, "● API Key Rejected!")
        except Exception:
            self.after(0, self.trigger_key_failure, "● Invalid API Key!")

    def trigger_key_failure(self, message):
        """Handle UI response when API key is bad."""
        self.status_lbl.configure(text=message, text_color="#ef4444")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"CRITICAL: The system detected an invalid or missing API key.\nPlease open Settings to update your OpenRouter credentials.\n\n---\n")
        self.chat.configure(state="disabled")

    def update_env_file(self, new_key):
        """Saves a new API key directly to the environment file and re-validates."""
        with open(ENV_FILE, "w") as f:
            f.write(f"OPENROUTER_API_KEY={new_key}\n")
        self.api_key = new_key
        os.environ["OPENROUTER_API_KEY"] = new_key
        threading.Thread(target=self.verify_api_key, daemon=True).start()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar Navigation
        s = ctk.CTkFrame(self, width=260, fg_color="#020617")
        s.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(s, text="🏛️ Policy Advisor", font=("Segoe UI", 20, "bold")).pack(pady=(25, 20))
        ctk.CTkButton(s, text="⧉ Dedicated Chat", font=("Segoe UI", 13, "bold"), fg_color="#10b981", hover_color="#059669", command=lambda: DedicatedChatWindow(self, self)).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="📂 Upload Policies", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="⚙️ Settings", font=("Segoe UI", 13), fg_color="#334155", command=self.open_settings).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="🧹 Clear Dashboard", font=("Segoe UI", 13), fg_color="#334155", command=self.clear_chat).pack(fill="x", padx=15, pady=8)
        
        self.status_lbl = ctk.CTkLabel(s, text="● Initializing...", text_color="#94a3b8", font=("Segoe UI", 12, "bold"))
        self.status_lbl.pack(side="bottom", pady=20)

        # Main Dashboard Chat
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#0f172a", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat.insert("1.0", "SYSTEM: Enterprise Module booting sequence initiated...\n\n")
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, height=50, placeholder_text="Ask a compliance or policy question...", font=("Segoe UI", 14))
        self.entry.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.entry.bind("<Return>", lambda e: self.send_main())

    def clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.insert("1.0", "SYSTEM: Dashboard memory wiped. Ready for new inquiry.\n\n")
        self.chat.configure(state="disabled")

    def send_main(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.ai_generate, args=(q, self.chat), daemon=True).start()

    def log_audit(self, query, sources):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "sources_referenced": sources}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

    def ai_generate(self, q, target):
        target.configure(state="normal")
        target.insert("end", f"\nUSER: {q}\n\nADVISOR: Thinking...")
        target.see("end")
        
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model)
            context = ""
            sources_list = []
            
            if self.db:
                docs = self.db.as_retriever(search_kwargs={"k": 6}).invoke(q)
                context = "\n\n".join([d.page_content for d in docs])
                sources_list = list(set([os.path.basename(d.metadata.get('source', 'Unknown Document')) for d in docs]))
                
            resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]).content
            
            target.delete("end-12c", "end") 
            target.insert("end", f"{resp}\n\n")
            
            if sources_list:
                citations = ", ".join(sources_list)
                target.insert("end", f"[Sources Referenced: {citations}]\n")
                
            target.insert("end", "---\n")
            self.log_audit(q, sources_list)
            
        except Exception as e: 
            target.delete("end-12c", "end")
            target.insert("end", f"System Error: API Key or Connection issue detected.\nDetails: {e}\n\n---\n")
            
        target.configure(state="disabled")
        target.see("end")

    # --- ADVANCED SETTINGS MENU ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Advanced Configuration")
        win.geometry("450x450")
        win.attributes("-topmost", True)
        win.configure(fg_color="#0f172a")
        
        ctk.CTkLabel(win, text="System Configuration", font=("Segoe UI", 22, "bold")).pack(pady=20)
        
        ctk.CTkLabel(win, text="OpenRouter API Key:", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        api_entry = ctk.CTkEntry(win, width=370, show="*")
        api_entry.insert(0, self.api_key)
        api_entry.pack(pady=5)

        ctk.CTkLabel(win, text="App Vault Password (Optional):", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        pwd_entry = ctk.CTkEntry(win, width=370, show="*")
        pwd_entry.insert(0, self.app_password)
        pwd_entry.pack(pady=5)

        def apply_changes():
            self.app_password = pwd_entry.get()
            self.save_settings()
            
            new_key = api_entry.get().strip()
            if new_key != self.api_key:
                self.update_env_file(new_key)
                
            win.destroy()
            
        ctk.CTkButton(win, text="Apply & Verify", fg_color="#3b82f6", height=40, font=("Segoe UI", 14, "bold"), command=apply_changes).pack(pady=30)

    # --- DATABASE & STORAGE MANAGEMENT ---
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
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            self.db = FAISS.from_documents(splitter.split_documents(docs), self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.app_password = d.get("app_password", "")
            except: pass

    def save_settings(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({"app_password": getattr(self, 'app_password', "")}, f)

if __name__ == "__main__":
    app = PolicyAdvisorMaster()
    app.mainloop()
