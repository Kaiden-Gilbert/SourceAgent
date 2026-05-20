import os, threading, shutil, math, json, queue
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

# --- CONFIG ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")
os.makedirs(SOURCE_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are "Policy Advisor 2026." 
1. Answer strictly using provided policy docs.
2. Quote verbatim. 
3. Separate quotes from explanation.
4. NO hallucinations. If missing, say: "I cannot find a policy regarding this."
5. Tone: Clinical, professional, precise."""

class DedicatedChatWindow(ctk.CTkToplevel):
    def __init__(self, master, app_core):
        super().__init__(master)
        self.parent = app_core
        self.title("Session Terminal"); self.geometry("700x500")
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), fg_color="#020617")
        self.chat.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat.configure(state="disabled")
        self.entry = ctk.CTkEntry(self, height=40); self.entry.pack(fill="x", padx=10, pady=10)
        self.entry.bind("<Return>", lambda e: self.send())
    
    def send(self):
        q = self.entry.get()
        self.entry.delete(0, "end")
        threading.Thread(target=self.parent.ai_generate, args=(q, self.chat), daemon=True).start()

class PolicyAdvisorMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise")
        self.geometry("1100x700")
        ctk.set_appearance_mode("Dark")
        
        # Defaults
        self.ai_model = "google/gemini-1.5-flash:free"
        self.app_password = ""
        self.load_settings()
        
        self.setup_ui()
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()

    def setup_ui(self):
        s = ctk.CTkFrame(self, width=250, fg_color="#020617"); s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkButton(s, text="⧉ Chat", command=lambda: DedicatedChatWindow(self, self)).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(s, text="📂 Docs", command=self.add_docs).pack(fill="x", padx=10, pady=5)
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), fg_color="#0f172a")
        self.chat.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, height=45); self.entry.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 15))
        self.entry.bind("<Return>", lambda e: self.ai_generate(self.entry.get(), self.chat, True))

    def ai_generate(self, q, target, clear=False):
        if clear: self.entry.delete(0, "end")
        target.configure(state="normal")
        target.insert("end", f"\n>> {q}\n\nADVISOR: ")
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model)
            context = ""
            if self.db: context = "\n".join([d.page_content for d in self.db.as_retriever(search_kwargs={"k": 3}).invoke(q)])
            resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=f"Context:{context}\nInquiry:{q}")]).content
            target.insert("end", f"{resp}\n---\n")
        except Exception as e: target.insert("end", f"Error: {e}\n")
        target.configure(state="disabled")

    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True) if os.path.exists(index) else None

    def add_docs(self):
        files = filedialog.askopenfilenames()
        if not files: return
        for f in files: shutil.copy(f, SOURCE_DIR)
        self.rebuild_db()

    def rebuild_db(self):
        docs = [PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load()[0] for f in os.listdir(SOURCE_DIR) if f.endswith(".pdf")]
        if docs: self.db = FAISS.from_documents(RecursiveCharacterTextSplitter(chunk_size=1000).split_documents(docs), self.embeddings)

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "r") as f:
                d = json.load(f)
                self.app_password = d.get("app_password", "")

if __name__ == "__main__":
    app = PolicyAdvisorMaster()
    app.mainloop()
