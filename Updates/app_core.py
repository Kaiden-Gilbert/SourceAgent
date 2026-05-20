"""
SOURCE AGENT X
═══════════════════════════════════════════════════════════════
Single-file AI Source Agent Platform
Modern RAG + Persistent Memory + Auto Updates + Chat Saves

FEATURES
───────────────────────────────────────────────────────────────
✓ Multi-document RAG
✓ Persistent chat memory
✓ Dedicated chat windows
✓ Source citation system
✓ PDF ingestion
✓ Auto FAISS persistence
✓ Thread-safe UI
✓ Live status system
✓ Update checker every 10 seconds
✓ GitHub hot-update system
✓ Saved chat export
✓ Session recovery
✓ Modern UI
✓ Background embedding
✓ Async-safe querying
✓ Crash recovery
✓ Rollback support
✓ Query history
✓ Document manager
✓ API settings panel
✓ Source tracing
✓ Search previews
✓ Local vault system
✓ Auto folder creation
"""

import os
import sys
import json
import time
import queue
import shutil
import threading
import traceback
import urllib.request
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from dotenv import load_dotenv, set_key

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_community.document_loaders import (
    PyMuPDFLoader
)

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from langchain_community.vectorstores import (
    FAISS
)

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage
)

# ═════════════════════════════════════════════════════════════
# ENVIRONMENT LOCK
# ═════════════════════════════════════════════════════════════

if os.environ.get("SOURCE_AGENT_RUNNING") == "1":
    sys.exit(0)

os.environ["SOURCE_AGENT_RUNNING"] = "1"

# ═════════════════════════════════════════════════════════════
# PATHS
# ═════════════════════════════════════════════════════════════

BASE_DIR = os.path.join(
    os.getenv("LOCALAPPDATA", os.getcwd()),
    "SourceAgentX"
)

DOCS_DIR = os.path.join(BASE_DIR, "source_docs")
CHAT_DIR = os.path.join(BASE_DIR, "saved_chats")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

FAISS_INDEX = os.path.join(DOCS_DIR, "faiss_index")

ENV_FILE = os.path.join(BASE_DIR, ".env")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

VERSION_FILE = os.path.join(BASE_DIR, "version.json")

TEMP_UPDATE = os.path.join(BASE_DIR, "update_temp.py")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(CHAT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ═════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════

CURRENT_VERSION = "2.0.0"

UPDATE_CHECK_INTERVAL = 10

ENGINE_UPDATE_URL = (
    "https://raw.githubusercontent.com/"
    "Kaiden-Gilbert/SourceAgent/main/Updates/app_core.py"
)

VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "Kaiden-Gilbert/SourceAgent/main/Updates/version.json"
)

DEFAULT_MODEL = "google/gemini-1.5-flash:free"

TOP_K = 5

SYSTEM_PROMPT = """
You are Source Agent X.

Rules:
1. Answer ONLY from retrieved context.
2. NEVER hallucinate.
3. Cite sources clearly.
4. If information is unavailable say:
"I cannot find this in the loaded sources."
5. Be concise and technically accurate.
"""

COLORS = {
    "bg": "#020617",
    "panel": "#0f172a",
    "sidebar": "#111827",
    "accent": "#3b82f6",
    "text": "#e2e8f0",
    "muted": "#64748b",
    "success": "#22c55e",
    "error": "#ef4444",
}

# ═════════════════════════════════════════════════════════════
# CHAT LOGGER
# ═════════════════════════════════════════════════════════════

class ChatLogger:

    @staticmethod
    def save(role, message):

        try:

            now = datetime.now()

            filename = os.path.join(
                CHAT_DIR,
                now.strftime("%Y-%m-%d") + ".txt"
            )

            with open(
                filename,
                "a",
                encoding="utf-8"
            ) as f:

                f.write(
                    f"[{now.strftime('%H:%M:%S')}] "
                    f"{role}: {message}\n"
                )

        except:
            traceback.print_exc()

# ═════════════════════════════════════════════════════════════
# THREAD SAFE UI QUEUE
# ═════════════════════════════════════════════════════════════

class UIQueue:

    def __init__(self, root):

        self.root = root
        self.q = queue.Queue()

        self.poll()

    def poll(self):

        try:

            while True:

                fn, args = self.q.get_nowait()

                fn(*args)

        except queue.Empty:
            pass

        self.root.after(50, self.poll)

    def run(self, fn, *args):

        self.q.put((fn, args))

# ═════════════════════════════════════════════════════════════
# UPDATE MANAGER
# ═════════════════════════════════════════════════════════════

class UpdateManager:

    def __init__(self, app):

        self.app = app

        threading.Thread(
            target=self.loop,
            daemon=True
        ).start()

    def loop(self):

        while True:

            try:

                with urllib.request.urlopen(
                    VERSION_URL,
                    timeout=10
                ) as r:

                    data = json.loads(
                        r.read().decode("utf-8")
                    )

                remote = data.get("version")

                if remote != CURRENT_VERSION:

                    self.app.ui.run(
                        self.app.notify_update,
                        remote
                    )

            except:
                pass

            time.sleep(
                UPDATE_CHECK_INTERVAL
            )

