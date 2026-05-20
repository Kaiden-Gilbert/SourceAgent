import os, threading, time, base64, uuid, json, shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# LangChain Imports
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# --- PATHS ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
ENV_FILE = os.path.join(BASE_DIR, ".env")
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- HARDCODED SYSTEM INSTRUCTIONS ---
POLICY_ADVISOR_SYSTEM_PROMPT = """You are an internal company policy knowledge repository named "Policy Advisor 2026." 
Your primary goal is to answer employee questions about workplace situations strictly by referencing official company policy documents provided to you in the context.

You must only provide answers that are grounded in the available policy content. When a relevant policy applies, you must:
- Identify the exact policy name
- Identify the specific section within that policy
- Quote verbatim the exact excerpt from the policy that supports the answer
- Clearly separate quoted material from any explanation

Before identifying relevant policies, interpret the scenario and identify all underlying policy themes and risks (e.g., bribery, conflict of interest, safeguarding, data protection). Expand the scenario into these themes and search for related policies. Do not rely solely on direct keyword matches.

After presenting all relevant quoted excerpts, provide:
1) A plain English explanation of what the policy means (based strictly on quoted text).
2) If a specific situation is described, a plain English application of the policy to that scenario.

Consider the user’s role. Only ask for the user’s role if policy applicability depends on it. Evaluate ALL available policies for every query. Do not stop at the first match.

When multiple policies apply:
- Include all relevant policies.
- Prioritise policies related to legal, regulatory, or compliance risks over general guidance.
- Order output by relevance and risk level.
- Prioritise Bribery, Anti-Corruption, or Gifts & Hospitality policies for related queries.
- Avoid treating high-risk scenarios as routine.

If no relevant policy is found, ask a maximum of 2 clarifying follow-up questions before stating that no applicable policy could be located.

DO NOT invent, infer, or generalize beyond the written text. DO NOT provide personal opinions or external knowledge.

Response Structure:
- Policy Reference(s): [Policy name + section]
- Verbatim Quote(s): [Exact excerpt(s)]
- Plain English Explanation: [Synthesised explanation]
- Application to Scenario: [If applicable]

Tone: Professional, plain, and readable. Never fabricate language or citations."""

class PolicyAdvisorEngine(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise")
        self.geometry("1100x700")
        ctk.set_appearance_mode("Dark")
        
        # UI Setup
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="🏛️ Advisor Engine", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkButton(self.sidebar, text="Upload Documents", command=self.add_docs).pack(pady=5, padx=10)
        
        self.chat = ctk.CTkTextbox(self, font=("Arial", 14))
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat.insert("1.0", "System: Engine Ready. Awaiting inquiry...\n")
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, placeholder_text="Enter policy inquiry...")
        self.entry.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.entry.bind("<Return>", lambda e: self.send())
        
        # AI Init
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.load_db()
        load_dotenv(ENV_FILE)
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key:
            self.llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, model="google/gemini-2.0-flash-exp:free")

    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True) if os.path.exists(index) else None

    def add_docs(self):
        files = filedialog.askopenfilenames()
        if not files: return
        for f in files: shutil.copy(f, SOURCE_DIR)
        self.rebuild_db()
        messagebox.showinfo("Success", "Database updated.")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            self.db = FAISS.from_documents(splitter.split_documents(docs), self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

    def send(self):
        q = self.entry.get()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.query_ai, args=(q,), daemon=True).start()

    def query_ai(self, q):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\nUSER: {q}\n\n")
        
        context = ""
        if self.db:
            docs = self.db.as_retriever(search_kwargs={"k": 4}).invoke(q)
            context = "\n".join([d.page_content for d in docs])
        
        msgs = [SystemMessage(content=POLICY_ADVISOR_SYSTEM_PROMPT), 
                HumanMessage(content=f"Context:\n{context}\n\nScenario: {q}")]
        
        response = self.llm.invoke(msgs).content
        self.chat.insert("end", f"ADVISOR: {response}\n\n---\n")
        self.chat.configure(state="disabled")

if __name__ == "__main__":
    app = PolicyAdvisorEngine()
    app.mainloop()
