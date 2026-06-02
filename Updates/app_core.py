import os, threading, shutil, json, queue
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
        
        # Settings State
        self.ai_model = "google/gemini-1.5-flash:free"
        
        # UI & AI
        self.setup_ui()
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.load_db()

    def setup_ui(self):
        s = ctk.CTkFrame(self, width=200); s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkButton(s, text="New Session", command=self.clear_chat).pack(pady=10)
        
        self.chat = ctk.CTkTextbox(self, fg_color="#0f172a"); self.chat.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.chat.configure(state="disabled")
        
        self.entry = ctk.CTkEntry(self); self.entry.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        self.entry.bind("<Return>", lambda e: self.send())

    def send(self):
        q = self.entry.get()
        self.entry.delete(0, "end")
        threading.Thread(target=self.ai_generate, args=(q, self.chat), daemon=True).start()

    def ai_generate(self, q, target):
        target.configure(state="normal")
        target.insert("end", f"\nUSER: {q}\nADVISOR: ")
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model=self.ai_model)
            resp = llm.invoke([SystemMessage(content="You are Policy Advisor. Provide precise, documented answers."), HumanMessage(content=q)]).content
            target.insert("end", f"{resp}\n---\n")
        except Exception as e: target.insert("end", f"Error: {e}\n")
        target.configure(state="disabled")

    def add_docs(self): pass # Implement file selection logic as before
    def load_db(self): pass

if __name__ == "__main__":
    app = PolicyAdvisorMaster()
    app.mainloop()