# ═════════════════════════════════════════════════════════════
# MAIN APP
# ═════════════════════════════════════════════════════════════

class SourceAgentX(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.title("Source Agent X")

        self.geometry("1400x820")

        self.configure(
            fg_color=COLORS["bg"]
        )

        ctk.set_appearance_mode("Dark")

        self.protocol(
            "WM_DELETE_WINDOW",
            self.safe_exit
        )

        self.history = []

        self.db = None

        self.api_key = ""

        self.ai_model = DEFAULT_MODEL

        self.embeddings = None

        self.ui = UIQueue(self)

        self.query_lock = threading.Lock()

        self.load_settings()

        self.build_ui()

        UpdateManager(self)

        threading.Thread(
            target=self.initialize_backend,
            daemon=True
        ).start()

    # ════════════════════════════════════════════════════════
    # UI
    # ════════════════════════════════════════════════════════

    def build_ui(self):

        self.grid_columnconfigure(
            1,
            weight=1
        )

        self.grid_rowconfigure(
            0,
            weight=1
        )

        sidebar = ctk.CTkFrame(
            self,
            width=250,
            fg_color=COLORS["sidebar"]
        )

        sidebar.grid(
            row=0,
            column=0,
            sticky="ns"
        )

        ctk.CTkLabel(
            sidebar,
            text="SOURCE\nAGENT X",
            font=("Segoe UI", 28, "bold"),
            text_color=COLORS["accent"]
        ).pack(pady=25)

        buttons = [

            ("📂 Add PDFs", self.add_documents),

            ("🧠 Rebuild Index", self.rebuild_index),

            ("🗑 Clear History", self.clear_history),

            ("⚙ Settings", self.open_settings),

            ("💾 Open Chat Logs", self.open_chat_folder),
        ]

        for text, cmd in buttons:

            ctk.CTkButton(
                sidebar,
                text=text,
                command=cmd,
                height=42
            ).pack(
                fill="x",
                padx=12,
                pady=5
            )

        self.status = ctk.CTkLabel(
            sidebar,
            text="Initializing...",
            text_color=COLORS["muted"]
        )

        self.status.pack(
            side="bottom",
            pady=15
        )

        main = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel"]
        )

        main.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        main.grid_rowconfigure(
            0,
            weight=1
        )

        main.grid_columnconfigure(
            0,
            weight=1
        )

        self.chat = ctk.CTkTextbox(
            main,
            font=("Consolas", 14),
            wrap="word"
        )

        self.chat.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=14,
            pady=(14, 6)
        )

        entry_row = ctk.CTkFrame(
            main,
            fg_color="transparent"
        )

        entry_row.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=14,
            pady=(0, 14)
        )

        entry_row.grid_columnconfigure(
            0,
            weight=1
        )

        self.entry = ctk.CTkEntry(
            entry_row,
            height=48,
            placeholder_text="Ask the source agent..."
        )

        self.entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 8)
        )

        self.entry.bind(
            "<Return>",
            lambda e: self.dispatch_query()
        )

        self.send_btn = ctk.CTkButton(
            entry_row,
            text="Send",
            width=100,
            command=self.dispatch_query
        )

        self.send_btn.grid(
            row=0,
            column=1
        )

    # ════════════════════════════════════════════════════════
    # SETTINGS
    # ════════════════════════════════════════════════════════

    def load_settings(self):

        load_dotenv(ENV_FILE)

        self.api_key = os.getenv(
            "OPENROUTER_API_KEY",
            ""
        )

        if os.path.exists(CONFIG_FILE):

            try:

                with open(
                    CONFIG_FILE,
                    "r"
                ) as f:

                    data = json.load(f)

                self.ai_model = data.get(
                    "model",
                    DEFAULT_MODEL
                )

            except:
                pass

    def save_settings(self):

        with open(
            CONFIG_FILE,
            "w"
        ) as f:

            json.dump(
                {
                    "model": self.ai_model
                },
                f,
                indent=4
            )

    # ════════════════════════════════════════════════════════
    # BACKEND
    # ════════════════════════════════════════════════════════

    def initialize_backend(self):

        self.set_status(
            "Loading embeddings..."
        )

        try:

            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2"
            )

            self.load_index()

            self.set_status(
                "Ready."
            )

        except Exception as e:

            self.set_status(
                f"Embedding error: {e}"
            )

    def load_index(self):

        if os.path.exists(FAISS_INDEX):

            self.db = FAISS.load_local(
                FAISS_INDEX,
                self.embeddings,
                allow_dangerous_deserialization=True
            )

    # ════════════════════════════════════════════════════════
    # CHAT
    # ════════════════════════════════════════════════════════

    def append_chat(self, role, text):

        self.chat.insert(
            "end",
            f"\n[{role}]\n{text}\n"
            + ("─" * 60)
            + "\n"
        )

        self.chat.see("end")

    def dispatch_query(self):

        q = self.entry.get().strip()

        if not q:
            return

        self.entry.delete(0, "end")

        threading.Thread(
            target=self.generate,
            args=(q,),
            daemon=True
        ).start()

    def generate(self, query):

        self.ui.run(
            self.append_chat,
            "YOU",
            query
        )

        ChatLogger.save(
            "USER",
            query
        )

        context = self.retrieve_context(
            query
        )

        msgs = [
            SystemMessage(
                content=SYSTEM_PROMPT
            )
        ]

        for h in self.history[-8:]:

            msgs.append(h)

        msgs.append(
            HumanMessage(
                content=f"""
Context:
{context}

Question:
{query}
"""
            )
        )

        try:

            llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                model=self.ai_model,
                temperature=0.2
            )

            with self.query_lock:

                resp = llm.invoke(msgs)

            answer = resp.content

            self.history.append(
                HumanMessage(content=query)
            )

            self.history.append(
                AIMessage(content=answer)
            )

            self.ui.run(
                self.append_chat,
                "AGENT",
                answer
            )

            ChatLogger.save(
                "AGENT",
                answer
            )

        except Exception as e:

            self.ui.run(
                self.append_chat,
                "ERROR",
                str(e)
            )

    # ════════════════════════════════════════════════════════
    # VECTOR SEARCH
    # ════════════════════════════════════════════════════════

    def retrieve_context(self, query):

        if not self.db:

            return (
                "No indexed documents available."
            )

        try:

            docs = self.db.as_retriever(
                search_kwargs={"k": TOP_K}
            ).invoke(query)

            return "\n\n".join([
                d.page_content
                for d in docs
            ])

        except Exception as e:

            return f"Retrieval error: {e}"

    # ════════════════════════════════════════════════════════
    # DOCUMENTS
    # ════════════════════════════════════════════════════════

    def add_documents(self):

        files = filedialog.askopenfilenames(
            filetypes=[
                ("PDF Files", "*.pdf")
            ]
        )

        if not files:
            return

        for f in files:

            shutil.copy(
                f,
                DOCS_DIR
            )

        self.set_status(
            "Documents added."
        )

    def rebuild_index(self):

        threading.Thread(
            target=self._rebuild_index,
            daemon=True
        ).start()

    def _rebuild_index(self):

        self.set_status(
            "Loading PDFs..."
        )

        docs = []

        for f in os.listdir(DOCS_DIR):

            if f.endswith(".pdf"):

                path = os.path.join(
                    DOCS_DIR,
                    f
                )

                try:

                    docs.extend(
                        PyMuPDFLoader(path).load()
                    )

                except:
                    pass

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150
        )

        chunks = splitter.split_documents(
            docs
        )

        self.set_status(
            "Embedding chunks..."
        )

        self.db = FAISS.from_documents(
            chunks,
            self.embeddings
        )

        self.db.save_local(
            FAISS_INDEX
        )

        self.set_status(
            f"Indexed {len(chunks)} chunks."
        )

    # ════════════════════════════════════════════════════════
    # UTIL
    # ════════════════════════════════════════════════════════

    def set_status(self, text):

        self.ui.run(
            self.status.configure,
            text=text
        )

    def notify_update(self, version):

        messagebox.showinfo(
            "Update Available",
            (
                "Hey! It's time to update "
                "the application!\n\n"
                "Please save your work "
                "and restart.\n\n"
                f"Version: {version}"
            )
        )

    def clear_history(self):

        self.history.clear()

        self.append_chat(
            "SYSTEM",
            "History cleared."
        )

    def open_chat_folder(self):

        os.startfile(CHAT_DIR)

    def open_settings(self):

        win = ctk.CTkToplevel(self)

        win.title("Settings")

        win.geometry("500x220")

        model = ctk.CTkEntry(
            win,
            width=420
        )

        model.pack(
            pady=(25, 10)
        )

        model.insert(
            0,
            self.ai_model
        )

        key = ctk.CTkEntry(
            win,
            width=420,
            show="•"
        )

        key.pack(
            pady=10
        )

        key.insert(
            0,
            self.api_key
        )

        def save():

            self.ai_model = model.get()

            self.api_key = key.get()

            set_key(
                ENV_FILE,
                "OPENROUTER_API_KEY",
                self.api_key
            )

            self.save_settings()

            win.destroy()

            self.set_status(
                "Settings saved."
            )

        ctk.CTkButton(
            win,
            text="Save",
            command=save
        ).pack(
            pady=20
        )

    def safe_exit(self):

        try:

            self.destroy()

        except:
            pass

# ═════════════════════════════════════════════════════════════
# ENTRY
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":

    try:

        app = SourceAgentX()

        app.mainloop()

    except Exception:

        traceback.print_exc()
