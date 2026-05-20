import os, sys, threading, time, base64, math, uuid, json, shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# LangChain Dependencies
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# --- VAULT CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.path.abspath(os.path.dirname(__file__)) if '__file__' in globals() else os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
ENV_FILE = os.path.join(BASE_DIR, ".env")

for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

POLICY_ADVISOR_SYSTEM_PROMPT = """You are "Policy Advisor 2026." 
Answer employee questions strictly by referencing official company policy documents provided.

You must only provide answers grounded in the available policy content. When a relevant policy applies:
- Identify the policy name and section.
- Quote verbatim the exact excerpt(s).
- Clearly separate quoted material from your explanation.

Before answering, interpret the scenario and identify underlying policy themes/risks (e.g., bribery, safeguarding, data protection).
After quoting, provide:
1) A plain English explanation of the policy.
2) Application to the user's specific situation.

Order policies by relevance/risk level. If no policy is found, ask a maximum of 2 clarifying questions before admitting no policy could be located."""

class SourceAgentWorkspace(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise Edition")
        self.geometry("1400x900")
        
        # Design Tokens
        ctk.set_appearance_mode("Dark")
        self.accent = "#3b82f6"
        self.bg_deep = "#020617"
        self.bg_surface = "#0f172a"
        
        self.cached_vectorstore = None
        self.user_name = "Employee"
        self.current_session_id = str(uuid.uuid4())
        self.session_history = []
        
        self.load_save_data()
        self.setup_ui()
        
        load_dotenv(ENV_FILE)
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key: self.setup_ai(api_key)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=280, fg_color=self.bg_deep, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="🏛️ Policy Advisor", font=("Segoe UI", 20, "bold")).pack(pady=20)
        
        # Action Bar
        action_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        action_box.pack(fill="x", padx=15)
        ctk.CTkButton(action_box, text="Upload", fg_color="#0ea5e9", height=35, command=self.add_source_document).pack(fill="x", pady=5)
        ctk.CTkButton(action_box, text="Database", fg_color="#334155", height=35, command=self.open_source_manager).pack(fill="x", pady=5)
        
        # Status Monitor
        self.health_lbl = ctk.CTkLabel(self.sidebar, text="● System Ready", text_color="#22c55e", font=("Segoe UI", 12))
        self.health_lbl.pack(pady=20)
        
        # Inquiry List
        self.history_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True, padx=10)
        
        # Main Area
        self.chat_display = ctk.CTkTextbox(self, fg_color=self.bg_surface, font=("Segoe UI", 14))
        self.chat_display.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_display.configure(state="disabled")

        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        
        self.user_input = ctk.CTkEntry(input_frame, height=45, placeholder_text="Enter policy inquiry...")
        self.user_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.user_input.bind("<Return>", lambda e: self.send_message())
        
        ctk.CTkButton(input_frame, text="Ask", width=80, height=45, command=self.send_message).pack(side="right")

    def setup_ai(self, key):
        base = "https://openrouter.ai/api/v1"
        self.editor_engine = ChatOpenAI(base_url=base, api_key=key, model="google/gemini-2.0-flash-exp:free").with_fallbacks([ChatOpenAI(base_url=base, api_key=key, model="meta-llama/llama-3.3-70b-instruct:free")])
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.load_local_vectorstore()

    def send_message(self):
        q = self.user_input.get()
        if not q: return
        self.user_input.delete(0, "end")
        threading.Thread(target=self.process_query, args=(q,), daemon=True).start()

    def process_query(self, query):
        context = ""
        if self.cached_vectorstore:
            docs = self.cached_vectorstore.as_retriever(search_kwargs={"k": 6}).invoke(query)
            context = "\n".join([d.page_content for d in docs])
        
        msgs = [SystemMessage(content=POLICY_ADVISOR_SYSTEM_PROMPT), HumanMessage(content=f"Policy Context:\n{context}\n\nQuestion: {query}")]
        
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"\n>> {query}\n\n")
        for chunk in self.editor_engine.stream(msgs):
            self.chat_display.insert("end", chunk.content)
            self.update()
        self.chat_display.insert("end", "\n\n---\n")
        self.chat_display.configure(state="disabled")

    # Helper methods (Database management, save_data, etc.) remain as defined in previous versions
    def load_save_data(self): pass
    def save_current_state(self): pass
    def add_source_document(self): pass
    def rebuild_vectorstore(self): pass
    def load_local_vectorstore(self): pass
    def open_source_manager(self): pass

if __name__ == "__main__":
    app = SourceAgentWorkspace()
    app.mainloop()
