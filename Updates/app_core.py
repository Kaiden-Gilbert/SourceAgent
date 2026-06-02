import os, sys, threading, subprocess, json, time, textwrap
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import urllib.request

# We use requests in the client to talk to our own background server
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "fastapi", "uvicorn"])
    import requests

# --- CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SERVER_DIR = os.path.join(BASE_DIR, "Microservices")
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
ENV_FILE = os.path.join(BASE_DIR, ".env")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")

for d in [SERVER_DIR, SOURCE_DIR]:
    os.makedirs(d, exist_ok=True)

# ==========================================
# PART 1: THE BACKEND SERVER GENERATOR
# ==========================================
# This writes the heavy-lifting Brain to a separate file so it runs in its own process.
BACKEND_CODE = textwrap.dedent(f"""\
import os, json, shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import uvicorn
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage

app = FastAPI(title="Source Agent Core Brain")

SOURCE_DIR = r"{SOURCE_DIR}"
INDEX_DIR = os.path.join(SOURCE_DIR, "faiss_index")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class QueryRequest(BaseModel):
    query: str
    api_key: str
    model: str

def get_db():
    if os.path.exists(INDEX_DIR):
        try: return FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
        except: return None
    return None

@app.get("/ping")
def ping(): return {{"status": "online"}}

@app.post("/ingest/")
async def ingest_document(file: UploadFile = File(...)):
    # Future integration point for LayoutLM Table Extraction OCR
    file_path = os.path.join(SOURCE_DIR, file.filename)
    with open(file_path, "wb") as f: shutil.copyfileobj(file.file, f)
    
    docs = PyMuPDFLoader(file_path).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    split_docs = splitter.split_documents(docs)
    for d in split_docs: d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
        
    db = get_db()
    if db: db.add_documents(split_docs)
    else: db = FAISS.from_documents(split_docs, embeddings)
    db.save_local(INDEX_DIR)
    
    return {{"status": "indexed"}}

@app.post("/agentic_query/")
async def agentic_query(req: QueryRequest):
    db = get_db()
    if not db: raise HTTPException(status_code=400, detail="No sources indexed.")
    
    try:
        llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=req.api_key, model=req.model, temperature=0.0)
        
        # 1. Base Retrieval
        docs = db.as_retriever(search_kwargs={{"k": 5}}).invoke(req.query)
        context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}} | Page: {{d.metadata.get('page')}}\\n{{d.page_content}}" for d in docs])
        sources = list(set([d.metadata.get('source') for d in docs]))
        
        # 2. Agentic Evaluation (Future integration for Cross-Encoder Reranking)
        eval_resp = llm.invoke([SystemMessage(content="Evaluate if context answers the query. Reply SUFFICIENT or INSUFFICIENT."), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
        
        if "INSUFFICIENT" in eval_resp.upper():
            # Deep Search
            docs = db.as_retriever(search_kwargs={{"k": 12}}).invoke(req.query)
            context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}} | Page: {{d.metadata.get('page')}}\\n{{d.page_content}}" for d in docs])
            sources = list(set([d.metadata.get('source') for d in docs]))

        # 3. Grounded Generation
        sys_prompt = "You are Source Agent. Answer ONLY using context. Quote verbatim. If missing, say 'I cannot find this.' Every claim needs a citation."
        final_resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
        
        return {{"answer": final_resp, "sources": sources, "raw_evidence": context, "deep_search": "INSUFFICIENT" in eval_resp.upper()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="critical")
""")

# Write the backend server file
SERVER_FILE = os.path.join(SERVER_DIR, "backend_engine.py")
with open(SERVER_FILE, "w", encoding="utf-8") as f:
    f.write(BACKEND_CODE)

# ==========================================
# PART 2: THE NATIVE DESKTOP CLIENT
# ==========================================
class DedicatedChatWindow(ctk.CTkToplevel):
    def __init__(self, master, app_core):
        super().__init__(master)
        self.parent = app_core
        self.title("Agentic Session Terminal")
        self.geometry("850x600")
        self.current_evidence = ""
        
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), fg_color="#020617", spacing1=5, spacing3=5)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=45, placeholder_text="Ask a grounded question...")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send())
        
        ctk.CTkButton(input_frame, text="🔍 View Evidence", width=120, height=45, fg_color="#475569", command=self.show_evidence).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(input_frame, text="Submit", width=100, height=45, fg_color="#3b82f6", command=self.send).grid(row=0, column=2)
    
    def send(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.parent.query_backend, args=(q, self.chat, self), daemon=True).start()

    def show_evidence(self):
        if not self.current_evidence:
            messagebox.showinfo("Evidence Viewer", "No evidence currently loaded.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Raw Evidence Viewer")
        win.geometry("650x500")
        box = ctk.CTkTextbox(win, font=("Consolas", 12), fg_color="#0f172a", text_color="#34d399")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", "--- RAW RETRIEVAL DATA ---\\n\\n" + self.current_evidence)
        box.configure(state="disabled")

class SourceAgentClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Hybrid Apex V30")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        self.api_key = ""
        self.ai_model = "google/gemini-1.5-flash:free"
        self.app_password = ""
        self.load_settings()
        
        self.setup_ui()
        self.start_backend_server()

    def start_backend_server(self):
        self.chat.configure(state="normal")
        self.chat.insert("end", "SYSTEM: Igniting background microservice engine...\n")
        self.chat.configure(state="disabled")
        
        # Launch the FastAPI server in the background
        self.server_process = subprocess.Popen(
            [sys.executable, SERVER_FILE],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        # Wait for server to come online
        threading.Thread(target=self.wait_for_server, daemon=True).start()

    def wait_for_server(self):
        for _ in range(15):
            try:
                res = requests.get("http://127.0.0.1:8050/ping", timeout=1)
                if res.status_code == 200:
                    self.safe_insert(self.chat, "SYSTEM: Microservice connection established. Ready for queries.\n\n")
                    return
            except:
                time.sleep(1)
        self.safe_insert(self.chat, "CRITICAL: Background server failed to start.\n")

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        s = ctk.CTkFrame(self, width=260, fg_color="#020617")
        s.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 20, "bold")).pack(pady=(25, 20))
        ctk.CTkButton(s, text="⧉ Agentic Chat", font=("Segoe UI", 13, "bold"), fg_color="#10b981", command=lambda: DedicatedChatWindow(self, self)).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="📂 Ingest Sources", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(s, text="⚙️ Security & API", font=("Segoe UI", 13), fg_color="#334155", command=self.open_settings).pack(fill="x", padx=15, pady=8)
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#0f172a", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, height=50, placeholder_text="Ask a grounded question...", font=("Segoe UI", 14))
        self.entry.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.entry.bind("<Return>", lambda e: self.send_main())

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
        threading.Thread(target=self.query_backend, args=(q, self.chat, None), daemon=True).start()

    def query_backend(self, q, target, chat_window_instance=None):
        self.safe_insert(target, f"\nUSER: {q}\nAGENT: Processing via microservice...\n")
        
        if not self.api_key:
            self.safe_insert(target, "CRITICAL: OpenRouter API key missing. Configure in settings.\n---\n")
            return

        payload = {"query": q, "api_key": self.api_key, "model": self.ai_model}
        
        try:
            res = requests.post("http://127.0.0.1:8050/agentic_query/", json=payload)
            if res.status_code == 200:
                data = res.json()
                
                if data.get("deep_search"):
                    self.safe_insert(target, "AGENT: Triggered Deep Search Expansion...\n")
                
                if chat_window_instance:
                    chat_window_instance.current_evidence = data.get("raw_evidence", "No evidence.")
                
                sources = ", ".join(data.get("sources", [])) if data.get("sources") else "None"
                final_output = f"\n{data.get('answer')}\n\n[Sources Referenced: {sources}]\n---\n"
                self.safe_insert(target, final_output)
            else:
                self.safe_insert(target, f"\nServer Error: {res.json().get('detail')}\n---\n")
        except requests.exceptions.ConnectionError:
            self.safe_insert(target, "\nCRITICAL: Backend microservice is unreachable.\n---\n")

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Documents", "*.pdf")])
        if files:
            threading.Thread(target=self.upload_to_backend, args=(files,), daemon=True).start()
            messagebox.showinfo("Processing", "Transmitting to ingestion microservice...")

    def upload_to_backend(self, files):
        for file_path in files:
            try:
                with open(file_path, "rb") as f:
                    files_payload = {"file": (os.path.basename(file_path), f, "application/pdf")}
                    requests.post("http://127.0.0.1:8050/ingest/", files=files_payload)
            except Exception as e:
                print(f"Ingest error: {e}")

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.api_key = d.get("api_key", "")
                    self.app_password = d.get("app_password", "")
            except: pass

    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Security & API")
        win.geometry("450x300")
        win.attributes("-topmost", True)
        
        ctk.CTkLabel(win, text="OpenRouter API Key:").pack(pady=(20, 5))
        api_entry = ctk.CTkEntry(win, width=370, show="*"); api_entry.insert(0, self.api_key); api_entry.pack()

        def apply_changes():
            self.api_key = api_entry.get().strip()
            with open(SAVE_FILE, "w") as f: json.dump({"api_key": self.api_key, "app_password": self.app_password}, f)
            win.destroy()
            
        ctk.CTkButton(win, text="Apply", command=apply_changes).pack(pady=30)

    def destroy(self):
        if hasattr(self, 'server_process'):
            self.server_process.terminate()
        super().destroy()

if __name__ == "__main__":
    app = SourceAgentClient()
    app.mainloop()
