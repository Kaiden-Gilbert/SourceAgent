import os, sys, threading, subprocess, json, time, textwrap
import tkinter as tk
from tkinter import messagebox
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
SAVE_FILE = os.path.join(BASE_DIR, "config.json")

for d in [SERVER_DIR, SOURCE_DIR]:
    os.makedirs(d, exist_ok=True)

# ==========================================
# PART 1: THE NETWORKED BACKEND SERVER
# ==========================================
BACKEND_CODE = textwrap.dedent(f"""\
import os, shutil, time
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage

app = FastAPI(title="Source Agent Nexus Brain")

SOURCE_DIR = r"{SOURCE_DIR}"
INDEX_DIR = os.path.join(SOURCE_DIR, "faiss_index")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

connected_users = set()
message_queue: List[Dict] = []

class QueryRequest(BaseModel):
    query: str
    api_key: str
    model: str
    persona: str

class MessageRequest(BaseModel):
    sender: str
    target: str
    message: str

def get_db():
    if os.path.exists(INDEX_DIR):
        try: return FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
        except: return None
    return None

@app.get("/ping")
def ping(): return {{"status": "online"}}

@app.post("/register/{{username}}")
def register(username: str):
    connected_users.add(username)
    return {{"status": "registered"}}

@app.post("/send_message/")
def send_message(req: MessageRequest):
    message_queue.append({{"id": time.time(), "sender": req.sender, "target": req.target, "msg": req.message}})
    if len(message_queue) > 100: message_queue.pop(0)
    return {{"status": "sent"}}

@app.get("/poll_messages/{{username}}/{{last_id}}")
def poll_messages(username: str, last_id: float):
    new_msgs = [m for m in message_queue if m['id'] > last_id and (m['target'] == 'all' or m['target'] == username)]
    return {{"messages": new_msgs}}

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
    
    personas = {{
        "Policy Strict": "You are a strict compliance advisor. Use ONLY provided context. Quote verbatim.",
        "Creative Brainstorm": "You are a strategic consultant. Use context to brainstorm expansive ideas.",
        "Code Reviewer": "You are a senior developer. Analyze the context for technical accuracy."
    }}
    
    try:
        llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=req.api_key, model=req.model, temperature=0.1)
        docs = db.as_retriever(search_kwargs={{"k": 5}}).invoke(req.query)
        context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}}\\n{{d.page_content}}" for d in docs])
        sources = list(set([d.metadata.get('source') for d in docs]))
        
        final_resp = llm.invoke([SystemMessage(content=personas.get(req.persona, personas["Policy Strict"])), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
        return {{"answer": final_resp, "sources": sources}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8050, log_level="info")
""")

SERVER_FILE = os.path.join(SERVER_DIR, "backend_engine.py")
with open(SERVER_FILE, "w", encoding="utf-8") as f:
    f.write(BACKEND_CODE)

# ==========================================
# PART 2: THE NATIVE NEXUS CLIENT
# ==========================================
class GradientFrame(tk.Canvas):
    def __init__(self, master, color1, color2, **kwargs):
        super().__init__(master, **kwargs)
        self.color1 = color1
        self.color2 = color2
        self.bind('<Configure>', self._draw_gradient)

    def _draw_gradient(self, event=None):
        self.delete("gradient")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1: return
        r1, g1, b1 = self.winfo_rgb(self.color1)
        r2, g2, b2 = self.winfo_rgb(self.color2)
        r_ratio = (r2 - r1) / height
        g_ratio = (g2 - g1) / height
        b_ratio = (b2 - b1) / height
        
        for i in range(height):
            # Cleanly calculate 8-bit colors outside of the f-string formatter
            nr = int(r1 + (r_ratio * i)) >> 8
            ng = int(g1 + (g_ratio * i)) >> 8
            nb = int(b1 + (b_ratio * i)) >> 8
            
            # Clamp values to strictly 0-255 to prevent hex crashes
            nr = max(0, min(255, nr))
            ng = max(0, min(255, ng))
            nb = max(0, min(255, nb))
            
            self.create_line(0, i, width, i, tags=("gradient",), fill=f"#{nr:02x}{ng:02x}{nb:02x}")
        self.lower("gradient")

class NotificationToast(ctk.CTkFrame):
    def __init__(self, parent, title, message, color="#3b82f6"):
        super().__init__(parent, fg_color="#1e293b", border_width=2, border_color=color, corner_radius=8)
        self.parent = parent
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 14, "bold"), text_color=color).pack(anchor="w", padx=15, pady=(10, 0))
        ctk.CTkLabel(self, text=message, font=("Segoe UI", 12), justify="left", wraplength=250).pack(anchor="w", padx=15, pady=(0, 10))
        self.place(relx=0.5, rely=-0.2, anchor="n")
        self.animate_in(0)
        
    def animate_in(self, step):
        if step < 20:
            self.place(relx=0.5, rely=-0.2 + (step * 0.012), anchor="n")
            self.after(15, lambda: self.animate_in(step + 1))
        else: self.after(4000, self.animate_out, 0)
            
    def animate_out(self, step):
        if step < 20:
            self.place(relx=0.5, rely=0.04 - (step * 0.012), anchor="n")
            self.after(15, lambda: self.animate_out(step + 1))
        else: self.destroy()

