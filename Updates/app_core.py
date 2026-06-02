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

# --- PROMPT ARCHITECTURE ---
STANDARD_PROMPT = """You are a secure, offline Enterprise AI. 
CORE RULE: You operate under a STRICT SOURCE TRUTH policy. 
Answer ONLY using the exact facts found in the provided context. If the answer is not in the context, you MUST reply exactly with 'I cannot find this information in the provided sources.' Do not invent information."""

RESEARCH_PROMPT = """You are an Enterprise Research Analyst. 
Conduct a Deep Research synthesis on the provided context. 
1. Identify all core concepts related to the query.
2. Compare evidence across multiple sources if applicable.
3. Generate a highly detailed, structured Executive Report using headings and bullet points.
4. Ensure every factual claim is strictly grounded in the text. Do not hallucinate."""

# ==========================================
# SYSTEM PROVISIONING UI
# ==========================================
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
        
        self.sub_lbl = ctk.CTkLabel(self, text="Please wait. This may take a few minutes.", font=("Segoe UI", 12), text_color="#94a3b8")
        self.sub_lbl.pack(pady=10)
        
        if self.mode == "install":
            threading.Thread(target=self.download_and_install_ollama, daemon=True).start()
        elif self.mode == "pull":
            threading.Thread(target=self.pull_models, daemon=True).start()

    def disable_close(self): pass

    def download_and_install_ollama(self):
        self.lbl.configure(text="Downloading Ollama Engine...")
        installer_path = os.path.join(BASE_DIR, "OllamaSetup.exe")
        
        try:
            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, installer_path)
            self.lbl.configure(text="Installing Engine (Check Taskbar)...")
            self.sub_lbl.configure(text="Please complete the setup wizard that just opened.")
            
            # Launch installer and wait for it to close
            subprocess.run([installer_path], check=True)
            
            # Clean up
            os.remove(installer_path)
            
            self.lbl.configure(text="Installation Complete!")
            time.sleep(2)
            self.destroy()
            self.master_app.check_environment()
            
        except Exception as e:
            messagebox.showerror("Install Failed", f"Could not install Ollama: {e}\nPlease install it manually from ollama.com")
            sys.exit(1)

    def pull_models(self):
        self.lbl.configure(text=f"Pulling Local Neural Network...")
        self.sub_lbl.configure(text=f"Downloading {self.master_app.ai_model}. This requires a network connection temporarily.")
        try:
            # Hide the console window on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(["ollama", "pull", self.master_app.ai_model], check=True, startupinfo=startupinfo)
            self.destroy()
            self.master_app.finish_boot()
        except Exception as e:
            messagebox.showerror("Pull Failed", f"Could not download the AI model: {e}")
            sys.exit(1)

