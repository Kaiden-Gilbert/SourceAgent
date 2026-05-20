import os, sys, threading, time, base64, math, uuid, json, shutil
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

# --- V8/V9 VAULT INTEGRATION ---
BASE_DIR = globals().get('VAULT_DIR', os.path.abspath(os.path.dirname(__file__)) if '__file__' in globals() else os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
ENV_FILE = os.path.join(BASE_DIR, ".env")

for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# ==========================================
# THE ENTERPRISE POLICY ADVISOR DIRECTIVE
# ==========================================
POLICY_ADVISOR_SYSTEM_PROMPT = """You are an internal company policy knowledge repository named "Policy Advisor 2026." 
Your primary goal is to answer employee questions about workplace situations strictly by referencing official company policy documents provided to you in the context.

You must only provide answers that are grounded in the available policy content. When a relevant policy applies, you must:
- Identify the exact policy name
- Identify the specific section within that policy
- Quote verbatim the exact excerpt from the policy that supports the answer
- Clearly separate quoted material from any explanation

Before identifying relevant policies, interpret the scenario and identify all underlying policy themes and risks, even if not explicitly stated. Expand the scenario into these themes and search for related policies. Do not rely solely on direct keyword matches.
Examples:
- Receiving a gift → bribery, conflict of interest, safeguarding
- Data sharing → data protection, confidentiality
- Student safety → safeguarding, duty of care, incident reporting

After presenting all relevant quoted excerpts, provide:
1) A plain English explanation of what the policy means (based strictly on quoted text).
2) If a specific situation is described, a plain English application of the policy to that scenario.

Consider the user’s role. Only ask for the user’s role if policy applicability depends on it. Evaluate ALL available policies for every query. Do not stop at the first match.

When multiple policies apply:
- Include all relevant policies.
- Prioritise policies related to legal, regulatory, or compliance risks (e.g. bribery, data protection, safeguarding) over general guidance.
- Order output by relevance and risk level.
- Prioritise Bribery/Gifts policies for situations involving gifts/payments.
- Consider context (e.g., receiving vs. giving).
- Do not rely solely on a general policy if a specific one exists.

For safeguarding/safety-critical scenarios:
- Recognise risk and urgency.
- Perform an additional pass for escalation, emergency response, or incident reporting policies.
- Avoid treating high-risk scenarios as routine.

If no relevant policy is found in the provided context, you must first ask up to a maximum of 2 clarifying follow-up questions (including role clarification) to try to identify an applicable policy. If still none is found, state clearly that no applicable policy could be located. 

DO NOT invent, infer, or generalize beyond the written text. DO NOT provide personal opinions or external knowledge.

Response Structure:
- Policy Reference(s): [Policy name + section]
- Verbatim Quote(s): [Exact excerpt(s)]
- Plain English Explanation: [Synthesised explanation]
- Application to Scenario: [If applicable]

Tone: Professional, plain, and readable. Avoid overly legalistic language. Assume policies may be updated. Never fabricate language or citations."""

class SourceAgentWorkspace(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026")
        self.geometry("1300x850")
        
        self.theme_mode = "Dark"
        self.bg_dark = "#050508"
        self.bg_surface = "#0f0f1a"
        self.accent = "#6366f1"
        self.text_main = "#f8fafc"
        self.text_muted = "#64748b"
        
        self.cached_vectorstore = None
        self.attached_media_path = None
        self.user_name = None
        self.token_speed = 30 
        self.current_session_id = str(uuid.uuid4())
        self.session_history = []
        
        self.load_save_data()
        self.apply_theme(self.theme_mode)
        
        load_dotenv(ENV_FILE)
        api_key = os.environ.get("OPENROUTER_API_KEY")
        
        self.draw_dynamic_background()
        
        if not self.user_name or not api_key:
            self.show_installer_wizard()
        else:
            self.setup_ai_failover(api_key)
            self.show_cinematic_welcome()

    def apply_theme(self, mode):
        self.theme_mode = mode
        ctk.set_appearance_mode(mode)
        if mode == "Dark":
            self.bg_dark, self.bg_surface, self.text_main, self.text_muted = "#050508", "#0f0f1a", "#f8fafc", "#64748b"
        else:
            self.bg_dark, self.bg_surface, self.text_main, self.text_muted = "#e2e8f0", "#f8fafc", "#0f172a", "#475569"

    def draw_dynamic_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg=self.bg_dark)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.orbs = [self.bg_canvas.create_oval(0,0,0,0, outline="", fill="#1e1b4b"), self.bg_canvas.create_oval(0,0,0,0, outline="", fill="#312e81")]
        self.anim_step = 0
        self.animate_bg()

    def animate_bg(self):
        if not self.winfo_exists(): return
        w, h = self.winfo_width(), self.winfo_height()
        if w > 100:
            self.anim_step += 0.015
            x1 = (math.sin(self.anim_step) * (w/3)) + (w/2)
            y1 = (math.cos(self.anim_step * 0.7) * (h/3)) + (h/2)
            self.bg_canvas.coords(self.orbs[0], x1-600, y1-600, x1+600, y1+600)
            x2 = (math.cos(self.anim_step * 0.5) * (w/4)) + (w/2)
            y2 = (math.sin(self.anim_step * 0.8) * (h/4)) + (h/2)
            self.bg_canvas.coords(self.orbs[1], x2-400, y2-400, x2+400, y2+400)
        self.bg_canvas.lower("all")
        self.after(30, self.animate_bg)

    def show_installer_wizard(self):
        self.wizard_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.wizard_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.title_frame = tk.Frame(self.wizard_frame, bg=self.bg_dark, width=600, height=100)
        self.title_frame.place(relx=0.5, rely=0.25, anchor="center")
        self.title_chars = []
        
        title_text = "POLICY ADVISOR 2026"
        start_x = 20
        for i, char in enumerate(title_text):
            lbl = tk.Label(self.title_frame, text=char, font=("Segoe UI", 32, "bold"), bg=self.bg_dark, fg=self.text_main)
            lbl.place(x=start_x + (i*28), y=50, anchor="center")
            self.title_chars.append((lbl, start_x + (i*28)))
            
        self.wave_step = 0
        self.is_waving = True
        self.animate_wave()
        
        box = ctk.CTkFrame(self.wizard_frame, fg_color=self.bg_surface, corner_radius=20, border_width=1, border_color="#1a1a2e")
        box.place(relx=0.5, rely=0.6, anchor="center")
        
        ctk.CTkLabel(box, text="System Initialization", font=("Segoe UI", 20, "bold"), text_color=self.text_main).pack(pady=(30, 10), padx=40)
        self.name_e = ctk.CTkEntry(box, placeholder_text="Enter your display name...", width=320, height=45)
        self.name_e.pack(pady=10, padx=40)
        self.api_e = ctk.CTkEntry(box, placeholder_text="Paste your OpenRouter API Key...", width=320, height=45, show="*")
        self.api_e.pack(pady=10, padx=40)
        ctk.CTkButton(box, text="Finalize Installation", height=45, fg_color=self.accent, font=("Segoe UI", 14, "bold"), command=self.run_installation).pack(pady=(20, 40))

    def animate_wave(self):
        if not self.is_waving: return
        self.wave_step += 0.15
        for i, (lbl, basex) in enumerate(self.title_chars):
            offset = math.sin(self.wave_step + i) * 10
            lbl.place(x=basex, y=50 + offset, anchor="center")
            lbl.config(fg=self.accent if math.sin(self.wave_step + i) > 0 else self.text_main)
        self.after(30, self.animate_wave)

    def run_installation(self):
        name = self.name_e.get().strip()
        api_key = self.api_e.get().strip()
        if not name or not api_key: return
        with open(ENV_FILE, "w") as f: f.write(f"OPENROUTER_API_KEY={api_key}\n")
        self.user_name = name
        self.save_current_state()
        self.is_waving = False
        self.wizard_frame.destroy()
        self.setup_ai_failover(api_key)
        self.show_cinematic_welcome()

    def show_cinematic_welcome(self):
        self.welcome_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.welcome_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.welcome_lbl = ctk.CTkLabel(self.welcome_frame, text="", font=("Segoe UI", 48, "bold"), text_color=self.text_main)
        self.welcome_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.full_welcome_text = f"Welcome, {self.user_name}."
        self.type_index = 0
        self.type_text_effect()

    def type_text_effect(self):
        if self.type_index < len(self.full_welcome_text):
            self.welcome_lbl.configure(text=self.welcome_lbl.cget("text") + self.full_welcome_text[self.type_index])
            self.type_index += 1
            self.after(40 if self.full_welcome_text[self.type_index-1] != " " else 100, self.type_text_effect)
        else:
            self.welcome_lbl.configure(text_color=self.accent)
            self.after(1200, self.transition_to_workspace)

    def transition_to_workspace(self):
        self.welcome_frame.destroy()
        self.bg_canvas.destroy() 
        self.build_main_ui()

    def setup_ai_failover(self, key):
        base = "https://openrouter.ai/api/v1"
        e_prim = ChatOpenAI(base_url=base, api_key=key, model="google/gemini-2.0-flash-lite-preview-02-05:free", streaming=True, max_retries=1)
        e_back = ChatOpenAI(base_url=base, api_key=key, model="meta-llama/llama-3.2-11b-vision-instruct:free", streaming=True, max_retries=3)
        self.editor_engine = e_prim.with_fallbacks([e_back])
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.load_local_vectorstore()

    def build_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=300, fg_color=self.bg_dark, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="🏛️ Policy Advisor", font=("Segoe UI", 22, "bold")).pack(pady=(30, 10), padx=20)
        
        ctk.CTkButton(self.sidebar, text="📄 Upload Policy Documents", fg_color="#27ae60", hover_color="#2ecc71", command=self.add_source_document).pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkButton(self.sidebar, text="⚙️ Manage Database", fg_color="transparent", border_width=1, border_color=self.text_muted, text_color=self.text_main, command=self.open_source_manager).pack(fill="x", padx=20, pady=5)
        
        self.source_count_lbl = ctk.CTkLabel(self.sidebar, text="0 Policies Loaded", font=("Segoe UI", 11), text_color=self.text_muted)
        self.source_count_lbl.pack(pady=(0, 20))
        
        ctk.CTkButton(self.sidebar, text="+ New Inquiry", fg_color=self.accent, command=self.start_new_session).pack(fill="x", padx=20, pady=10)
        self.history_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=400)
        self.history_scroll.pack(fill="x", padx=10, pady=10)
        
        self.chat_frame = ctk.CTkFrame(self, fg_color=self.bg_surface, corner_radius=15, border_width=1, border_color="#1a1a2e")
        self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(0, weight=1); self.chat_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(self.chat_frame, state="disabled", font=("Segoe UI", 16), wrap="word", fg_color="transparent", spacing1=5, spacing3=5)
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        input_bar = ctk.CTkFrame(self.chat_frame, fg_color=self.bg_dark, corner_radius=12)
        input_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        input_bar.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(input_bar, text="📸", width=40, font=("Segoe UI", 18), command=self.attach_media, fg_color="transparent", hover_color="#1a1a2e").grid(row=0, column=0, padx=10)
        self.user_input = ctk.CTkEntry(input_bar, placeholder_text="Ask a compliance or policy question...", height=50, fg_color="transparent", border_width=0, font=("Segoe UI", 14))
        self.user_input.grid(row=0, column=1, sticky="ew")
        self.user_input.bind("<Return>", lambda e: self.send_message())
        ctk.CTkButton(input_bar, text="Submit", width=80, command=self.send_message, fg_color=self.accent).grid(row=0, column=2, padx=10)
        
        status_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        status_frame.grid(row=1, column=0, sticky="ew", padx=30)
        self.status_bar = ctk.CTkLabel(status_frame, text="🟢 Compliance Engine Online", font=("Segoe UI", 12), text_color=self.text_muted)
        self.status_bar.pack(side="left")
        ctk.CTkButton(status_frame, text="⚙️ Options", width=60, fg_color="transparent", hover_color="#1a1a2e", text_color=self.text_muted, command=self.open_settings_menu).pack(side="right")
        
        self.update_sidebar_history()
        self.update_source_count()
        self.load_active_chat()

    def load_local_vectorstore(self):
        index_path = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index_path):
            try: self.cached_vectorstore = FAISS.load_local(index_path, self.embeddings, allow_dangerous_deserialization=True)
            except: self.cached_vectorstore = None
        else: self.cached_vectorstore = None

    def add_source_document(self):
        fps = filedialog.askopenfilenames(filetypes=[("Documents", "*.pdf *.txt *.docx")])
        if fps:
            self.status_bar.configure(text="Indexing Policies...", text_color="#f39c12")
            for fp in fps: shutil.copy(fp, SOURCE_DIR)
            threading.Thread(target=self.rebuild_vectorstore, daemon=True).start()

    def open_source_manager(self):
        win = ctk.CTkToplevel(self)
        win.title("Manage Policy Database")
        win.geometry("500x400")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.bg_surface)
        ctk.CTkLabel(win, text="Active Policy Documents", font=("Segoe UI", 20, "bold"), text_color=self.text_main).pack(pady=(20, 10))
        scroll = ctk.CTkScrollableFrame(win, fg_color=self.bg_dark, width=450, height=250)
        scroll.pack(pady=10, padx=20, fill="both", expand=True)
        
        def refresh_list():
            for w in scroll.winfo_children(): w.destroy()
            files = [f for f in os.listdir(SOURCE_DIR) if f.endswith(('.pdf', '.txt', '.docx'))]
            if not files: return ctk.CTkLabel(scroll, text="No policies loaded.", text_color=self.text_muted).pack(pady=20)
            for f in files:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=5)
                ctk.CTkLabel(row, text=f, font=("Segoe UI", 12), text_color=self.text_main).pack(side="left", padx=10)
                ctk.CTkButton(row, text="🗑️", width=30, fg_color="#e74c3c", hover_color="#c0392b", command=lambda filename=f: self.delete_source(filename, refresh_list)).pack(side="right", padx=10)
        refresh_list()

    def delete_source(self, filename, callback):
        try:
            os.remove(os.path.join(SOURCE_DIR, filename))
            self.status_bar.configure(text=f"Removed {filename}. Rebuilding...", text_color="#f39c12")
            callback()
            threading.Thread(target=self.rebuild_vectorstore, daemon=True).start()
        except Exception as e: messagebox.showerror("Error", str(e))

    def rebuild_vectorstore(self):
        docs = []
        index_path = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index_path): shutil.rmtree(index_path)
        for file in os.listdir(SOURCE_DIR):
            path = os.path.join(SOURCE_DIR, file)
            try:
                if file.endswith(".pdf"): docs.extend(PyMuPDFLoader(path).load())
                elif file.endswith(".txt"): docs.extend(TextLoader(path, encoding="utf-8").load())
                elif file.endswith(".docx"): docs.extend(Docx2txtLoader(path).load())
            except: pass
        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            self.cached_vectorstore = FAISS.from_documents(splitter.split_documents(docs), self.embeddings)
            self.cached_vectorstore.save_local(index_path)
            self.after(0, lambda: self.status_bar.configure(text="Database Active.", text_color="#2ecc71"))
        else:
            self.cached_vectorstore = None
            self.after(0, lambda: self.status_bar.configure(text="Database Empty.", text_color=self.text_muted))
        self.after(0, self.update_source_count)

    def update_source_count(self):
        count = len([f for f in os.listdir(SOURCE_DIR) if f.endswith(('.pdf', '.txt', '.docx'))])
        if hasattr(self, 'source_count_lbl'):
            self.source_count_lbl.configure(text=f"{count} Policies Loaded", text_color="#2ecc71" if count > 0 else self.text_muted)

    def attach_media(self):
        fp = filedialog.askopenfilename(filetypes=[("Media", "*.png;*.jpg;*.jpeg;*.mp4;*.avi")])
        if fp:
            self.attached_media_path = fp
            self.status_bar.configure(text=f"📎 Attached: {os.path.basename(fp)}", text_color=self.accent)

    def send_message(self):
        q = self.user_input.get().strip()
        if not q: return
        self.user_input.delete(0, "end")
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"👤 Inquiry: {q}\n\n")
        self.chat_display.configure(state="disabled")
        self.append_to_chat_history(f"👤 Inquiry: {q}\n\n")
        threading.Thread(target=self.process_query, args=(q,), daemon=True).start()

    def process_query(self, query):
        try:
            self.after(0, lambda: self.status_bar.configure(text="🧠 Scanning Policies...", text_color=self.accent))
            context = ""
            if self.cached_vectorstore:
                # Increased K to 6 to ensure it pulls a broader range of policies for comprehensive scanning
                retrieved_docs = self.cached_vectorstore.as_retriever(search_kwargs={"k": 6}).invoke(query)
                context = "\n".join([d.page_content for d in retrieved_docs])

            # Inject the strict enterprise logic
            messages = [SystemMessage(content=POLICY_ADVISOR_SYSTEM_PROMPT)]
            
            final_query = f"Available Policy Documents:\n{context}\n\nUser Scenario/Question: {query}" if context else f"User Scenario/Question: {query}"

            if self.attached_media_path:
                with open(self.attached_media_path, "rb") as f: b64 = base64.b64encode(f.read()).decode('utf-8')
                self.attached_media_path = None
                messages.append(HumanMessage(content=[{"type": "text", "text": final_query}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]))
            else:
                messages.append(HumanMessage(content=final_query))

            self.after(0, lambda: self.status_bar.configure(text="⚡ Auditing...", text_color=self.accent))
            self.after(0, lambda: self.chat_display.configure(state="normal"))
            self.after(0, lambda: self.chat_display.insert("end", "🏛️ Policy Advisor: "))
            
            full_response = "🏛️ Policy Advisor: "
            stream = self.editor_engine.stream(messages)
            
            for chunk in stream:
                full_response += chunk.content
                self.after(0, lambda c=chunk.content: self.chat_display.insert("end", c))
                if self.token_speed > 0: time.sleep(self.token_speed / 1000.0) 
            
            self.after(0, lambda: self.chat_display.insert("end", "\n\n"))
            self.after(0, lambda: self.chat_display.configure(state="disabled"))
            self.after(0, lambda: self.status_bar.configure(text="🟢 Compliance Engine Online", text_color=self.text_muted))
            
            self.append_to_chat_history(full_response + "\n\n")
            
            if len(self.session_history) == 0 or self.session_history[0]['id'] != self.current_session_id:
                self.session_history.insert(0, {'id': self.current_session_id, 'title': query[:20] + "..." if len(query) > 20 else query})
                self.save_current_state()
                self.after(0, self.update_sidebar_history)

        except Exception as e: 
            self.after(0, lambda: messagebox.showerror("Matrix Error", f"Engine failed.\n\n{str(e)}"))
            self.after(0, lambda: self.status_bar.configure(text="🟢 Compliance Engine Online", text_color=self.text_muted))

    def append_to_chat_history(self, text):
        with open(os.path.join(HISTORY_DIR, f"{self.current_session_id}.txt"), "a", encoding="utf-8") as f: f.write(text)

    def load_active_chat(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        hf = os.path.join(HISTORY_DIR, f"{self.current_session_id}.txt")
        if os.path.exists(hf):
            with open(hf, "r", encoding="utf-8") as f: self.chat_display.insert("end", f.read())
        self.chat_display.configure(state="disabled")

    def switch_session(self, session_id):
        self.current_session_id = session_id
        self.load_active_chat()

    def start_new_session(self):
        self.current_session_id = str(uuid.uuid4())
        self.load_active_chat()

    def update_sidebar_history(self):
        for w in self.history_scroll.winfo_children(): w.destroy()
        for item in self.session_history: 
            ctk.CTkButton(self.history_scroll, text=item['title'], fg_color="transparent", anchor="w", command=lambda sid=item['id']: self.switch_session(sid)).pack(fill="x", pady=2)

    def open_settings_menu(self):
        win = ctk.CTkToplevel(self)
        win.title("Options")
        win.geometry("450x450")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.bg_surface)
        
        ctk.CTkLabel(win, text="⚙️ Configuration", font=("Segoe UI", 22, "bold"), text_color=self.text_main).pack(pady=(20, 20))
        ctk.CTkLabel(win, text="UI Theme:", text_color=self.text_muted).pack()
        theme_menu = ctk.CTkOptionMenu(win, values=["Dark", "Light"], command=lambda v: [self.apply_theme(v), self.save_current_state()])
        theme_menu.set(self.theme_mode)
        theme_menu.pack(pady=(5, 20))
        
        ctk.CTkLabel(win, text="AI Response Stream Delay (ms):", text_color=self.text_muted).pack()
        def update_speed_lbl(val): speed_val_lbl.configure(text=f"{int(val)} ms")
        def save_speed(val): self.token_speed = int(val); self.save_current_state()
        slider = ctk.CTkSlider(win, from_=0, to=100, command=update_speed_lbl)
        slider.set(self.token_speed)
        slider.pack(pady=10)
        speed_val_lbl = ctk.CTkLabel(win, text=f"{int(self.token_speed)} ms", font=("Segoe UI", 14, "bold"), text_color=self.accent)
        speed_val_lbl.pack(pady=(0, 20))
        slider.configure(command=lambda v: [update_speed_lbl(v), save_speed(v)])
        
        def nuke_history():
            if messagebox.askyesno("Confirm Data Wipe", "Delete all inquiry history?"):
                for f in os.listdir(HISTORY_DIR): os.remove(os.path.join(HISTORY_DIR, f))
                self.session_history = []
                self.save_current_state()
                self.start_new_session()
                self.update_sidebar_history()
        ctk.CTkButton(win, text="🧨 Purge Inquiry Log", fg_color="#e74c3c", hover_color="#c0392b", command=nuke_history).pack(pady=20)

    def load_save_data(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.user_name = d.get("user_name")
                    self.theme_mode = d.get("theme_mode", "Dark")
                    self.token_speed = d.get("token_speed", 30) 
                    self.session_history = d.get("history", [])
                    if self.session_history: self.current_session_id = self.session_history[0]['id']
            except: pass

    def save_current_state(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({"user_name": self.user_name, "theme_mode": self.theme_mode, "token_speed": self.token_speed, "history": self.session_history}, f)

app = SourceAgentWorkspace()
app.mainloop()
