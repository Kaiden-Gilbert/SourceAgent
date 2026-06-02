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
            nr, ng, nb = int(r1 + (r_ratio * i)), int(g1 + (g_ratio * i)), int(b1 + (b_ratio * i))
            self.create_line(0, i, width, i, tags=("gradient",), fill=f"#{nr>>8:02x}{ng>>
