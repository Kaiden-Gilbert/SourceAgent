import os, sys, threading, shutil, json, time, urllib.request, subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from collections import Counter
from datetime import datetime

from langchain_community.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage

# --- CONFIGURATION & VERSIONING ---
CURRENT_VERSION = 41.0
VERSION_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/version.json"

BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.json")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(SOURCE_DIR, exist_ok=True)

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"

# --- SYSTEM PROMPTS ---
STRICT_TINYLLAMA_PROMPT = """You are a strict reading assistant.
You must ONLY use the provided facts inside the Context section below.
If the answer is not directly stated in the Context, say exactly: "I cannot find this information in the provided sources."
Do not make up facts. Do not use outside knowledge. Stick strictly to the text."""

RESEARCH_PROMPT = """You are an Enterprise Research Analyst. 
Conduct a Deep Research synthesis on the provided context. 
1. Identify all core concepts related to the query.
2. Compare evidence across multiple sources.
3. Generate a highly detailed, structured Executive Report.
4. Ensure every factual claim is strictly grounded in the text."""

STUDIO_PROMPTS = {
    "Executive Briefing": "You are an executive assistant. Using the provided context, write a high-level Executive Briefing. Use professional formatting, clear headings, and bullet points to summarize the main objectives, key data points, and conclusions found in the text. Do not invent information.",
    "FAQ Document": "You are a technical writer. Using the provided context, generate a Frequently Asked Questions (FAQ) document. Identify the 5 most important topics in the text and format them as clear Question and Answer pairs.",
    "Study Guide": "You are an expert tutor. Using the provided context, create a comprehensive Study Guide. Break down the core concepts into easy-to-understand sections, provide definitions for key terms found in the text, and summarize the main arguments."
}

# ==========================================
# UI COMPONENTS: TOAST & PROVISIONER
# ==========================================
class NotificationToast(ctk.CTkFrame):
    def __init__(self, parent, title, message, color="#f59e0b"):
        super().__init__(parent, fg_color="#1e293b", border_width=2, border_color=color, corner_radius=8)
        self.parent = parent
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 14, "bold"), text_color=color).pack(anchor="w", padx=15, pady=(10, 0))
        ctk.CTkLabel(self, text=message, font=("Segoe UI", 12), justify="left", wraplength=300).pack(anchor="w", padx=15, pady=(0, 10))
        
        self.place(relx=0.5, rely=-0.2, anchor="n")
        self.animate_in(0)
        
    def animate_in(self, step):
        if step < 20:
            self.place(relx=0.5, rely=-0.2 + (step * 0.012), anchor="n")
            self.after(15, lambda: self.animate_in(step + 1))
        else: self.after(6000, self.animate_out, 0)
            
    def animate_out(self, step):
        if step < 20:
            self.place(relx=0.5, rely=0.04 - (step * 0.012), anchor="n")
            self.after(15, lambda: self.animate_out(step + 1))
        else: self.destroy()

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
        self.pb = ctk.CTkProgressBar(self, mode="indeterminate", width=400); self.pb.pack(); self.pb.start()
        self.sub_lbl = ctk.CTkLabel(self, text="Please wait. Preparing environment...", font=("Segoe UI", 12), text_color="#94a3b8")
        self.sub_lbl.pack(pady=10)
        
        if self.mode == "install": threading.Thread(target=self.download_and_install_ollama, daemon=True).start()
        elif self.mode == "pull": threading.Thread(target=self.pull_tinyllama, daemon=True).start()

    def disable_close(self): pass

    def download_and_install_ollama(self):
        self.after(0, lambda: self.lbl.configure(text="Downloading Ollama Engine..."))
        installer_path = os.path.join(BASE_DIR, "OllamaSetup.exe")
        try:
            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, installer_path)
            self.after(0, lambda: self.lbl.configure(text="Installing Engine (Check Taskbar)..."))
            self.after(0, lambda: self.sub_lbl.configure(text="Please finish the setup wizard that popped up on your screen."))
            subprocess.run([installer_path], check=True)
            if os.path.exists(installer_path): os.remove(installer_path)
            self.after(0, lambda: self.lbl.configure(text="Installation Finished!"))
            time.sleep(2)
            self.after(0, self.destroy); self.after(0, self.master_app.check_environment)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Setup Failed", f"Could not auto-install Ollama: {e}\nPlease run it manually from ollama.com"))
            self.after(0, lambda: sys.exit(1))

    def pull_tinyllama(self):
        self.after(0, lambda: self.lbl.configure(text="Pulling TinyLlama Core..."))
        self.after(0, lambda: self.sub_lbl.configure(text="Downloading model parameters (~650MB)."))
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ollama", "pull", "tinyllama"], check=True, startupinfo=startupinfo)
            self.after(0, self.destroy); self.after(0, self.master_app.finish_boot)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Download Failed", f"Ollama failed to pull tinyllama: {e}"))
            self.after(0, lambda: sys.exit(1))


