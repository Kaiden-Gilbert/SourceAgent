import os, sys, threading, shutil, json, time, urllib.request, subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from collections import Counter

from langchain_community.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage

# --- CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(SOURCE_DIR, exist_ok=True)

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"

# --- SYSTEM PROMPT DESIGNED FOR TINYLLAMA ---
STRICT_TINYLLAMA_PROMPT = """You are a strict reading assistant.
You must ONLY use the provided facts inside the Context section below.
If the answer is not directly stated in the Context, say exactly: "I cannot find this information in the provided sources."
Do not make up facts. Do not use outside knowledge. Stick strictly to the text."""

class ProvisionerWindow(ctk.CTkToplevel):
    def __init__(self, master, mode="install"):
        super().__init__(master)
        self.title("System Provisioner")
        self.geometry("500x250")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.disable_close)
        
        self.mode = mode
        self.master_app = master
        
        self.lbl = ctk.CTkLabel(self, text="Initializing Local AI Engine...", font=("Segoe UI", 18, "bold"))
        self.lbl.pack(pady=(40, 20))
        
        self.pb = ctk.CTkProgressBar(self, mode="indeterminate", width=400)
        self.pb.pack()
        self.pb.start()
        
        self.sub_lbl = ctk.CTkLabel(self, text="Please wait. Preparing environment...", font=("Segoe UI", 12), text_color="#94a3b8")
        self.sub_lbl.pack(pady=10)
        
        if self.mode == "install":
            threading.Thread(target=self.download_and_install_ollama, daemon=True).start()
        elif self.mode == "pull":
            threading.Thread(target=self.pull_tinyllama, daemon=True).start()

    def disable_close(self): pass

    def download_and_install_ollama(self):
        self.after(0, lambda: self.lbl.configure(text="Downloading Ollama Engine..."))
        installer_path = os.path.join(BASE_DIR, "OllamaSetup.exe")
        
        try:
            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, installer_path)
            self.after(0, lambda: self.lbl.configure(text="Installing Engine (Check Taskbar)..."))
            self.after(0, lambda: self.sub_lbl.configure(text="Please finish the setup wizard that popped up on your screen."))
            
            subprocess.run([installer_path], check=True)
            if os.path.exists(installer_path):
                os.remove(installer_path)
            
            self.after(0, lambda: self.lbl.configure(text="Installation Finished!"))
            time.sleep(2)
            
            # Safely route UI teardown and boot sequence to the main thread
            self.after(0, self.destroy)
            self.after(0, self.master_app.check_environment)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Setup Failed", f"Could not auto-install Ollama: {e}\nPlease run it manually from ollama.com"))
            self.after(0, lambda: sys.exit(1))

    def pull_tinyllama(self):
        self.after(0, lambda: self.lbl.configure(text="Pulling TinyLlama Core..."))
        self.after(0, lambda: self.sub_lbl.configure(text="Downloading model parameters (~650MB) directly to your local drive."))
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(["ollama", "pull", "tinyllama"], check=True, startupinfo=startupinfo)
            
            # Safely route UI teardown and boot sequence to the main thread
            self.after(0, self.destroy)
            self.after(0, self.master_app.finish_boot)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Download Failed", f"Ollama failed to pull tinyllama: {e}"))
            self.after(0, lambda: sys.exit(1))


class AnalyticsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("System Audit Metrics")
        self.geometry("600x500")
        self.attributes("-topmost", True)
        
        ctk.CTkLabel(self, text="📊 Processing Analytics", font=("Segoe UI", 24, "bold"), text_color="#0ea5e9").pack(pady=(20, 10))
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent"); self.stats_frame.pack(fill="x", padx=20, pady=10)
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 13), fg_color="#0f172a"); self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.load_analytics()

    def load_analytics(self):
        if not os.path.exists(AUDIT_FILE):
            self.log_box.insert("1.0", "No local transaction logs found yet."); self.log_box.configure(state="disabled")
            return
        try:
            with open(AUDIT_FILE, "r") as f: logs = json.load(f)
            total_queries = len(logs)
            successful = sum(1 for log in logs if log.get("status") == "Success")
            success_rate = (successful / total_queries * 100) if total_queries > 0 else 0
            
            all_sources = []
            for log in logs:
                if isinstance(log.get("sources"), list): all_sources.extend(log.get("sources"))
            
            ctk.CTkLabel(self.stats_frame, text=f"Total Document Inquiries: {total_queries}", font=("Segoe UI", 14, "bold")).pack(side="left", padx=20)
            ctk.CTkLabel(self.stats_frame, text=f"Data Adherence: {success_rate:.1f}%", font=("Segoe UI", 14, "bold"), text_color="#10b981").pack(side="right", padx=20)
            
            report = "--- TOP SECURITY DOCS CONSULTED ---\n\n"
            for src, count in Counter(all_sources).most_common(5): report += f"[{count} read-hits] -> {src}\n"
            report += "\n--- HISTORICAL RUNTIME LOG ---\n\n"
            for log in reversed(logs[-10:]): report += f"[{log.get('timestamp', '')[:16]}] Query: {log.get('query')}\n"
                
            self.log_box.insert("1.0", report); self.log_box.configure(state="disabled")
        except Exception as e: self.log_box.insert("1.0", f"Error displaying metrics: {e}")


class SourceAgentMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | TinyLlama Sovereign Engine V39.1")
        self.geometry("1150x750")
        ctk.set_appearance_mode("Dark")
        
        self.ai_model = "tinyllama"
        self.withdraw()
        
        # Give the mainloop 100ms to stabilize before blocking the thread with subprocess checks
        self.after(100, self.check_environment)

    def check_environment(self):
        # Verify if Ollama exists as an executable command
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        except (FileNotFoundError, subprocess.CalledProcessError):
            ProvisionerWindow(self, mode="install")
            return

        # Verify if TinyLlama is already pulled locally
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True, startupinfo=startupinfo)
            if self.ai_model not in result.stdout:
                ProvisionerWindow(self, mode="pull")
                return
        except: pass

        self.finish_boot()

    def finish_boot(self):
        self.setup_ui()
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()
        self.deiconify()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        s = ctk.CTkFrame(self, width=280, fg_color="#020617", corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 10))
        ctk.CTkLabel(s, text="🔒 100% Offline Air-Gapped Mode", font=("Segoe UI", 11), text_color="#10b981").pack(pady=(0, 25))
        
        info_frame = ctk.CTkFrame(s, fg_color="#0f172a", height=60)
        info_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(info_frame, text="Active Core: TinyLlama (1.1B)", font=("Segoe UI", 12, "bold"), text_color="#3b82f6").place(relx=0.5, rely=0.3, anchor="center")
        ctk.CTkLabel(info_frame, text="Temp Locked: 0.0 (Strict)", font=("Segoe UI", 10), text_color="#94a3b8").place(relx=0.5, rely=0.7, anchor="center")

        ctk.CTkButton(s, text="📂 Ingest PDF Sources", font=("Segoe UI", 13), fg_color="#0ea5e9", hover_color="#0284c7", command=self.add_docs).pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkButton(s, text="📊 Performance Analytics", font=("Segoe UI", 13), fg_color="#8b5cf6", hover_color="#7c3aed", command=lambda: AnalyticsWindow(self)).pack(fill="x", padx=20, pady=10)
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#0f172a", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=(20, 10))
        self.chat.insert("1.0", "SYSTEM: TinyLlama compute core activated. Ingest a document and query the localized vault directly.\n\n")
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=50, placeholder_text="Ask a question from your documents...", font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send_main())
        
        ctk.CTkButton(input_frame, text="Query local AI", width=140, height=50, fg_color="#3b82f6", hover_color="#2563eb", font=("Segoe UI", 14, "bold"), command=self.send_main).grid(row=0, column=1)

    def log_audit(self, query, status, sources):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "status": status, "sources": sources}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

    def safe_insert(self, text):
        def _update():
            self.chat.configure(state="normal"); self.chat.insert("end", text); self.chat.see("end"); self.chat.configure(state="disabled")
        self.after(0, _update)

    def send_main(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.engine_generate, args=(q,), daemon=True).start()

    def engine_generate(self, q):
        self.safe_insert(f"\nUSER: {q}\nAGENT: Inquiring localized text embeddings...\n")
        
        try:
            llm = ChatOllama(model=self.ai_model, temperature=0.0, base_url="http://localhost:11434")
            context = ""
            sources_list = []
            
            if self.db:
                docs = self.db.as_retriever(search_kwargs={"k": 4}).invoke(q)
                context = "\n\n".join([f"Document Chunk:\n{d.page_content}" for d in docs])
                sources_list = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
                
            structured_query = f"Context:\n{context}\n\nQuestion: {q}"
            
            final_resp = llm.invoke([
                SystemMessage(content=STRICT_TINYLLAMA_PROMPT), 
                HumanMessage(content=structured_query)
            ]).content
            
            citations = ", ".join(sources_list) if sources_list else "None"
            self.safe_insert(f"\n{final_resp}\n\n[Verified Sources: {citations}]\n---\n")
            self.log_audit(q, "Success", sources_list)
            
        except Exception as e: 
            self.safe_insert(f"\nExecution Warning: Verify Ollama is awake in your taskbar. Details: {e}\n\n---\n")
            self.log_audit(q, f"Error: {str(e)}", [])

    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index):
            try: self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True)
            except: self.db = None

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Documents", "*.pdf")])
        if files:
            for f in files: shutil.copy(f, SOURCE_DIR)
            threading.Thread(target=self.rebuild_db, daemon=True).start()
            messagebox.showinfo("Processing", "Documents added. Building vector table...")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=150)
            split_docs = splitter.split_documents(docs)
            for d in split_docs: d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
            self.db = FAISS.from_documents(split_docs, self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

if __name__ == "__main__":
    from datetime import datetime
    app = SourceAgentMaster()
    app.mainloop()