class LoginGateway(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Nexus Gateway")
        self.geometry("600x400")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", sys.exit)
        
        self.bg = GradientFrame(self, "#020617", "#1e3a8a", highlightthickness=0)
        self.bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        box = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=15, width=400, height=250)
        box.place(relx=0.5, rely=0.5, anchor="center")
        box.pack_propagate(False)
        
        ctk.CTkLabel(box, text="ENTERPRISE NEXUS", font=("Segoe UI", 24, "bold")).pack(pady=(30, 20))
        self.user = ctk.CTkEntry(box, width=300, height=45, placeholder_text="Enter Username...")
        self.user.pack(pady=10)
        if master.username: self.user.insert(0, master.username)
        
        self.btn = ctk.CTkButton(box, text="Connect", font=("Segoe UI", 14, "bold"), fg_color="#3b82f6", height=45, width=300, command=self.connect)
        self.btn.pack(pady=(20, 0))
        self.master_app = master
        
    def connect(self):
        usr = self.user.get().strip()
        if not usr: return
        self.btn.configure(text="Authenticating...", state="disabled")
        self.update() 
        
        def _attempt_connection():
            try:
                requests.post(f"{self.master_app.api_base}/register/{usr}", timeout=5)
                self.master_app.username = usr
                self.master_app.save_settings()
                self.master_app.start_network_poller()
                self.after(0, self.destroy)
            except Exception:
                self.after(0, lambda: messagebox.showwarning("Connection Pending", "The Nexus Server is still starting up. Please wait 5 seconds and click Connect again."))
                self.after(0, lambda: self.btn.configure(text="Connect", state="normal"))

        threading.Thread(target=_attempt_connection, daemon=True).start()

class SourceAgentClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Nexus V33.3 Auto")
        self.geometry("1250x800")
        ctk.set_appearance_mode("Dark")
        
        self.api_key = ""
        self.ai_model = "google/gemini-1.5-flash:free"
        self.persona = "Policy Strict"
        self.username = ""
        self.api_base = "http://127.0.0.1:8050"
        self.last_msg_id = time.time()
        self.server_process = None
        
        self.load_settings()
        self.autonomous_server_boot()
        self.setup_ui()
        
        self.withdraw()
        self.wait_window(LoginGateway(self))
        self.deiconify()

    def autonomous_server_boot(self):
        try:
            requests.get(f"{self.api_base}/ping", timeout=2)
        except:
            if os.name == 'nt':
                self.server_process = subprocess.Popen(
                    [sys.executable, SERVER_FILE], 
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                self.server_process = subprocess.Popen([sys.executable, SERVER_FILE])

    def start_network_poller(self):
        threading.Thread(target=self.poll_messages, daemon=True).start()

    def poll_messages(self):
        while True:
            time.sleep(2)
            try:
                res = requests.get(f"{self.api_base}/poll_messages/{self.username}/{self.last_msg_id}", timeout=2)
                if res.status_code == 200:
                    for m in res.json().get("messages", []):
                        self.last_msg_id = max(self.last_msg_id, m['id'])
                        if m['sender'] != self.username:
                            title = f"📢 Broadcast from {m['sender']}" if m['target'] == 'all' else f"✉️ Private from {m['sender']}"
                            color = "#f59e0b" if m['target'] == 'all' else "#10b981"
                            self.after(0, lambda t=title, c=color, msg=m['msg']: NotificationToast(self, t, msg, c))
            except: pass

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        s = ctk.CTkFrame(self, width=280, corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 20))
        
        ctk.CTkLabel(s, text="AI Engine:", font=("Segoe UI", 12)).pack(anchor="w", padx=20)
        self.model_menu = ctk.CTkOptionMenu(s, values=["google/gemini-1.5-flash:free", "meta-llama/llama-3.3-70b-instruct:free", "anthropic/claude-3-haiku"], command=self.save_settings)
        self.model_menu.set(self.ai_model); self.model_menu.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(s, text="Active Persona:", font=("Segoe UI", 12)).pack(anchor="w", padx=20)
        self.persona_menu = ctk.CTkOptionMenu(s, values=["Policy Strict", "Creative Brainstorm", "Code Reviewer"], command=self.save_settings)
        self.persona_menu.set(self.persona); self.persona_menu.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkButton(s, text="📂 Ingest Policies", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(s, text="⚙️ Credentials", font=("Segoe UI", 13), fg_color="#475569", command=self.open_settings).pack(fill="x", padx=20, pady=5)
        
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main