# ==========================================
# WINDOW CLASS: ANALYTICS DASHBOARD
# ==========================================
class AnalyticsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Enterprise Analytics")
        self.geometry("600x500")
        self.attributes("-topmost", True)
        
        ctk.CTkLabel(self, text="📊 System Analytics", font=("Segoe UI", 24, "bold"), text_color="#3b82f6").pack(pady=(20, 10))
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent"); self.stats_frame.pack(fill="x", padx=20, pady=10)
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 13), fg_color="#0f172a"); self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.load_analytics()

    def load_analytics(self):
        if not os.path.exists(AUDIT_FILE):
            self.log_box.insert("1.0", "No audit data found."); self.log_box.configure(state="disabled")
            return
        try:
            with open(AUDIT_FILE, "r") as f: logs = json.load(f)
            total_queries = len(logs)
            successful = sum(1 for log in logs if log.get("status") == "Success")
            success_rate = (successful / total_queries * 100) if total_queries > 0 else 0
            
            all_sources = []
            for log in logs:
                if isinstance(log.get("sources"), list): all_sources.extend(log.get("sources"))
            
            ctk.CTkLabel(self.stats_frame, text=f"Total Queries: {total_queries}", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
            ctk.CTkLabel(self.stats_frame, text=f"Success Rate: {success_rate:.1f}%", font=("Segoe UI", 16, "bold"), text_color="#10b981").pack(side="right", padx=20)
            
            report = "--- TOP REFERENCED DOCUMENTS ---\n\n"
            for src, count in Counter(all_sources).most_common(5): report += f"[{count} refs] -> {src}\n"
            report += "\n--- RECENT AUDIT TRAIL ---\n\n"
            for log in reversed(logs[-10:]): report += f"[{log.get('timestamp', '')[:16]}] Query: {log.get('query')}\n"
                
            self.log_box.insert("1.0", report); self.log_box.configure(state="disabled")
        except Exception as e: self.log_box.insert("1.0", f"Error: {e}")

# ==========================================
# MAIN APPLICATION ENGINE
# ==========================================
class SourceAgentMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Source Agent | Local Sovereign V38")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        self.ai_model = "tinyllama"
        self.load_settings()
        
        # Hide main window during provisioning
        self.withdraw()
        self.check_environment()

    def check_environment(self):
        # 1. Check if Ollama is installed
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        except (FileNotFoundError, subprocess.CalledProcessError):
            ProvisionerWindow(self, mode="install")
            return

        # 2. Check if the specific model is downloaded
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
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 20))
        
        ctk.CTkLabel(s, text="Local CPU Model:", font=("Segoe UI", 12)).pack(anchor="w", padx=20)
        self.model_menu = ctk.CTkOptionMenu(s, values=["tinyllama", "llama3.2:1b"], command=self.change_model)
        self.model_menu.set(self.ai_model); self.model_menu.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(s, text="📂 Ingest Documents", font=("Segoe UI", 13), fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(s, text="📊 View Analytics", font=("Segoe UI", 13), fg_color="#8b5cf6", hover_color="#7c3aed", command=lambda: AnalyticsWindow(self)).pack(fill="x", padx=20, pady=10)
        
        self.chat = ctk.CTkTextbox(self, font=("Segoe UI", 15), fg_color="#0f172a", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=1, sticky="nsew", padx=20, pady=(20, 10))
        self.chat.insert("1.0", "SYSTEM: Local CPU Engine Online. 100% Offline Mode Active.\n\n")
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=50, placeholder_text="Ask the local AI a policy question...", font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send_main())
        
        self.research_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(input_frame, text="Deep Research", variable=self.research_var, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(input_frame, text="Submit", width=100, height=50, fg_color="#3b82f6", font=("Segoe UI", 14, "bold"), command=self.send_main).grid(row=0, column=2)

    def change_model(self, selection):
        self.ai_model = selection
        self.save_settings()
        # Immediately verify if the newly selected model needs to be downloaded
        self.withdraw()
        self.check_environment()

    def log_audit(self, query, status, sources):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "status": status, "sources": sources}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

    def safe_insert(self, target, text):
        def _update():
            target.configure(state="normal"); target.insert("end", text); target.see("end"); target.configure(state="disabled")
        self.after(0, _update)

    def send_main(self):
        q = self.entry.get().strip(); 
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.engine_generate, args=(q,), daemon=True).start()

    def engine_generate(self, q):
        self.safe_insert(self.chat, f"\nUSER: {q}\nAGENT: Computing locally via {self.ai_model}...\n")
        
        is_deep_research = self.research_var.get()
        try:
            llm = ChatOllama(model=self.ai_model, temperature=0.1, base_url="http://localhost:11434")
            context = ""; sources_list = []
            
            if self.db:
                k_depth = 12 if is_deep_research else 5
                docs = self.db.as_retriever(search_kwargs={"k": k_depth}).invoke(q)
                context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')} | Page: {d.metadata.get('page', 'N/A')}\n{d.page_content}" for d in docs])
                sources_list = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
                
            sys_prompt = RESEARCH_PROMPT if is_deep_research else STANDARD_PROMPT
            final_resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]).content
            
            citations = ", ".join(sources_list) if sources_list else "None"
            self.safe_insert(self.chat, f"\n{final_resp}\n\n[Sources Referenced: {citations}]\n---\n")
            self.log_audit(q, "Success", sources_list)
            
        except Exception as e: 
            self.safe_insert(self.chat, f"\nSystem Error: Make sure Ollama is running in your system tray. {e}\n\n---\n")
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
            messagebox.showinfo("Processing", "Documents added. Indexing via CPU in background...")

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=250)
            split_docs = splitter.split_documents(docs)
            for d in split_docs: d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
            self.db = FAISS.from_documents(split_docs, self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f: self.ai_model = json.load(f).get("ai_model", "tinyllama")
            except: pass

    def save_settings(self):
        with open(SAVE_FILE, "w") as f: json.dump({"ai_model": self.ai_model}, f)

if __name__ == "__main__":
    from datetime import datetime
    app = SourceAgentMaster()
    app.mainloop()
