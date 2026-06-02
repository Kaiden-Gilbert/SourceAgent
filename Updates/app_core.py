import os, threading, shutil, json
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
ENV_FILE = os.path.join(BASE_DIR, ".env")
os.makedirs(SOURCE_DIR, exist_ok=True)

class PolicyAdvisorMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise")
        self.geometry("1200x800")
        
        self.ai_model = "google/gemini-1.5-flash:free"
        
        self.setup_ui()
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        s = ctk.CTkFrame(self, width=200)
        s.grid(row=0, column=0, sticky="nsew")
        
        # UI Buttons
        ctk.CTkButton(s, text="New Session", command=self.clear_chat).pack(pady=10, padx=10)
        ctk.CTkButton(s, text="📂 Upload Docs", command=self.add_docs).pack(fill="x", padx=10, pady=5)
        
        self.chat = ctk.CTkTextbox(self, fg_color="#0f172a", font=("Segoe UI", 14))
        self.chat.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.chat.insert("1.0", "SYSTEM: Enterprise Module Online.\n\n")
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self, height=45, placeholder_text="Ask a compliance question...")
        self.entry.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        self.entry.bind("<Return>", lambda e: self.send())

    def clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.insert("1.0", "SYSTEM: Memory wiped. Ready for new inquiry.\n\n")
        self.chat.configure(state="disabled")

    def send(self):
        q = self.entry.get()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.ai_generate, args=(q, self.chat), daemon=True).start()

    def ai_generate(self, q, target):
        target.configure(state="normal")
        target.insert("end", f"\nUSER: {q}\n\nADVISOR: ")
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model)
            context = ""
            if self.db:
                docs = self.db.as_retriever(search_kwargs={"k": 4}).invoke(q)
                context = "\n".join([d.page_content for d in docs])
                
            prompt = "You are Policy Advisor. Provide precise, documented answers from the context. Quote verbatim. If missing, state it is not in the policy."
            resp = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]).content
            target.insert("end", f"{resp}\n\n---\n")
        except Exception as e: 
            target.insert("end", f"Error: {e}\n\n---\n")
        target.configure(state="disabled")

    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index):
            try:
                self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True)
            except:
                self.db = None

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDFs", "*.pdf")])
        if files:
            for f in files: shutil.copy(f, SOURCE_DIR)
            self.rebuild_db()

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            self.db = FAISS.from_documents(RecursiveCharacterTextSplitter(chunk_size=1000).split_documents(docs), self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

if __name__ == "__main__":
    app = PolicyAdvisorMaster()
    app.mainloop()
