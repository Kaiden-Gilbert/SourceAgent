import os, sys, threading, time, base64, math, uuid, json
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
from dotenv import load_dotenv
import cv2

# --- PATH FIX FOR COMPILED EXECUTABLES ---
if getattr(sys, 'frozen', False):
    # If running from the .exe, look in the folder holding the .exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If running from the terminal
    BASE_DIR = os.path.abspath(os.path.dirname(__file__)) if '__file__' in globals() else os.getcwd()

SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage")
ENV_FILE = os.path.join(BASE_DIR, ".env")

for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

load_dotenv(ENV_FILE)

BG_DARK = "#050508"
BG_SURFACE = "#0f0f1a"
ACCENT = "#6366f1"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#64748b"

class SourceAgentWorkspace(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SourceAgent Pro")
        self.geometry("1300x850")
        ctk.set_appearance_mode("Dark")
        
        self.cached_vectorstore = None
        self.cached_docs_hash = ""
        self.attached_media_path = None
        self.user_name = None
        self.token_speed = 0
        self.current_session_id = str(uuid.uuid4())
        self.session_history = []
        
        self.load_save_data()
        self.setup_ai_failover()
        
        if self.user_name: self.build_main_ui()
        else: self.show_onboarding()

    def show_onboarding(self):
        self.onboarding_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.onboarding_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        box = ctk.CTkFrame(self.onboarding_frame, fg_color=BG_SURFACE, corner_radius=20, border_width=1, border_color="#1a1a2e")
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="Initialize SourceAgent", font=("Segoe UI", 26, "bold"), text_color=ACCENT).pack(pady=(40, 20), padx=40)
        self.name_e = ctk.CTkEntry(box, placeholder_text="Identify yourself...", width=280, height=45)
        self.name_e.pack(pady=10, padx=40)
        ctk.CTkButton(box, text="Sync Identity", height=40, font=("Segoe UI", 14, "bold"), command=self.save_name_and_start).pack(pady=(20, 40))

    def save_name_and_start(self):
        name = self.name_e.get().strip()
        if name:
            self.user_name = name
            self.save_current_state()
            self.onboarding_frame.destroy()
            self.build_main_ui()

    def build_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=300, fg_color=BG_DARK, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="📚 SourceAgent", font=("Segoe UI", 22, "bold")).pack(pady=30, padx=20)
        ctk.CTkButton(self.sidebar, text="+ New Session", fg_color=ACCENT, command=self.start_new_session).pack(fill="x", padx=20, pady=10)
        
        self.history_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=300)
        self.history_scroll.pack(fill="x", padx=10)
        
        self.chat_frame = ctk.CTkFrame(self, fg_color=BG_SURFACE, corner_radius=15, border_width=1, border_color="#1a1a2e")
        self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(0, weight=1); self.chat_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(self.chat_frame, state="disabled", font=("Segoe UI", 16), wrap="word", fg_color="transparent", spacing1=5, spacing3=5)
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        input_bar = ctk.CTkFrame(self.chat_frame, fg_color=BG_DARK, corner_radius=12)
        input_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        input_bar.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(input_bar, text="📸", width=40, font=("Segoe UI", 18), command=self.attach_media, fg_color="transparent", hover_color="#1a1a2e").grid(row=0, column=0, padx=10)
        self.user_input = ctk.CTkEntry(input_bar, placeholder_text="Ask about your docs or attached media...", height=50, fg_color="transparent", border_width=0, font=("Segoe UI", 14))
        self.user_input.grid(row=0, column=1, sticky="ew")
        self.user_input.bind("<Return>", lambda e: self.send_message())
        
        ctk.CTkButton(input_bar, text="Send", width=80, command=self.send_message).grid(row=0, column=2, padx=10)
        
        status_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        status_frame.grid(row=1, column=0, sticky="ew", padx=30)
        self.status_bar = ctk.CTkLabel(status_frame, text="🟢 Ready", font=("Segoe UI", 12), text_color=TEXT_MUTED)
        self.status_bar.pack(side="left")
        ctk.CTkButton(status_frame, text="⚙️ Settings", width=60, fg_color="transparent", hover_color="#1a1a2e", text_color=TEXT_MUTED, command=self.open_settings_menu).pack(side="right")
        
        self.update_sidebar_history()

    def setup_ai_failover(self):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            messagebox.showwarning("Missing Credentials", f"Warning: Could not find OPENROUTER_API_KEY in:\n{ENV_FILE}\n\nPlease ensure your .env file is next to the executable.")
            key = "missing_key" # Prevent the hard crash
            
        base = "https://openrouter.ai/api/v1"
        r_prim = ChatOpenAI(base_url=base, api_key=key, model="mistralai/mistral-small-3.1-24b:free")
        r_back = ChatOpenAI(base_url=base, api_key=key, model="google/gemma-3-27b-it:free")
        self.researcher_engine = r_prim.with_fallbacks([r_back])
        
        e_prim = ChatOpenAI(base_url=base, api_key=key, model="google/gemini-2.0-flash-lite-preview-02-05:free", streaming=True)
        e_back = ChatOpenAI(base_url=base, api_key=key, model="meta-llama/llama-3.2-11b-vision-instruct:free", streaming=True)
        self.editor_engine = e_prim.with_fallbacks([e_back])
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

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
        threading.Thread(target=self.process_query, args=(q,), daemon=True).start()

    def process_query(self, query):
        try:
            self.after(0, lambda: self.status_bar.configure(text="🧠 Thinking...", text_color=ACCENT))
            media_msg = None
            if self.attached_media_path:
                path = self.attached_media_path
                self.attached_media_path = None
                with open(path, "rb") as f: b64 = base64.b64encode(f.read()).decode('utf-8')
                media_msg = HumanMessage(content=[{"type": "text", "text": query}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}])

            self.after(0, lambda: self.chat_display.configure(state="normal"))
            self.after(0, lambda: self.chat_display.insert("end", "🤖 Agent: "))
            
            stream = self.editor_engine.stream([media_msg] if media_msg else query)
            for chunk in stream:
                self.after(0, lambda c=chunk.content: self.chat_display.insert("end", c))
                if self.token_speed > 0: time.sleep(self.token_speed / 1000.0) 
            
            self.after(0, lambda: self.chat_display.insert("end", "\n\n"))
            self.after(0, lambda: self.chat_display.configure(state="disabled"))
            self.after(0, lambda: self.status_bar.configure(text="🟢 Ready", text_color=TEXT_MUTED))
        except Exception as e: self.after(0, lambda: messagebox.showerror("AI Error", str(e)))

    def open_settings_menu(self):
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("400x300")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="⚙️ Settings", font=("Segoe UI", 22, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(win, text="Token Display Delay (ms):", text_color=TEXT_MUTED).pack()
        
        def update_speed_lbl(val): speed_val_lbl.configure(text=f"{int(val)} ms")
        def save_speed(val): 
            self.token_speed = int(val)
            self.save_current_state()

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
                    self.token_speed = d.get("token_speed", 0)
                    self.session_history = d.get("history", [])
            except: pass

    def save_current_state(self):
        with open(SAVE_FILE, "w") as f:
            json.dump({"user_name": self.user_name, "token_speed": self.token_speed, "history": self.session_history}, f)

    def start_new_session(self):
        self.current_session_id = str(uuid.uuid4())
        self.chat_display.configure(state="normal"); self.chat_display.delete("1.0", "end"); self.chat_display.configure(state="disabled")

    def update_sidebar_history(self):
        for w in self.history_scroll.winfo_children(): w.destroy()
        for item in self.session_history: ctk.CTkButton(self.history_scroll, text=item['title'], fg_color="transparent").pack(fill="x")

app = SourceAgentWorkspace()
app.mainloop()
