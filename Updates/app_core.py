import os, sys, threading, subprocess, json, time, textwrap
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

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
HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")

for d in [SERVER_DIR, SOURCE_DIR]:
    os.makedirs(d, exist_ok=True)

# ==========================================
# PART 1: THE BACKEND SERVER GENERATOR
# ==========================================
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
        
        docs = db.as_retriever(search_kwargs={{"k": 5}}).invoke(req.query)
        context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}} | Page: {{d.metadata.get('page')}}\\n{{d.page_content}}" for d in docs])
        sources = list(set([d.metadata.get('source') for d in docs]))
        
        eval_resp = llm.invoke([SystemMessage(content="Evaluate if context answers the query. Reply SUFFICIENT or INSUFFICIENT."), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
        
        if "INSUFFICIENT" in eval_resp.upper():
            docs = db.as_retriever(search_kwargs={{"k": 12}}).invoke(req.query)
            context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}} | Page: {{d.metadata.get('page')}}\\n{{d.page_content}}" for d in docs])
            sources = list(set([d.metadata.get('source') for d in docs]))

        sys_prompt = "You are Source Agent. Answer ONLY using context. Quote verbatim. If missing, say 'I cannot find this.' Every claim needs a citation."
        final_resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
        
        return {{"answer": final_resp, "sources": sources, "raw_evidence": context, "deep_search": "INSUFFICIENT" in eval_resp.upper()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="critical")
""")

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
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), spacing1=5, spacing3=5)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=45, placeholder_text="Ask a grounded question...")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send())
        
        ctk.CTkButton(input_frame, text="🔍 View Evidence", width=120, height=45, fg_color="#475569", command=self.show_evidence).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(input_frame, text="Submit", width=100, height=45, command=self.send).grid(row=0, column=2)
    
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
        box = ctk.CTkTextbox(win, font=("Consolas", 12), text_color="#34d399")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", "--- RAW RETRIEVAL DATA ---\n\n" + self.current_evidence)
        box.configure(state="disabled")

class SourceAgentClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Enterprise Workspace")
        self.geometry("1250x800")
        
        # Load Preferences
        self.api_key = ""
        self.ai_model = "google/gemini-1.5-flash:free"
        self.app_password = ""
        self.theme_mode = "Dark"
        self.accent_color = "blue"
        self.chat_history_data = []
        
        self.load_settings()
        
        # Apply Presets
        ctk.set_appearance_mode(self.theme_mode)
        ctk.set_default_color_theme(self.accent_color)
        
        self.setup_ui()
        self.load_chat_history_to_ui()
        self.start_backend_server()

    def start_backend_server(self):
        if not self.chat_history_data:
            self.safe_insert(self.chat, "SYSTEM: Igniting background microservice engine...\n")
            
        self.server_process = subprocess.Popen([sys.executable, SERVER_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        threading.Thread(target=self.wait_for_server, daemon=True).start()

    def wait_for_server(self):
        for _ in range(15):
            try:
                res = requests.get("http://127.0.0.1:8050/ping", timeout=1)
                if res.status_code == 200:
                    if not self.chat_history_data:
                        self.safe_insert(self.chat, "SYSTEM: Microservice connection established. Ready for queries.\n\n")
                    return
            except: time.sleep(1)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        # Modern Sidebar
        s = ctk.CTkFrame(self, width=280, corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 30))
        
        # Action Buttons
        ctk.CTkButton(s, text="⧉ Open Dedicated Terminal", font=("Segoe UI", 13, "bold"), fg_color="#10b981", hover_color="#059669", height=45, command=lambda: DedicatedChatWindow(self, self)).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(s, text="📂 Ingest Policy Docs", font=("Segoe UI", 13), height=40, command=self.add_docs).pack(fill="x", padx=20, pady=10)
        
        # Bottom tools
        bottom_frame = ctk.CTkFrame(s, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=20)
        ctk.CTkButton(bottom_frame, text="🧹 Clear History", font=("Segoe UI", 13), fg_color="#ef4444", hover_color="#dc2626", command=self.clear_main_chat).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(bottom_frame, text="⚙️ Workspace Settings", font=("Segoe UI", 13), fg_color="#475569", command=self.open_settings).pack(fill="x", padx=20, pady=5)
        
        # Chat Area
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1); main_frame.grid_rowconfigure(0, weight=1)
        
        self.chat = ctk.CTkTextbox(main_frame, font=("Segoe UI", 15), spacing1=10, spacing3=10, corner_radius=10)
        self.chat.grid(row=0, column=0, sticky="nsew", pady=(0, 20))
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(main_frame, corner_radius=10)
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=55, placeholder_text="Ask a grounded compliance question...", border_width=0, font=("Segoe UI", 15))
        self.entry.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.entry.bind("<Return>", lambda e: self.send_main())
        ctk.CTkButton(input_frame, text="Send", width=100, height=45, font=("Segoe UI", 14, "bold"), command=self.send_main).grid(row=0, column=1, padx=10)

    # --- PERSISTENCE ENGINE ---
    def load_chat_history_to_ui(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.chat_history_data = json.load(f)
                    if self.chat_history_data:
                        self.chat.configure(state="normal")
                        for msg in self.chat_history_data:
                            self.chat.insert("end", f"{msg['role']}: {msg['content']}\n")
                        self.chat.insert("end", "\n--- Session Restored ---\n\n")
                        self.chat.see("end")
                        self.chat.configure(state="disabled")
            except: pass

    def save_chat_to_file(self, role, content):
        self.chat_history_data.append({"role": role, "content": content})
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.chat_history_data, f, indent=4)

    def clear_main_chat(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to delete this conversation permanently?"):
            self.chat_history_data = []
            if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
            self.chat.configure(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.insert("1.0", "SYSTEM: Dashboard memory wiped. Ready for new inquiry.\n\n")
            self.chat.configure(state="disabled")

    def safe_insert(self, target, text, role=None, raw_content=None):
        def _update():
            target.configure(state="normal")
            target.insert("end", text)
            target.see("end")
            target.configure(state="disabled")
            if role and raw_content and target == self.chat:
                self.save_chat_to_file(role, raw_content)
        self.after(0, _update)

    def send_main(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.query_backend, args=(q, self.chat, None), daemon=True).start()

    def query_backend(self, q, target, chat_window_instance=None):
        self.safe_insert(target, f"\nUSER: {q}\n", "USER", q)
        
        if not self.api_key:
            self.safe_insert(target, "CRITICAL: OpenRouter API key missing. Configure in settings.\n---\n")
            return

        try:
            res = requests.post("http://127.0.0.1:8050/agentic_query/", json={"query": q, "api_key": self.api_key, "model": self.ai_model})
            if res.status_code == 200:
                data = res.json()
                if chat_window_instance: chat_window_instance.current_evidence = data.get("raw_evidence", "No evidence.")
                
                sources = ", ".join(data.get("sources", [])) if data.get("sources") else "None"
                final_answer = data.get('answer')
                display_output = f"AGENT: {final_answer}\n\n[Sources Referenced: {sources}]\n---\n"
                
                self.safe_insert(target, display_output, "AGENT", f"{final_answer} [Sources: {sources}]")
            else:
                self.safe_insert(target, f"Server Error: {res.json().get('detail')}\n---\n")
        except requests.exceptions.ConnectionError:
            self.safe_insert(target, "CRITICAL: Backend microservice is unreachable.\n---\n")

    # --- ADVANCED SETTINGS TABVIEW ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Workspace Settings")
        win.geometry("500x450")
        win.attributes("-topmost", True)
        
        tabs = ctk.CTkTabview(win)
        tabs.pack(fill="both", expand=True, padx=20, pady=20)
        
        # TAB 1: API & Security
        tab_api = tabs.add("Credentials")
        ctk.CTkLabel(tab_api, text="OpenRouter API Key:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10,5))
        api_entry = ctk.CTkEntry(tab_api, width=400, show="*"); api_entry.insert(0, self.api_key); api_entry.pack()
        
        ctk.CTkLabel(tab_api, text="Vault Password:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(15,5))
        pwd_entry = ctk.CTkEntry(tab_api, width=400, show="*"); pwd_entry.insert(0, self.app_password); pwd_entry.pack()

        # TAB 2: Appearance
        tab_look = tabs.add("Appearance")
        ctk.CTkLabel(tab_look, text="UI Theme Mode:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10,5))
        theme_menu = ctk.CTkOptionMenu(tab_look, values=["Dark", "Light", "System"], width=400)
        theme_menu.set(self.theme_mode.capitalize()); theme_menu.pack()
        
        ctk.CTkLabel(tab_look, text="Accent Color Preset (Requires Restart):", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(15,5))
        color_menu = ctk.CTkOptionMenu(tab_look, values=["blue", "green", "dark-blue"], width=400)
        color_menu.set(self.accent_color); color_menu.pack()

        def apply_changes():
            self.api_key = api_entry.get().strip()
            self.app_password = pwd_entry.get()
            self.theme_mode = theme_menu.get()
            self.accent_color = color_menu.get()
            
            # Apply instantly where possible
            ctk.set_appearance_mode(self.theme_mode)
            
            with open(SAVE_FILE, "w") as f: 
                json.dump({
                    "api_key": self.api_key, 
                    "app_password": self.app_password,
                    "theme_mode": self.theme_mode,
                    "accent_color": self.accent_color
                }, f)
            win.destroy()
            
        ctk.CTkButton(win, text="Save Workspace Preferences", font=("Segoe UI", 14, "bold"), height=45, command=apply_changes).pack(pady=(0, 20), padx=20, fill="x")

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Documents", "*.pdf")])
        if files:
            threading.Thread(target=self.upload_to_backend, args=(files,), daemon=True).start()
            messagebox.showinfo("Processing", "Transmitting to ingestion microservice...")

    def upload_to_backend(self, files):
        for file_path in files:
            try:
                with open(file_path, "rb") as f:
                    requests.post("http://127.0.0.1:8050/ingest/", files={"file": (os.path.basename(file_path), f, "application/pdf")})
            except Exception as e: print(f"Ingest error: {e}")

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.api_key = d.get("api_key", "")
                    self.app_password = d.get("app_password", "")
                    self.theme_mode = d.get("theme_mode", "Dark")
                    self.accent_color = d.get("accent_color", "blue")
            except: pass

    def destroy(self):
        if hasattr(self, 'server_process'): self.server_process.terminate()
        super().destroy()

if __name__ == "__main__":
    app = SourceAgentClient()
    app.mainloop()