# ==========================================
# MAIN APPLICATION ENGINE (TABBED MONOLITH)
# ==========================================
class SourceAgentMaster(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Source Agent | Enterprise Workspace V{CURRENT_VERSION}")
        self.geometry("1280x850")
        ctk.set_appearance_mode("Dark")
        
        self.ai_model = "tinyllama"
        self.withdraw()
        self.after(100, self.check_environment)

    def check_environment(self):
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        except:
            ProvisionerWindow(self, mode="install")
            return

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
        threading.Thread(target=self.sentinel_update_check, daemon=True).start()

    def sentinel_update_check(self):
        while True:
            try:
                req = urllib.request.Request(VERSION_URL + "?t=" + str(time.time()), headers={'Cache-Control': 'no-cache'})
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read().decode('utf-8'))
                    cloud_version = float(data.get('app_version', CURRENT_VERSION))
                    if cloud_version > CURRENT_VERSION:
                        msg = f"Version {cloud_version} is available! Save your work and restart the application to apply the update automatically."
                        self.after(0, lambda: NotificationToast(self, "System Update Available", msg, color="#f59e0b"))
                        break 
            except: pass
            time.sleep(300) 

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        # --- SIDEBAR ---
        s = ctk.CTkFrame(self, width=280, fg_color="#020617", corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(s, text="🏛️ Source Agent", font=("Segoe UI", 24, "bold")).pack(pady=(30, 10))
        ctk.CTkLabel(s, text="🔒 100% Offline Air-Gapped Mode", font=("Segoe UI", 11), text_color="#10b981").pack(pady=(0, 25))
        
        info_frame = ctk.CTkFrame(s, fg_color="#0f172a", height=60)
        info_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(info_frame, text="Active Core: TinyLlama", font=("Segoe UI", 12, "bold"), text_color="#3b82f6").place(relx=0.5, rely=0.3, anchor="center")
        ctk.CTkLabel(info_frame, text=f"Build Version: {CURRENT_VERSION}", font=("Segoe UI", 10), text_color="#94a3b8").place(relx=0.5, rely=0.7, anchor="center")

        ctk.CTkButton(s, text="📂 Ingest PDF Sources", font=("Segoe UI", 14, "bold"), height=45, fg_color="#0ea5e9", hover_color="#0284c7", command=self.add_docs).pack(fill="x", padx=20, pady=(20, 10))
        
        # --- MAIN TABBED VIEW ---
        self.tabview = ctk.CTkTabview(self, fg_color="#0f172a", segmented_button_selected_color="#3b82f6")
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.tab_chat = self.tabview.add("Agentic Chat")
        self.tab_studio = self.tabview.add("Notebook Studio")
        self.tab_analytics = self.tabview.add("System Analytics")
        
        self.build_chat_tab()
        self.build_studio_tab()
        self.build_analytics_tab()

    # ------------------------------------------
    # TAB 1: AGENTIC CHAT
    # ------------------------------------------
    def build_chat_tab(self):
        self.tab_chat.grid_columnconfigure(0, weight=1); self.tab_chat.grid_rowconfigure(0, weight=1)
        
        self.chat = ctk.CTkTextbox(self.tab_chat, font=("Segoe UI", 15), fg_color="#1e293b", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=0, sticky="nsew", pady=(10, 20))
        self.chat.insert("1.0", "SYSTEM: TinyLlama compute core activated. Ready for inquiry.\n\n")
        self.chat.configure(state="disabled")
        
        input_frame = ctk.CTkFrame(self.tab_chat, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_frame, height=50, placeholder_text="Ask a question from your documents...", font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.send_chat())
        
        self.research_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(input_frame, text="Deep Research", variable=self.research_var, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(input_frame, text="Query Core", width=120, height=50, fg_color="#3b82f6", font=("Segoe UI", 14, "bold"), command=self.send_chat).grid(row=0, column=2)

    def send_chat(self):
        q = self.entry.get().strip(); 
        if not q: return
        self.entry.delete(0, "end")
        threading.Thread(target=self.engine_chat, args=(q,), daemon=True).start()

    def engine_chat(self, q):
        self.after(0, lambda: self.safe_insert(self.chat, f"\nUSER: {q}\nAGENT: Inquiring localized text embeddings...\n"))
        is_deep_research = self.research_var.get()
        
        try:
            llm = ChatOllama(model=self.ai_model, temperature=0.0, base_url="http://localhost:11434")
            context = ""; sources_list = []
            
            if self.db:
                k_depth = 10 if is_deep_research else 4
                docs = self.db.as_retriever(search_kwargs={"k": k_depth}).invoke(q)
                context = "\n\n".join([f"Document Chunk:\n{d.page_content}" for d in docs])
                sources_list = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
                
            structured_query = f"Context:\n{context}\n\nQuestion: {q}"
            sys_prompt = RESEARCH_PROMPT if is_deep_research else STRICT_TINYLLAMA_PROMPT
            
            final_resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=structured_query)]).content
            citations = ", ".join(sources_list) if sources_list else "None"
            
            self.after(0, lambda: self.safe_insert(self.chat, f"\n{final_resp}\n\n[Verified Sources: {citations}]\n---\n"))
            self.log_audit(q, "Success", sources_list)
            self.after(0, self.refresh_analytics) # Update analytics tab automatically
            
        except Exception as e: 
            self.after(0, lambda: self.safe_insert(self.chat, f"\nExecution Warning: {e}\n\n---\n"))
            self.log_audit(q, f"Error: {str(e)}", [])

    # ------------------------------------------
    # TAB 2: NOTEBOOK STUDIO (DOCUMENT GENERATOR)
    # ------------------------------------------
    def build_studio_tab(self):
        self.tab_studio.grid_columnconfigure(0, weight=1); self.tab_studio.grid_rowconfigure(1, weight=1)
        
        header_frame = ctk.CTkFrame(self.tab_studio, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(10, 20))
        
        ctk.CTkLabel(header_frame, text="Document Type:", font=("Segoe UI", 14, "bold")).pack(side="left", padx=(0, 10))
        self.doc_type_menu = ctk.CTkOptionMenu(header_frame, values=["Executive Briefing", "FAQ Document", "Study Guide"], width=200)
        self.doc_type_menu.pack(side="left", padx=10)
        
        ctk.CTkButton(header_frame, text="✨ Generate Document", font=("Segoe UI", 13, "bold"), fg_color="#8b5cf6", hover_color="#7c3aed", command=self.generate_studio_doc).pack(side="left", padx=20)
        ctk.CTkButton(header_frame, text="💾 Save to File", font=("Segoe UI", 13), fg_color="#10b981", hover_color="#059669", command=self.export_studio).pack(side="right")
        
        self.studio_box = ctk.CTkTextbox(self.tab_studio, font=("Consolas", 14), fg_color="#1e293b", spacing1=5, spacing3=5)
        self.studio_box.grid(row=1, column=0, sticky="nsew")
        self.studio_box.insert("1.0", "--- NOTEBOOK STUDIO ---\nSelect a document type above and click Generate to synthesize your ingested sources into a structured report.\n")

    def generate_studio_doc(self):
        if not self.db:
            messagebox.showwarning("No Data", "Please ingest PDF sources first before generating documents.")
            return
            
        doc_type = self.doc_type_menu.get()
        self.studio_box.delete("1.0", "end")
        self.studio_box.insert("end", f"Generating {doc_type}...\nQuerying global vector database...\nSynthesizing context, please wait...\n\n")
        
        threading.Thread(target=self._process_studio_generation, args=(doc_type,), daemon=True).start()

    def _process_studio_generation(self, doc_type):
        try:
            # We use a broad search query to pull general concepts from the FAISS db
            broad_query = "What are the core concepts, main topics, and primary details discussed in these documents?"
            docs = self.db.as_retriever(search_kwargs={"k": 8}).invoke(broad_query)
            context = "\n\n".join([f"Document Chunk:\n{d.page_content}" for d in docs])
            
            sys_prompt = STUDIO_PROMPTS.get(doc_type, STUDIO_PROMPTS["Executive Briefing"])
            llm = ChatOllama(model=self.ai_model, temperature=0.1, base_url="http://localhost:11434")
            
            final_resp = llm.invoke([
                SystemMessage(content=sys_prompt), 
                HumanMessage(content=f"Context:\n{context}\n\nTask: Generate the {doc_type}.")
            ]).content
            
            self.after(0, lambda: self.studio_box.delete("1.0", "end"))
            self.after(0, lambda: self.studio_box.insert("end", f"# {doc_type.upper()}\nGenerated by Source Agent Studio\n\n{final_resp}\n"))
            self.log_audit(f"Studio Gen: {doc_type}", "Success", list(set([d.metadata.get('source', 'Unknown') for d in docs])))
            self.after(0, self.refresh_analytics)
            
        except Exception as e:
            self.after(0, lambda: self.studio_box.insert("end", f"\n[ERROR: {str(e)}]"))

    def export_studio(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md"), ("Text File", "*.txt")], title="Export Studio Document")
        if file_path:
            try:
                content = self.studio_box.get("1.0", "end-1c")
                with open(file_path, "w", encoding="utf-8") as f: f.write(content)
                messagebox.showinfo("Success", "Document successfully exported!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

    # ------------------------------------------
    # TAB 3: SYSTEM ANALYTICS
    # ------------------------------------------
    def build_analytics_tab(self):
        self.tab_analytics.grid_columnconfigure(0, weight=1); self.tab_analytics.grid_rowconfigure(1, weight=1)
        
        self.stats_frame = ctk.CTkFrame(self.tab_analytics, fg_color="transparent")
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(10, 20))
        
        self.lbl_total = ctk.CTkLabel(self.stats_frame, text="Total Queries: 0", font=("Segoe UI", 16, "bold"))
        self.lbl_total.pack(side="left", padx=20)
        
        self.lbl_success = ctk.CTkLabel(self.stats_frame, text="Success Rate: 0%", font=("Segoe UI", 16, "bold"), text_color="#10b981")
        self.lbl_success.pack(side="right", padx=20)
        
        self.log_box = ctk.CTkTextbox(self.tab_analytics, font=("Consolas", 13), fg_color="#1e293b")
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self.refresh_analytics()

    def refresh_analytics(self):
        if not os.path.exists(AUDIT_FILE):
            self.log_box.configure(state="normal"); self.log_box.delete("1.0", "end")
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
            
            self.lbl_total.configure(text=f"Total Document Inquiries: {total_queries}")
            self.lbl_success.configure(text=f"Data Adherence: {success_rate:.1f}%")
            
            report = "--- TOP SECURITY DOCS CONSULTED ---\n\n"
            for src, count in Counter(all_sources).most_common(5): report += f"[{count} read-hits] -> {src}\n"
            report += "\n--- HISTORICAL RUNTIME LOG ---\n\n"
            for log in reversed(logs[-15:]): report += f"[{log.get('timestamp', '')[:16]}] Action: {log.get('query')}\n"
                
            self.log_box.configure(state="normal"); self.log_box.delete("1.0", "end")
            self.log_box.insert("1.0", report); self.log_box.configure(state="disabled")
        except: pass

    # ------------------------------------------
    # UTILITIES
    # ------------------------------------------
    def safe_insert(self, target, text):
        target.configure(state="normal"); target.insert("end", text); target.see("end"); target.configure(state="disabled")

    def log_audit(self, query, status, sources):
        entry = {"timestamp": datetime.now().isoformat(), "query": query, "status": status, "sources": sources}
        try:
            log_data = []
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r") as f: log_data = json.load(f)
            log_data.append(entry)
            with open(AUDIT_FILE, "w") as f: json.dump(log_data, f, indent=4)
        except: pass

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
    app = SourceAgentMaster()
    app.mainloop()
