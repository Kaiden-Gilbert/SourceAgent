import os, sys, threading, time, base64, math, uuid, json, shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage
import cv2

# --- PATH FIX FOR EXECUTABLES ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__)) if '__file__' in globals() else os.getcwd()

SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
ENV_FILE = os.path.join(BASE_DIR, ".env")

# Ensure base directories exist
for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

BG_DARK = "#050508"
BG_SURFACE = "#0f0f1a"
ACCENT = "#6366f1"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#64748b"

class SourceAgentWorkspace(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SourceAgent Pro Setup")
        self.geometry("1300x850")
        ctk.set_appearance_mode("Dark")
        
        self.cached_vectorstore = None
        self.attached_media_path = None
        self.user_name = None
        self.token_speed = 30 # Default retro typing speed
        self.current_session_id = str(uuid.uuid4())
        self.session_history = []
        
        self.load_save_data()
        
        # Check if setup is required
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
        api_key = os.environ.get("OPENROUTER_API_KEY")
        
        self.draw_dynamic_background()
        
        if not self.user_name or not api_key:
            self.show_installer_wizard()
        else:
            self.setup_ai_failover(api_key)
            self.show_cinematic_welcome()

    # ==========================================
    # STAGE 1: DYNAMIC BACKGROUND ANIMATION
    # ==========================================
    def draw_dynamic_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg="#020205")
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.orbs = [
            self.bg_canvas.create_oval(0,0,0,0, outline="", fill="#1e1b4b"), 
            self.bg_canvas.create_oval(0,0,0,0, outline="", fill="#312e81")
        ]
        self.anim_step = 0
        self.animate_bg()

    def animate_bg(self):
        if not self.winfo_exists(): return
        w, h = self.winfo_width(), self.winfo_height()
        if w > 100:
            self.anim_step += 0.012
            x1 = (math.sin(self.anim_step) * (w/3)) + (w/2)
            y1 = (math.cos(self.anim_step * 0.7) * (h/3)) + (h/2)
            self.bg_canvas.coords(self.orbs[0], x1-500, y1-500, x1+500, y1+500)
        self.bg_canvas.lower("all")
        self.after(40, self.animate_bg)

    # ==========================================
    # STAGE 2: INSTALLER WIZARD (OOBE)
    # ==========================================
    def show_installer_wizard(self):
        self.wizard_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.wizard_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Waving Title inside the Wizard
        self.title_frame = tk.Frame(self.wizard_frame, bg="#020205", width=600, height=100)
        self.title_frame.place(relx=0.5, rely=0.25, anchor="center")
        self.title_chars = []
        
        title_text = "SOURCEAGENT SETUP"
        start_x = 20
        for i, char in enumerate(title_text):
            lbl = tk.Label(self.title_frame, text=char, font=("Segoe UI", 32, "bold"), bg="#020205", fg=TEXT_MAIN)
            lbl.place(x=start_x + (i*30), y=50, anchor="center")
            self.title_chars.append((lbl, start_x + (i*30)))
            
        self.wave_step = 0
        self.is_waving = True
        self.animate_wave()
        
        # Setup Box
        box = ctk.CTkFrame(self.wizard_frame, fg_color=BG_SURFACE, corner_radius=20, border_width=1, border_color="#1a1a2e")
        box.place(relx=0.5, rely=0.6, anchor="center")
        
        ctk.CTkLabel(box, text="System Initialization", font=("Segoe UI", 20, "bold"), text_color=TEXT_MAIN).pack(pady=(30, 10), padx=40)
        ctk.CTkLabel(box, text="Please configure your core settings to continue.", text_color=TEXT_MUTED).pack(pady=(0, 20))
        
        self.name_e = ctk.CTkEntry(box, placeholder_text="Enter your display name...", width=320, height=45)
        self.name_e.pack(pady=10, padx=40)
        
        self.api_e = ctk.CTkEntry(box, placeholder_text="Paste your OpenRouter API Key...", width=320, height=45, show="*")
        self.api_e.pack(pady=10, padx=40)
        
        ctk.CTkButton(box, text="Finalize Installation", height=45, fg_color=ACCENT, font=("Segoe UI", 14, "bold"), command=self.run_installation).pack(pady=(20, 40))

    def animate_wave(self):
        if not self.is_waving: return
        self.wave_step += 0.15
        for i, (lbl, basex) in enumerate(self.title_chars):
            offset = math.sin(self.wave_step + i) * 10
            lbl.place(x=basex, y=50 + offset, anchor="center")
            color = ACCENT if math.sin(self.wave_step + i) > 0 else TEXT_MAIN
            lbl.config(fg=color)
        self.after(30, self.animate_wave)

    def run_installation(self):
        name = self.name_e.get().strip()
        api_key = self.api_e.get().strip()
        
        if not name or not api_key:
            messagebox.showwarning("Missing Data", "Please provide both your name and API key to initialize.")
            return
            
        # Write the .env file programmatically
        with open(ENV_FILE, "w") as f:
            f.write(f"OPENROUTER_API_KEY={api_key}\n")
            
        self.user_name = name
        self.save_current_state()
        
        self.is_waving = False
        self.wizard_frame.destroy()
        
        self.setup_ai_failover(api_key)
        self.show_cinematic_welcome()

    # ==========================================
    # STAGE 3: CINEMATIC TYPING WELCOME
    # ==========================================
    def show_cinematic_welcome(self):
        self.welcome_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.welcome_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.welcome_lbl = ctk.CTkLabel(self.welcome_frame, text="", font=("Segoe UI", 48, "bold"), text_color=TEXT_MAIN)
        self.welcome_lbl.place(relx=0.5, rely=0.5, anchor="center")
        
        self.full_welcome_text = f"Welcome online, {self.user_name}."
        self.type_index = 0
        self.type_text_effect()

    def type_text_effect(self):
        if self.type_index < len(self.full_welcome_text):
            current_text = self.welcome_lbl.cget("text")
            self.welcome_lbl.configure(text=current_text + self.full_welcome_text[self.type_index])
            self.type_index += 1
            delay = 40 if self.full_welcome_text[self.type_index-1] != " " else 100
            self.after(delay, self.type_text_effect)
        else:
            self.welcome_lbl.configure(text_color=ACCENT)
            self.after(1200, self.transition_to_workspace)

    def transition_to_workspace(self):
        self.welcome_frame.destroy()
        self.bg_canvas.destroy() # Clear background to save memory
        self.title("SourceAgent Pro")
        self.build_main_ui()

    # ==========================================
    # STAGE 4: WORKSPACE & AI ENGINE
    # ==========================================
    def setup_ai_failover(self, key):
        base = "https://openrouter.ai/api/v1"
        e_prim = ChatOpenAI(base_url=base, api_key=key, model="google/gemini-2.0-flash-lite-preview-02-05:free", streaming=True)
        e_back = ChatOpenAI(base_url=base, api_key=key, model="meta-llama/llama-3.2-11b-vision-instruct:free", streaming=True)
        self.editor_engine = e_prim.with_fallbacks([e_back])
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.load_local_vectorstore()

    def load_local_vectorstore(self):
        index_path = os.path.join(SOURCE_DIR, "faiss_index")
        if os.path.exists(index_path):
            try: self.cached_vectorstore = FAISS.load_local(index_path, self.embeddings, allow_dangerous_deserialization=True)
            except: pass

    def build_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=300, fg_color=BG_DARK, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="📚 SourceAgent", font=("Segoe UI", 22, "bold")).pack(pady=(30, 10), padx=20)
        
        # Source Tools
        ctk.CTkButton(self.sidebar, text="📄 Add Source Document", fg_color="#27ae60", hover_color="#2ecc71", command=self.add_source_document).pack(fill="x", padx=20, pady=(10, 5))
        self.source_count_lbl = ctk.CTkLabel(self.sidebar, text="0 Sources Loaded", font=("Segoe UI", 11), text_color=TEXT_MUTED)
        self.source_count_lbl.pack(pady=(0, 20))
        
        # Sessions
        ctk.CTkButton(self.sidebar, text="+ New Session", fg_color=ACCENT, command=self.start_new_session).pack(fill="x", padx=20, pady=10)
        self.history_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=400)
        self.history_scroll.pack(fill="x", padx=10, pady=10)
        
        # Chat Canvas
        self.chat_frame = ctk.CTkFrame(self, fg_color=BG_SURFACE, corner_radius=15, border_width=1, border_color="#1a1a2e")
        self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(0, weight=1); self.chat_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(self.chat_frame, state="disabled", font=("Segoe UI", 16), wrap="word", fg_color="transparent", spacing1=5, spacing3=5)
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Input Controller
        input_bar = ctk.CTkFrame(self.chat_frame, fg_color=BG_DARK, corner_radius=12)
        input_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        input_bar.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(input_bar, text="📸", width=40, font=("Segoe UI", 18), command=self.attach_media, fg_color="transparent", hover_color="#1a1a2e").grid(row=0, column=0, padx=10)
        self.user_input = ctk.CTkEntry(input_bar, placeholder_text="Ask about your docs or attached media...", height=50, fg_color="transparent", border_width=0, font=("Segoe UI", 14))
        self.user_input.grid(row=0, column=1, sticky="ew")
        self.user_input.bind("<Return>", lambda e: self.send_message())
        ctk.CTkButton(input_bar, text="Send", width=80, command=self.send_message).grid(row=0, column=2, padx=10)
        
        # Status Bar
        status_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        status_frame.grid(row=1, column=0, sticky="ew", padx=30)
        self.status_bar = ctk.CTkLabel(status_frame, text="🟢 Systems Online", font=("Segoe UI", 12), text_color=TEXT_MUTED)
        self.status_bar.pack(side="left")
        ctk.CTkButton(status_frame, text="⚙️ Settings", width=60, fg_color="transparent", hover_color="#1a1a2e", text_color=TEXT_MUTED, command=self.open_settings_menu).pack(side="right")
        
        self.update_sidebar_history()
        self.update_source_count()
        self.load_active_chat()

    # ==========================================
    # LOGIC HANDLING
    # ==========================================
    def add_source_document(self):
        fps = filedialog.askopenfilenames(filetypes=[("Documents", "*.pdf *.txt *.docx")])
        if fps:
            self.status_bar.configure(text="Ingesting Documents...", text_color="#f39c12")
            for fp in fps: shutil.copy(fp, SOURCE_DIR)
            threading.Thread(target=self.process_documents_to_vectorstore, daemon=True).start()

    def process_documents_to_vectorstore(self):
        docs = []
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
            self.cached_vectorstore.save_local(os.path.join(SOURCE_DIR, "faiss_index"))
            self.after(0, lambda: self.status_bar.configure(text="Sources Integrated.", text_color="#2ecc71"))
            self.after(0, self.update_source_count)

    def update_source_count(self):
        count = len([f for f in os.listdir(SOURCE_DIR) if f.endswith(('.pdf', '.txt', '.docx'))])
        if hasattr(self, 'source_count_lbl'):
            self.source_count_lbl.configure(text=f"{count} Sources Loaded", text_color="#2ecc71" if count > 0 else TEXT_MUTED)

    def attach_media(self):
        fp = filedialog.askopenfilename(filetypes=[("Media", "*.png;*.jpg;*.jpeg;*.mp4;*.avi")])
        if fp:
            self.attached_media_path = fp
            self.status_bar.configure(text=f"📎 Attached: {os.path.basename(fp)}", text_color=ACCENT)

    def send_message(self):
        q = self.user_input.get().strip()
        if not q: return
        self.user_input.delete(0, "end")
        
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"👤 You: {q}\n\n")
        self.chat_display.configure(state="disabled")
        self.append_to_chat_history(f"👤 You: {q}\n\n")
        
        threading.Thread(target=self.process_query, args=(q,), daemon=True).start()

    def process_query(self, query):
        try:
            self.after(0, lambda: self.status_bar.configure(text="🧠 Searching Sources...", text_color=ACCENT))
            context = ""
            if self.cached_vectorstore:
                retrieved_docs = self.cached_vectorstore.as_retriever(search_kwargs={"k": 3}).invoke(query)
                context = "\n".join([d.page_content for d in retrieved_docs])

            final_query = f"Use the following retrieved documents to answer the question.\n\nContext:\n{context}\n\nQuestion: {query}" if context else query

            messages = []
            if self.attached_media_path:
                with open(self.attached_media_path, "rb") as f: b64 = base64.b64encode(f.read()).decode('utf-8')
                self.attached_media_path = None
                messages.append(HumanMessage(content=[{"type": "text", "text": final_query}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]))
            else:
                messages.append(HumanMessage(content=final_query))

            self.after(0, lambda: self.status_bar.configure(text="🧠 Thinking...", text_color=ACCENT))
            self.after(0, lambda: self.chat_display.configure(state="normal"))
            self.after(0, lambda: self.chat_display.insert("end", "🤖 Agent: "))
            
            full_response = "🤖 Agent: "
            stream = self.editor_engine.stream(messages)
            
            for chunk in stream:
                full_response += chunk.content
                self.after(0, lambda c=chunk.content: self.chat_display.insert("end", c))
                if self.token_speed > 0: time.sleep(self.token_speed / 1000.0) 
            
            self.after(0, lambda: self.chat_display.insert("end", "\n\n"))
            self.after(0, lambda: self.chat_display.configure(state="disabled"))
            self.after(0, lambda: self.status_bar.configure(text="🟢 Systems Online", text_color=TEXT_MUTED))
            
            self.append_to_chat_history(full_response + "\n\n")
            
            if len(self.session_history) == 0 or self.session_history[0]['id'] != self.current_session_id:
                self.session_history.insert(0, {'id': self.current_session_id, 'title': query[:20] + "..." if len(query) > 20 else query})
                self.save_current_state()
                self.after(0, self.update_sidebar_history)

        except Exception as e: 
            self.after(0, lambda: messagebox.showerror("AI Error", str(e)))
            self.after(0, lambda: self.status_bar.configure(text="🟢 Systems Online", text_color=TEXT_MUTED))

    # --- UTILS ---
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
        win.title("Settings")
        win.geometry("400x300")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="⚙️ Settings", font=("Segoe UI", 22, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(win, text="Token Display Delay (ms):", text_color=TEXT_MUTED).pack()
        def update_speed_lbl(val): speed_val_lbl.configure(text=f"{int(val)} ms")
        def save_speed(val): 
            self.token_speed = int(val); self.save_current_state()
        slider = ctk.CTkSlider(win, from_=0, to=100, command=update_speed_lbl)
        slider.set(self.token_speed)
        slider.pack(pady=10)
        speed_val_lbl = ctk.CTkLabel(win, text=f"{int(self.token_speed)} ms", font=("Segoe UI", 14, "bold"), text_color=ACCENT)
        speed_val_lbl.pack()
        slider.configure(command=lambda v: [update_speed_lbl(v), save_speed(v)])

    def load_save_data(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    d = json.load(f)
                    self.user_name = d.get("user_name")
                    self.token_speed = d.get("token_speed", 30) # Restored default speed!
                    self.session_history = d.get("history", [])
                    if self.session_history: self.current_session_id = self.session_history[0]['id']
            except: pass

    def save_current_state(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({"user_name": self.user_name, "token_speed": self.token_speed, "history": self.session_history}, f)

app = SourceAgentWorkspace()
app.mainloop()
