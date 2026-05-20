import os, threading, time, shutil, math, uuid, json, queue
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

# --- VAULT CONFIGURATION ---
BASE_DIR = globals().get('VAULT_DIR', os.getcwd())
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- THE COMPLIANCE DIRECTIVE (STRICT LOCKDOWN) ---
SYSTEM_PROMPT = """You are "Policy Advisor 2026", an enterprise compliance AI.
You have ONE job: Answer questions using ONLY the provided policy documents.

CRITICAL RULES:
1. NEVER invent, guess, or hallucinate information. If the answer is not in the text, you must say "I cannot find a policy regarding this."
2. Quote the exact policy name, section, and text verbatim.
3. Separate your plain English explanation from the quotes.
4. Keep your tone clinical, professional, and precise. 
5. Do not ramble. Do not output gibberish. Use clear, structured formatting."""

class PolicyAdvisorV17(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Policy Advisor 2026 | Enterprise Edition")
        self.geometry("1250x800")
        
        # --- THEME & CONFIG DEFAULT STATES ---
        self.theme_mode = "Dark"
        self.ai_model = "google/gemini-1.5-flash:free"
        self.ai_temp = 0.1 # Locked down to prevent hallucinations
        self.ai_max_tokens = 1024
        self.bg_deep = "#020617"
        self.bg_surface = "#0f172a"
        self.accent = "#3b82f6"
        
        # --- FAILSAFE QUEUE SYSTEM ---
        self.text_queue = queue.Queue()
        
        self.load_settings()
        ctk.set_appearance_mode(self.theme_mode)
        
        # Initialize UI and Background
        self.draw_kinetic_background()
        self.setup_ui()
        
        # Initialize AI
        load_dotenv(ENV_FILE)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = None
        self.load_db()
        self.build_ai_engine()
        
        # Start the thread-safe UI updater
        self.process_queue()

    # ==========================================
    # KINETIC VISUAL ENGINE
    # ==========================================
    def draw_kinetic_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg=self.bg_deep)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.orbs = [
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#1e3a8a"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#172554"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", fill="#0f172a")
        ]
        self.anim_step = 0
        self.animate_bg()

    def animate_bg(self):
        if not hasattr(self, 'bg_canvas') or not self.bg_canvas.winfo_exists(): return
            
        w, h = self.winfo_width(), self.winfo_height()
        if w > 100:
            self.anim_step += 0.015 
            x1 = (math.sin(self.anim_step) * (w/3)) + (w/2)
            y1 = (math.cos(self.anim_step * 0.7) * (h/3)) + (h/2)
            self.bg_canvas.coords(self.orbs[0], x1-700, y1-700, x1+700, y1+700)
            
            x2 = (math.cos(self.anim_step * 0.5) * (w/4)) + (w/2)
            y2 = (math.sin(self.anim_step * 0.8) * (h/4)) + (h/2)
            self.bg_canvas.coords(self.orbs[1], x2-500, y2-500, x2+500, y2+500)

            x3 = (math.sin(self.anim_step * 1.2) * (w/5)) + (w/1.5)
            y3 = (math.cos(self.anim_step * 0.4) * (h/4)) + (h/1.5)
            self.bg_canvas.coords(self.orbs[2], x3-600, y3-600, x3+600, y3+600)
            
        self.bg_canvas.lower("all")
        self.after(35, self.animate_bg)

    def fade_in_window(self, window, target_alpha=1.0):
        alpha = window.attributes("-alpha")
        if alpha < target_alpha:
            window.attributes("-alpha", alpha + 0.08)
            self.after(20, lambda: self.fade_in_window(window, target_alpha))

    # ==========================================
    # CORE INTERFACE
    # ==========================================
    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=280, fg_color="transparent")
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        header_box = ctk.CTkFrame(self.sidebar, fg_color=self.bg_surface, corner_radius=12)
        header_box.pack(fill="x", pady=10)
        ctk.CTkLabel(header_box, text="🏛️ Policy Advisor", font=("Segoe UI", 20, "bold")).pack(pady=20)
        
        # Action Center
        tools_box = ctk.CTkFrame(self.sidebar, fg_color=self.bg_surface, corner_radius=12)
        tools_box.pack(fill="x", pady=10)
        ctk.CTkButton(tools_box, text="📁 Upload Policy Docs", fg_color="#0ea5e9", command=self.add_docs).pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkButton(tools_box, text="🗄️ Database Manager", fg_color="#334155", command=self.open_manager).pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(tools_box, text="⚙️ Advanced Settings", fg_color="#334155", command=self.open_settings).pack(fill="x", padx=15, pady=(5, 15))
        
        # Chat Actions
        chat_box = ctk.CTkFrame(self.sidebar, fg_color=self.bg_surface, corner_radius=12)
        chat_box.pack(fill="x", pady=10)
        ctk.CTkButton(chat_box, text="💾 Export Audit Log", fg_color="#475569", command=self.export_chat).pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkButton(chat_box, text="🗑️ Clear Session", fg_color="#ef4444", hover_color="#dc2626", command=self.clear_chat).pack(fill="x", padx=15, pady=(5, 15))

        self.status_lbl = ctk.CTkLabel(self.sidebar, text="● Engine Online", text_color="#10b981", font=("Segoe UI", 12, "bold"))
        self.status_lbl.pack(side="bottom", pady=20)

        # Main Workspace
        work_area = ctk.CTkFrame(self, fg_color=self.bg_surface, corner_radius=15)
        work_area.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        work_area.grid_rowconfigure(0, weight=1); work_area.grid_columnconfigure(0, weight=1)

        self.chat = ctk.CTkTextbox(work_area, font=("Segoe UI", 15), fg_color="transparent", spacing1=8, spacing3=8)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.chat.insert("1.0", "SYSTEM: Secure connection established. Strict Compliance Protocol enabled.\n\n")
        self.chat.configure(state="disabled")
        
        input_bar = ctk.CTkFrame(work_area, fg_color="#1e293b", corner_radius=10)
        input_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        input_bar.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(input_bar, height=50, placeholder_text="Enter policy or compliance question...", fg_color="transparent", border_width=0, font=("Segoe UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=10)
        self.entry.bind("<Return>", lambda e: self.send())
        
        ctk.CTkButton(input_bar, text="Submit", width=100, height=40, font=("Segoe UI", 14, "bold"), fg_color=self.accent, command=self.send).grid(row=0, column=1, padx=10, pady=5)

    # ==========================================
    # FAILSAFE AI ARCHITECTURE (STRICT)
    # ==========================================
    def build_ai_engine(self):
        if not self.api_key: return
        try:
            self.llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1", 
                api_key=self.api_key, 
                model=self.ai_model,
                temperature=self.ai_temp,
                max_tokens=self.ai_max_tokens,
                top_p=0.85, # The mathematical filter that stops word salad
                streaming=True
            )
        except Exception as e:
            self.safe_ui_update(f"\n[ENGINE BUILD ERROR: {str(e)}]\n")

    def process_queue(self):
        try:
            while True:
                chunk = self.text_queue.get_nowait()
                self.chat.configure(state="normal")
                self.chat.insert("end", chunk)
                self.chat.see("end")
                self.chat.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(50, self.process_queue)

    def safe_ui_update(self, text):
        self.text_queue.put(text)

    def send(self):
        q = self.entry.get().strip()
        if not q: return
        self.entry.delete(0, "end")
        self.safe_ui_update(f"\nUSER: {q}\n\nADVISOR: ")
        self.status_lbl.configure(text="● Auditing Database...", text_color="#f59e0b")
        threading.Thread(target=self.generate_response, args=(q,), daemon=True).start()

    def generate_response(self, q):
        try:
            context = ""
            if self.db:
                docs = self.db.as_retriever(search_kwargs={"k": 5}).invoke(q)
                context = "\n".join([d.page_content for d in docs])
            
            msgs = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=f"Context:\n{context}\n\nInquiry: {q}")]
            
            for chunk in self.llm.stream(msgs):
                self.safe_ui_update(chunk.content)
            
            self.safe_ui_update("\n\n---\n")
            self.after(0, lambda: self.status_lbl.configure(text="● Engine Online", text_color="#10b981"))
            
        except Exception as e:
            self.safe_ui_update(f"\n[CRITICAL ERROR: {str(e)}]\nPlease check your API Key and Model Settings.\n\n---\n")
            self.after(0, lambda: self.status_lbl.configure(text="● Engine Error", text_color="#ef4444"))

    # ==========================================
    # DATABASE & SETTINGS
    # ==========================================
    def load_db(self):
        index = os.path.join(SOURCE_DIR, "faiss_index")
        self.db = FAISS.load_local(index, self.embeddings, allow_dangerous_deserialization=True) if os.path.exists(index) else None

    def add_docs(self):
        files = filedialog.askopenfilenames(filetypes=[("Documents", "*.pdf *.txt")])
        if not files: return
        self.status_lbl.configure(text="● Indexing...", text_color="#3b82f6")
        for f in files: shutil.copy(f, SOURCE_DIR)
        threading.Thread(target=self.rebuild_db, daemon=True).start()

    def rebuild_db(self):
        docs = []
        for f in os.listdir(SOURCE_DIR):
            if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(os.path.join(SOURCE_DIR, f)).load())
        if docs:
            self.db = FAISS.from_documents(RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs), self.embeddings)
            self.db.save_local(os.path.join(SOURCE_DIR, "faiss_index"))
        self.after(0, lambda: self.status_lbl.configure(text="● Engine Online", text_color="#10b981"))

    def clear_chat(self):
        self.chat.configure(state="normal"); self.chat.delete("1.0", "end"); self.chat.configure(state="disabled")

    def export_chat(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(self.chat.get("1.0", "end"))

    def open_manager(self):
        messagebox.showinfo("Database Config", f"Active Indexed Policies: {len(os.listdir(SOURCE_DIR))}")

    # --- ADVANCED AI SETTINGS PANEL ---
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Advanced Configuration")
        win.geometry("450x550")
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0) 
        win.configure(fg_color=self.bg_surface)
        
        self.fade_in_window(win)
        ctk.CTkLabel(win, text="Engine Configuration", font=("Segoe UI", 22, "bold")).pack(pady=(20, 20))
        
        ctk.CTkLabel(win, text="AI Core Model:", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        models = ["google/gemini-1.5-flash:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-lite-preview-02-05:free"]
        model_menu = ctk.CTkOptionMenu(win, values=models, width=370)
        model_menu.set(self.ai_model)
        model_menu.pack(pady=(5, 20))
        
        # LOCKED DOWN TEMPERATURE SLIDER
        ctk.CTkLabel(win, text="Creativity (Locked Max 0.7):", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        temp_val = ctk.CTkLabel(win, text=str(self.ai_temp), font=("Segoe UI", 12, "bold"), text_color=self.accent)
        temp_val.pack()
        temp_slider = ctk.CTkSlider(win, from_=0.0, to=0.7, number_of_steps=14, width=370)
        temp_slider.set(self.ai_temp)
        temp_slider.pack(pady=(5, 20))
        def update_temp(v): temp_val.configure(text=f"{v:.2f}")
        temp_slider.configure(command=update_temp)
        
        ctk.CTkLabel(win, text="Response Length (Max Tokens):", font=("Segoe UI", 12)).pack(anchor="w", padx=40)
        tok_val = ctk.CTkLabel(win, text=str(self.ai_max_tokens), font=("Segoe UI", 12, "bold"), text_color=self.accent)
        tok_val.pack()
        tok_slider = ctk.CTkSlider(win, from_=256, to=4096, number_of_steps=15, width=370)
        tok_slider.set(self.ai_max_tokens)
        tok_slider.pack(pady=(5, 20))
        def update_tok(v): tok_val.configure(text=f"{int(v)}")
        tok_slider.configure(command=update_tok)

        def apply_changes():
            self.ai_model = model_menu.get()
            self.ai_temp = float(temp_slider.get())
            self.ai_max_tokens = int(tok_slider.get())
            self.save_settings()
            self.build_ai_engine() 
            win.destroy()
            
        ctk.CTkButton(win, text="Apply & Reboot Engine", fg_color=self.accent, height=40, font=("Segoe UI", 14, "bold"), command=apply_changes).pack(pady=(20, 0))

    def load_settings(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.ai_model = d.get("ai_model", "google/gemini-1.5-flash:free")
                    self.ai_temp = d.get("ai_temp", 0.1) # Forced low default
                    self.ai_max_tokens = d.get("ai_max_tokens", 1024)
            except: pass

    def save_settings(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({"ai_model": self.ai_model, "ai_temp": self.ai_temp, "ai_max_tokens": self.ai_max_tokens}, f)

if __name__ == "__main__":
    app = PolicyAdvisorV17()
    app.mainloop()
