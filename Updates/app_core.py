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

# --- NETWORK MEMORY ---
connected_users = set()
# Format: {{"id": float, "sender": str, "target": str, "msg": str}}
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
    # Keep queue manageable
    if len(message_queue) > 100: message_queue.pop(0)
    return {{"status": "sent"}}

@app.get("/poll_messages/{{username}}/{{last_id}}")
def poll_messages(username: str, last_id: float):
    # Retrieve messages targeted to 'all' or specifically to this username that are newer than last_id
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
    sys_prompt = personas.get(req.persona, personas["Policy Strict"])
    
    try:
        llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=req.api_key, model=req.model, temperature=0.1)
        docs = db.as_retriever(search_kwargs={{"k": 5}}).invoke(req.query)
        context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}}\\n{{d.page_content}}" for d in docs])
        sources = list(set([d.metadata.get('source') for d in docs]))
        
        final_resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
        return {{"answer": final_resp, "sources": sources}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Binding to 0.0.0.0 allows LAN access for true multi-client capability
    uvicorn.run(app, host="0.0.0.0", port=8050, log_level="critical")
""")

SERVER_FILE = os.path.join(SERVER_DIR, "backend_engine.py")
with open(SERVER_FILE, "w", encoding="utf-8") as f:
    f.write(BACKEND_CODE)

# ==========================================
# PART 2: THE NATIVE NEXUS CLIENT
# ==========================================
class GradientFrame(tk.Canvas):
    """Custom hardware-accelerated gradient renderer for Tkinter"""
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
            nr = int(r1 + (r_ratio * i))
            ng = int(g1 + (g_ratio * i))
            nb = int(b1 + (b_ratio * i))
            color = f"#{nr>>8:02x}{ng>>8:02x}{nb>>8:02x}"
            self.create_line(0, i, width, i, tags=("gradient",), fill=color)
        self.lower("gradient")

class NotificationToast(ctk.CTkFrame):
    """Sliding notification system"""
    def __init__(self, parent, title, message, color="#3b82f6"):
        super().__init__(parent, fg_color="#1e293b", border_width=2, border_color=color, corner_radius=8)
        self.parent = parent
        
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 14, "bold"), text_color=color).pack(anchor="w", padx=15, pady=(10, 0))
        ctk.CTkLabel(self, text=message, font=("Segoe UI", 12), justify="left", wraplength=250).pack(anchor="w", padx=15, pady=(0, 10))
        
        # Initial hidden position
        self.place(relx=0.5, rely=-0.2, anchor="n")
        self.animate_in(0)
        
    def animate_in(self, step):
        if step < 20:
            rely = -0.2 + (step * 0.012)
            self.place(relx=0.5, rely=rely, anchor="n")
            self.after(15, lambda: self.animate_in(step + 1))
        else:
            self.after(4000, self.animate_out, 0)
            
    def animate_out(self, step):
        if step < 20:
            rely = 0.04 - (step * 0.012)
            self.place(relx=0.5, rely=rely, anchor="n")
            self.after(15, lambda: self.animate_out(step + 1))
        else:
            self.destroy()

class LoginGateway(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Nexus Gateway")
        self.geometry("600x450")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", sys.exit)
        
        # Gradient Background
        self.bg = GradientFrame(self, "#020617", "#1e3a8a", highlightthickness=0)
        self.bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Login Box
        box = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=15, width=400, height=350)
        box.place(relx=0.5, rely=0.5, anchor="center")
        box.pack_propagate(False)
        
        ctk.CTkLabel(box, text="ENTERPRISE NEXUS", font=("Segoe UI", 24, "bold")).pack(pady=(30, 20))
        
        self.user = ctk.CTkEntry(box, width=300, height=45, placeholder_text="Username")
        self.user.pack(pady=10)
        if master.username: self.user.insert(0, master.username)
        
        self.ip = ctk.CTkEntry(box, width=300, height=45, placeholder_text="Server IP (e.g., 127.0.0.1)")
        self.ip.pack(pady=10)
        if master.server_ip: self.ip.insert(0, master.server_ip)
        
        ctk.CTkButton(box, text="Connect to Network", font=("Segoe UI", 14, "bold"), fg_color="#3b82f6", height=45, width=300, command=self.connect).pack(pady=(20, 0))
        self.master_app = master
        
    def connect(self):
        usr = self.user.get().strip()
        ip = self.ip.get().strip()
        if not usr or not ip: return
        
        try:
            res = requests.post(f"http://{ip}:8050/register/{usr}", timeout=3)
            if res.status_code == 200:
                self.master_app.username = usr
                self.master_app.server_ip = ip
                self.master_app.api_base = f"http://{ip}:8050"
                self.master_app.save_settings()
                self.master_app.start_network_poller()
                self.destroy()
        except Exception:
            messagebox.showerror("Connection Error", "Cannot reach the Nexus Server at that IP.")

class SourceAgentClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Nexus V32")
        self.geometry("1250x800")
        ctk.set_appearance_mode("Dark")
        
        # State
        self.api_key = ""
        self.ai_model = "google/gemini-1.5-flash:free"
        self.persona = "Policy Strict"
        self.username = ""
        self.server_ip = "127.0.0.1"
        self.api_base = "http://127.0.0.1:8050"
        self.last_msg_id = time.time()
        
        self.load_settings()
        self.setup_ui()
        
        # Launch local server blindly (if it fails because port is in use, it means it's already running!)
        self.server_process = subprocess.Popen([sys.executable, SERVER_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Force Login
        self.withdraw()
        gw = LoginGateway(self)
        self.wait_window(gw)
        self.deiconify()

    def start_network_poller(self):
        threading.Thread(target=self.poll_messages, daemon=True).start()

    def poll_messages(self):
        while True:
            time.sleep(2)
            try:
                res = requests.get(f"{self.api_base}/poll_messages/{self.username}/{self.last_msg_id}", timeout=2)
                if res.status_code == 200:
                    msgs = res.json().get("messages", [])
                    for m in msgs:
                        self.last_msg_id = max(self.last_msg_id, m['id'])
                        if m['sender'] != self.username:
                            title = f"📢 Global Broadcast from {m['sender']}" if m['target'] == 'all' else f"✉️ Private Message from {m['sender']}"
                            color = "#f59e0b" if m['target'] == 'all' else "#10b981"
                            self.after(0, lambda t=title, c=color, msg=m['msg']: NotificationToast(self, t, msg, c))
            except: pass

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        s = ctk.CTkFrame(self, width=280, corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 20))
        
        # Multi-AI Selectors
        ctk.CTkLabel(s, text="AI Engine:", font=("Segoe UI", 12)).pack(anchor="w", padx=20)
        self.model_menu = ctk.CTkOptionMenu(s, values=["google/gemini-1.5-flash:free", "meta-llama/llama-3.3-70b-instruct:free", "anthropic/claude-3-haiku"], command=self.update_ai)
        self.model_menu.set(self.ai_model); self.model_menu.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(s, text="Active Persona:", font=("Segoe UI", 12)).pack(anchor="w", padx=20)
        self.persona_menu = ctk.CTkOptionMenu(s, values=["Policy Strict", "Creative Brainstorm", "Code Reviewer"], command=self.update_ai)
        self.persona_menu.set(self.persona); self.persona_menu.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkButton(s, text="📂 Ingest Policies", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(s, text="⚙️ Credentials", font=("Segoe UI", 13), fg_color="#475569", command=self.open_settings).pack(fill="x", padx=20, pady=5)
        
        # Chat Area
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1); main_frame.grid_rowconfigure(0, weight=1)
        
        self.chat = ctk.CTkTextbox(main_frame, font=("Segoe UI", 15), spacing1=10, spacing3=10, corner_radius=10)
        self.chat.grid(row=0, column=0, sticky="nsew", pady=(0, 20))
        self.chat.insert("1.0", "SYSTEM: Network Established.\nCOMMANDS: Type '/announce [msg]' for global broadcast or '/msg [user] [msg]' for private comms.\n\n")
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(main_frame, height=55, placeholder_text="Ask the AI, or use /announce and /msg...", font=("Segoe UI", 15))
        self.entry.grid(row=1, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda e: self.process_input())

    def update_ai(self, _=None):
        self.ai_model = self.model_menu.get()
        self.persona = self.persona_menu.get()
        self.save_settings()

    def safe_insert(self, target, text):
        def _update():
            target.configure(state="normal")
            target.insert("end", text)
            target.see("end")
            target.configure(state="disabled")
        self.after(0, _update)

    def process_input(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        
        # Network Routing
        if q.startswith("/announce "):
            msg = q[10:]
            self.safe_insert(self.chat, f"\n[YOU BROADCAST]: {msg}\n")
            threading.Thread(target=lambda: requests.post(f"{self.api_base}/send_message/", json={"sender": self.username, "target": "all", "message": msg})).start()
            return
            
        if q.startswith("/msg "):
            parts = q.split(" ", 2)
            if len(parts) > 2:
                target_user = parts[1]
                msg = parts[2]
                self.safe_insert(self.chat, f"\n[YOU to {target_user}]: {msg}\n")
                threading.Thread(target=lambda: requests.post(f"{self.api_base}/send_message/", json={"sender": self.username, "target": target_user, "message": msg})).start()
            return

        # AI Routing
        threading.Thread(target=self.query_backend, args=(q,), daemon=True).start()

    def query_backend(self, q):
        self.safe_insert(self.chat, f"\nUSER: {q}\nAGENT: Thinking...\n")
        
        if not self.api_key:
            self.safe_insert(self.chat, "CRITICAL: OpenRouter API key missing. Configure in settings.\n---\n")
            return

        try:
            res = requests.post(f"{self.api_base}/agentic_query/", json={"query": q, "api_key": self.api_key, "model": self.ai_model, "persona": self.persona})
            if res.status_code == 200:
                data = res.json()
                sources = ", ".join(data.get("sources", [])) if data.get("sources") else "None"
                self.safe_insert(self.chat, f"\n{data.get('answer')}\n\n[Sources: {sources}]\n---\n")
            else:
                self.safe_insert(self.chat, f"Server Error: {res.json().get('detail')}\n---\n")
        except requests.exceptions.ConnectionError:
            self.safe_insert(self.chat, "CRITICAL: Nexus Backend is unreachable.\n---\n")

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Documents", "*.pdf")])
        if files:
            threading.Thread(target=self.upload_to_backend, args=(files,), daemon=True).start()
            messagebox.showinfo("Processing", "Transmitting to Nexus indexer...")

    def upload_to_backend(self, files):
        for file_path in files:
            try:
                with open(file_path, "rb") as f:
                    requests.post(f"{self.api_base}/ingest/", files={"file": (os.path.basename(file_path), f, "application/pdf")})
            except Exception as e: print(f"Ingest error: {e}")

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.api_key = d.get("api_key", "")
                    self.username = d.get("username", "")
                    self.server_ip = d.get("server_ip", "127.0.0.1")
                    self.ai_model = d.get("ai_model", "google/gemini-1.5-flash:free")
                    self.persona = d.get("persona", "Policy Strict")
            except: pass

    def save_settings(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({"api_key": self.api_key, "username": self.username, "server_ip": self.server_ip, "ai_model": self.ai_model, "persona": self.persona}, f)

    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Security & API")
        win.geometry("400x200")
        win.attributes("-topmost", True)
        
        ctk.CTkLabel(win, text="OpenRouter API Key:").pack(pady=(20, 5))
        api_entry = ctk.CTkEntry(win, width=350, show="*"); api_entry.insert(0, self.api_key); api_entry.pack()

        def apply_changes():
            self.api_key = api_entry.get().strip()
            self.save_settings()
            win.destroy()
            
        ctk.CTkButton(win, text="Apply Configuration", command=apply_changes).pack(pady=20)

    def destroy(self):
        if hasattr(self, 'server_process'): self.server_process.terminate()
        super().destroy()

if __name__ == "__main__":
    app = SourceAgentClient()
    app.mainloop()
