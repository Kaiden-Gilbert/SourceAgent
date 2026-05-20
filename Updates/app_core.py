import os, threading, time, shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# --- VAULT CONFIG ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
ENV_FILE = os.path.join(BASE_DIR, ".env")
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- HARDCODED SYSTEM INSTRUCTIONS ---
POLICY_ADVISOR_SYSTEM_PROMPT = """You are "Policy Advisor 2026." 
Answer employee questions strictly by referencing official company policy documents provided to you in the context.

When a relevant policy applies:
- Identify the exact policy name and section.
- Quote verbatim the exact excerpt from the policy.
- Clearly separate quoted material from your explanation.

Before answering, interpret the scenario and identify all underlying policy themes (e.g., bribery, safeguarding, data protection).

After presenting quoted excerpts, provide:
1) A plain English explanation of what the policy means.
2) If a situation is described, a plain English application of the policy to that situation.

Prioritise legal/regulatory risks and order output by relevance/risk level.
If no relevant policy is found, ask a maximum of 2 clarifying follow-up questions before stating none was found.

DO NOT invent, infer, or generalize. NO personal opinions or external knowledge.

Tone: Professional, plain, and readable. Never fabricate language or citations."""

class PolicyAdvisorV13(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise Edition")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        # Color Palette
        self.bg_deep = "#020617"
        self.bg_surface = "#0f172a"
        self.accent = "#3b82f6"
        
        self.setup_ui()
        load_dotenv(ENV_FILE)
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key: self.setup_ai(api_key)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        sidebar = ctk.CTkFrame(self, width=280, fg_color=self.bg_deep, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(sidebar, text="🏛️ Policy Advisor", font=("Segoe UI", 20, "bold")).pack(pady=30)
        
        # Control Panel
        ctk.CTkLabel(sidebar, text="DATABASE TOOLS", font=("Segoe UI", 10, "bold"), text_color="#64748b").pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkButton(sidebar, text="Upload Documents", command=self.add_docs, fg_color="#0ea5e9").pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(sidebar, text="Database Manager", command=self.open_manager, fg_color="#334155").pack(fill="x", padx=20, pady=5)
        
        # Action Panel
        ctk.CTkLabel(sidebar, text="SESSION ACTIONS", font=("Segoe UI", 10, "bold"), text_color="#64748b").pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkButton(sidebar, text="Clear Chat", fg_color="#ef4444", command=self.clear_chat).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(sidebar, text="Export Response", fg_color="#64748b", command=self.export_chat).pack(fill="x", padx=20, pady=5)

        # Main Chat
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 14), fg_color=self.bg_surface)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat.insert("1.0", "System: Policy Advisor 2026 Online.\n\n")
        self.chat.configure(state="disabled")
        
        # Input
        self.entry = ctk.CTkEntry(self, height=50, placeholder_text="Ask a compliance or policy question...")
        self.entry.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.entry.bind("<Return>", lambda e: self.send())
        
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.load_db()

    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True) if os.path.exists(index) else None

    def add_docs(self):
        files = filedialog.askopenfilenames()
        if not files: return
        for f in files: shutil.copy(f, SOURCE_DIR)
        self.rebuild_db()
        messagebox.showinfo("Done", "Policies indexed successfully.")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            self.db = FAISS.from_documents(splitter.split_documents(docs), self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

    def clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def export_chat(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            with open(path, "w") as f: f.write(self.chat.get("1.0", "end"))

    def open_manager(self):
        messagebox.showinfo("DB Info", f"Policies Loaded: {len(os.listdir(SOURCE_DIR))}")

    def send(self):
        q = self.entry.get()
        if not q: return
        self.entry.delete(0, "end")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n>> {q}\n\n")
        self.chat.configure(state="disabled")
        threading.Thread(target=self.query_ai, args=(q,), daemon=True).start()

    def query_ai(self, q):
        self.chat.configure(state="normal")
        self.chat.insert("end", "Advisor is auditing...")
        
        context = ""
        if self.db:
            docs = self.db.as_retriever(search_kwargs={"k": 4}).invoke(q)
            context = "\n".join([d.page_content for d in docs])
        
        msgs = [SystemMessage(content=POLICY_ADVISOR_SYSTEM_PROMPT), 
                HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]
        
        response = self.llm.invoke(msgs).content
        self.chat.delete("end-2l", "end") # Remove "Auditing..."
        self.chat.insert("end", f"{response}\n\n---\n")
        self.chat.configure(state="disabled")

    def setup_ai(self, key):
        base = "https://openrouter.ai/api/v1"
        self.llm = ChatOpenAI(base_url=base, api_key=key, model="google/gemini-2.0-flash-exp:free").with_fallbacks([ChatOpenAI(base_url=base, api_key=key, model="meta-llama/llama-3.3-70b-instruct:free")])

if __name__ == "__main__":
    app = PolicyAdvisorV13()
    app.mainloop()
