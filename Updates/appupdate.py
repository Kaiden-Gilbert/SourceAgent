import os, sys, subprocess, time, uuid, threading, json, datetime, urllib.request
import tkinter as tk 

# --- BOOTSTRAP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe") if os.name == 'nt' else os.path.join(BASE_DIR, ".venv", "bin", "python")

if sys.executable.lower() != VENV_PYTHON.lower() and os.path.exists(VENV_PYTHON):
    subprocess.Popen([VENV_PYTHON] + sys.argv)
    sys.exit()

import shutil
import customtkinter as ctk
from tkinter import filedialog
from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage") 

for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# --- APP CONFIGURATION ---
APP_VERSION = "4.3" # PERFORMANCE & UI OPTIMIZATION UPDATE
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

# --- UI SETTINGS ---
BG_SIDEBAR = "#0b0b12"    
BG_SURFACE = "#161622"    
ACCENT_PRIMARY = "#6366f1" 
ACCENT_HOVER = "#4f46e5"  
TEXT_MAIN = "#f8fafc"     
TEXT_MUTED = "#94a3b8"    
FONT_MAIN = "Segoe UI"

def interpolate_color(color1, color2, factor):
    c1 = [int(color1[i:i+2], 16) for i in (1, 3, 5)]
    c2 = [int(color2[i:i+2], 16) for i in (1, 3, 5)]
    res = [int(c1[j] + (c2[j] - c1[j]) * factor) for j in range(3)]
    return f"#{res[0]:02x}{res[1]:02x}{res[2]:02x}"

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"SourceAgent Pro v{APP_VERSION} - Multi-Agent Edition")
        self.geometry("1300x850")
        
        self.vector_store = None # IN-MEMORY CACHE FOR EXTREME SPEED
        
        self.load_save_data()
        ctk.set_appearance_mode(self.app_theme)
        self.draw_gradient_background()

        if self.user_name: self.show_welcome_back_screen()
        else: self.show_boot_screen()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    # ==========================================
    # 0. UNIVERSAL NOTIFICATION SYSTEM
    # ==========================================
    def show_notification(self, message, is_alert=False, duration=None):
        if hasattr(self, 'active_notification') and self.active_notification.winfo_exists():
            self.active_notification.destroy()
            
        bg_color = "#e74c3c" if is_alert else ACCENT_PRIMARY
        self.active_notification = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=8, border_width=1, border_color="#ffffff")
        self.active_notification.place(relx=0.5, rely=0.06, anchor="center")
        
        ctk.CTkLabel(self.active_notification, text=message, font=(FONT_MAIN, 13, "bold"), text_color="white").pack(side="left", padx=(20, 10), pady=10)
        ctk.CTkButton(self.active_notification, text="Dismiss", width=60, fg_color="transparent", border_color="white", border_width=1, text_color="white", hover_color=ACCENT_HOVER, command=self.active_notification.destroy).pack(side="right", padx=(0, 20), pady=10)
        
        if duration:
            self.after(duration, lambda: self.active_notification.destroy() if self.active_notification.winfo_exists() else None)

    # ==========================================
    # 1. SETTINGS & CLOUD RADAR
    # ==========================================
    def open_settings_menu(self):
        self.settings_win = ctk.CTkToplevel(self)
        self.settings_win.title("Settings")
        self.settings_win.geometry("400x450")
        self.settings_win.attributes("-topmost", True)
        self.settings_win.grab_set()

        ctk.CTkLabel(self.settings_win, text="⚙️ Settings panel", font=(FONT_MAIN, 22, "bold")).pack(pady=(20, 30))
        ctk.CTkLabel(self.settings_win, text="Appearance Theme:", font=(FONT_MAIN, 14, "bold")).pack(anchor="w", padx=30)
        
        self.theme_menu = ctk.CTkOptionMenu(self.settings_win, values=["System", "Dark", "Light"], command=self.change_theme, fg_color=ACCENT_PRIMARY, button_color=ACCENT_HOVER)
        self.theme_menu.pack(fill="x", padx=30, pady=10)
        self.theme_menu.set(self.app_theme)

        ctk.CTkFrame(self.settings_win, height=1, fg_color="#333").pack(fill="x", padx=30, pady=25)
        ctk.CTkLabel(self.settings_win, text="System Updates:", font=(FONT_MAIN, 14, "bold")).pack(anchor="w", padx=30)
        
        ctk.CTkButton(self.settings_win, text="Check for Updates", fg_color="transparent", border_color=ACCENT_PRIMARY, border_width=1, hover_color="#222", command=lambda: self.check_for_updates(manual=True)).pack(fill="x", padx=30, pady=10)
        self.update_status_lbl = ctk.CTkLabel(self.settings_win, text=f"Current Build: v{APP_VERSION}", font=(FONT_MAIN, 12), text_color=TEXT_MUTED)
        self.update_status_lbl.pack(pady=5)

    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)
        self.app_theme = new_theme
        self.save_current_state()
        self._paint_gradient() 

    def check_for_updates(self, manual=False):
        try:
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + "version.json", headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as response:
                cloud_version = float(json.loads(response.read().decode('utf-8')).get("version", 0.0))
            if cloud_version > float(APP_VERSION):
                if manual and hasattr(self, 'update_status_lbl'): self.update_status_lbl.configure(text=f"Update v{cloud_version} found! Restart app.", text_color="#2ecc71")
                else: self.after(3000, lambda: self.show_notification(f"🚀 Update Available: v{cloud_version} found! Close and restart the app to install."))
            else:
                if manual and hasattr(self, 'update_status_lbl'): self.update_status_lbl.configure(text="You are on the latest version.", text_color=TEXT_MUTED)
        except Exception as e:
            if manual and hasattr(self, 'update_status_lbl'): self.update_status_lbl.configure(text="Cloud server unreachable.", text_color="#e74c3c")

    # ==========================================
    # 2. DATA PERSISTENCE
    # ==========================================
    def load_save_data(self):
        self.user_name, self.current_session_id, self.session_history, self.app_theme = None, str(uuid.uuid4()), [], "Dark"
        if os.path.exists(SAVE_FILE):
            try:
                data = json.load(open(SAVE_FILE, "r"))
                self.user_name, self.current_session_id, self.session_history, self.app_theme = data.get("user_name"), data.get("session_id", self.current_session_id), data.get("history_list", []), data.get("app_theme", "Dark")
            except: pass

    def save_current_state(self):
        json.dump({"user_name": self.user_name, "session_id": self.current_session_id, "history_list": self.session_history, "app_theme": self.app_theme}, open(SAVE_FILE, "w"), indent=4)

    def draw_gradient_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._paint_gradient)

    def _paint_gradient(self, event=None):
        self.bg_canvas.delete("gradient")
        h = self.winfo_height()
        if h == 0: return 
        top_color, mid_color, bot_color = ("#e0eafc", "#cfdef3", "#e0eafc") if ctk.get_appearance_mode() == "Light" else ("#0f0c29", "#302b63", "#24243e")
        for i in range(int(h/2)): self.bg_canvas.create_line(0, i, self.winfo_width(), i, fill=interpolate_color(top_color, mid_color, i / (h/2)), tags="gradient")
        for i in range(int(h/2), h): self.bg_canvas.create_line(0, i, self.winfo_width(), i, fill=interpolate_color(mid_color, bot_color, (i - h/2) / (h/2)), tags="gradient")
        self.bg_canvas.lower("all") 

    def show_boot_screen(self):
        self.boot_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.boot_frame.pack(fill="both", expand=True)
        box = ctk.CTkFrame(self.boot_frame, fg_color=BG_SURFACE, corner_radius=15, border_width=1, border_color="#333")
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="📚 SourceAgent", font=(FONT_MAIN, 28, "bold"), text_color=ACCENT_PRIMARY).pack(pady=(40, 10), padx=50)
        self.name_entry = ctk.CTkEntry(box, placeholder_text="Enter your name...", width=300, height=45)
        self.name_entry.pack(pady=30, padx=40)
        ctk.CTkButton(box, text="Launch Workspace", command=self.first_time_launch).pack(pady=(0, 40))

    def first_time_launch(self):
        if self.name_entry.get().strip(): 
            self.user_name = self.name_entry.get().strip()
            self.save_current_state()
        self.boot_frame.destroy()
        self.show_welcome_back_screen()

    def show_welcome_back_screen(self):
        self.welcome_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.welcome_frame.pack(fill="both", expand=True)
        self.welcome_label = ctk.CTkLabel(self.welcome_frame, text=f"Welcome back, {self.user_name}.", font=(FONT_MAIN, 36, "bold"), text_color="#0f0c29")
        self.welcome_label.place(relx=0.5, rely=0.5, anchor="center")
        self.after(200, self.animate_fade_in)

    def animate_fade_in(self, step=0):
        if step <= 30:
            self.welcome_label.configure(text_color=interpolate_color("#0f0c29", "#ffffff", step / 30))
            self.after(30, lambda: self.animate_fade_in(step + 1))
        else: self.after(1000, self.launch_workspace)

    def launch_workspace(self):
        if hasattr(self, 'welcome_frame'): self.welcome_frame.destroy()
        self.build_main_ui()
        threading.Thread(target=self.setup_ai, daemon=True).start()

    # ==========================================
    # 3. MAIN UI
    # ==========================================
    def build_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="📚 SourceAgent", font=(FONT_MAIN, 20, "bold")).pack(pady=(30, 20), padx=20, anchor="w")
        ctk.CTkButton(self.sidebar, text="+ New Session", fg_color=ACCENT_PRIMARY, command=self.start_new_session).pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="CHAT HISTORY", font=(FONT_MAIN, 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(20, 5))
        self.history_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=200); self.history_list.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="KNOWLEDGE BASE", font=(FONT_MAIN, 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(10, 5))
        self.source_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=150); self.source_list.pack(fill="x", padx=10, pady=5)
        
        # UI OPTIMIZATION: Dual Buttons for Upload & Manage
        btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="📄 Upload", command=self.upload_files, fg_color=BG_SURFACE, width=130).pack(side="left")
        ctk.CTkButton(btn_frame, text="🗑️ Manage", command=self.manage_sources, fg_color=BG_SURFACE, width=130).pack(side="right")
        
        ctk.CTkButton(self.sidebar, text="⚙️ Settings", command=self.open_settings_menu, fg_color="transparent", border_color="#333", border_width=1).pack(side="bottom", fill="x", padx=20, pady=20)

        self.chat_container = ctk.CTkFrame(self, fg_color="transparent"); self.chat_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_container.grid_rowconfigure(0, weight=1); self.chat_container.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(self.chat_container, state="disabled", font=(FONT_MAIN, 15), wrap="word", fg_color="transparent", spacing1=4, spacing3=4)
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 20))
        self.status_indicator = ctk.CTkLabel(self.chat_container, text="🟢 Initializing Multi-Agent Core...", text_color=TEXT_MUTED)
        self.status_indicator.grid(row=1, column=0, sticky="w", padx=15, pady=(0,5))

        self.input_wrapper = ctk.CTkFrame(self.chat_container, fg_color=BG_SURFACE, corner_radius=12, border_width=1, border_color="#333")
        self.input_wrapper.grid(row=2, column=0, sticky="ew"); self.input_wrapper.grid_columnconfigure(0, weight=1)
        
        self.user_input = ctk.CTkEntry(self.input_wrapper, placeholder_text="Ask the Agent Brain Trust...", height=55, border_width=0, fg_color="transparent")
        self.user_input.grid(row=0, column=0, sticky="ew", padx=15); self.user_input.bind("<Return>", lambda e: self.send_message())
        self.send_btn = ctk.CTkButton(self.input_wrapper, text="Send", width=80, command=self.send_message); self.send_btn.grid(row=0, column=1, padx=10)

        self.update_sidebar_history(); self.update_source_list(); self.load_active_chat_to_display()

    # ==========================================
    # 4. CHAT HISTORY & RENAMING LOGIC
    # ==========================================
    def format_ui_text(self, text):
        for rep in [("**", ""), ("* ", "• "), ("- ", "• "), ("### ", ""), ("## ", ""), ("# ", "")]: text = text.replace(*rep)
        return text

    def update_sidebar_history(self):
        for w in self.history_list.winfo_children(): w.destroy()
        for entry in reversed(self.session_history):
            frame = ctk.CTkFrame(self.history_list, fg_color="transparent")
            frame.pack(fill="x", pady=2)
            btn = ctk.CTkButton(frame, text=entry['title'], anchor="w", fg_color="transparent", text_color=TEXT_MAIN, hover_color="#222", command=lambda sid=entry['id']: self.switch_to_session(sid))
            btn.pack(side="left", fill="x", expand=True)
            edit_btn = ctk.CTkButton(frame, text="✏️", width=25, fg_color="transparent", hover_color="#333", command=lambda sid=entry['id']: self.rename_chat(sid))
            edit_btn.pack(side="right", padx=2)

    def rename_chat(self, sid):
        dialog = ctk.CTkInputDialog(text="Enter new chat name:", title="Rename Session")
        new_title = dialog.get_input()
        if new_title and new_title.strip():
            for entry in self.session_history:
                if entry['id'] == sid:
                    entry['title'] = new_title.strip()
                    break
            self.save_current_state()
            self.update_sidebar_history()
            self.show_notification(f"✏️ Chat renamed to '{new_title.strip()}'", duration=3000)

    def switch_to_session(self, sid):
        self.current_session_id = sid; self.save_current_state(); self.load_active_chat_to_display()

    def load_active_chat_to_display(self):
        self.chat_display.configure(state="normal"); self.chat_display.delete("1.0", "end")
        if os.path.exists(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json")):
            try:
                for msg in json.load(open(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json"), "r")):
                    self.chat_display.insert("end", f"{'👤 You' if msg['type'] == 'human' else '🤖 Agent'}:\n{self.format_ui_text(msg['data']['content'])}\n\n")
            except: pass
        self.chat_display.configure(state="disabled"); self.chat_display.see("end")

    def start_new_session(self):
        new_id, ts = str(uuid.uuid4()), datetime.datetime.now().strftime("%b %d, %H:%M")
        self.session_history.append({"id": new_id, "timestamp": ts, "title": f"Chat {ts}"})
        self.current_session_id = new_id; self.save_current_state(); self.update_sidebar_history(); self.load_active_chat_to_display()

    # ==========================================
    # 5. CORE AI & INDEXING CACHE (PERFORMANCE BOOST)
    # ==========================================
    def setup_ai(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.researcher_engine = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="google/gemma-3-27b-it:free", max_retries=2, timeout=45.0).with_fallbacks([ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="mistralai/mistral-small-3.1-24b:free", max_retries=2)])
        self.editor_engine = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="meta-llama/llama-3.3-70b-instruct:free", streaming=True, max_retries=2, timeout=60.0).with_fallbacks([ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="openrouter/auto", streaming=True, max_retries=2)])
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Build Vector DB exactly ONCE on boot for massive speed gains
        self.build_vector_db()

    def build_vector_db(self):
        self.after(0, lambda: self.status_indicator.configure(text="⚙️ Caching Knowledge Base into Memory..."))
        docs = []
        for f in os.listdir(SOURCE_DIR):
            path = os.path.join(SOURCE_DIR, f)
            try:
                if f.lower().endswith(".pdf"): docs.extend(PyMuPDFLoader(path).load())
                elif f.lower().endswith(".txt"): docs.extend(TextLoader(path, encoding="utf-8").load())
                elif f.lower().endswith(".docx"): docs.extend(Docx2txtLoader(path).load())
            except Exception as e: print(f"Skipping {f}: {e}")
        
        if docs:
            splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs)
            self.vector_store = FAISS.from_documents(splits, self.embeddings)
            self.after(0, lambda: self.status_indicator.configure(text="🟢 Database Cached & Agent Ready (Lightning Speed)"))
        else:
            self.vector_store = None
            self.after(0, lambda: self.status_indicator.configure(text="🟢 Dual-Agent Core Ready (No Files)"))

    def send_message(self):
        query = self.user_input.get().strip()
        if not query: return
        self.user_input.delete(0, "end"); self.user_input.configure(state="disabled"); self.send_btn.configure(state="disabled")
        self.append_chat_to_ui(f"👤 You:\n{query}\n\n")
        threading.Thread(target=self.run_agentic_workflow, args=(query,), daemon=True).start()

    def run_agentic_workflow(self, query):
        try:
            # OPTIMIZATION: Pull instantly from memory instead of reading files!
            context = "No documents provided."
            if self.vector_store:
                relevant = self.vector_store.as_retriever(search_kwargs={"k": 5}).invoke(query)
                context = "\n\n".join([d.page_content for d in relevant])

            history_obj = FileChatMessageHistory(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json"))
            history_text = "\n".join([f"{'User' if m.type == 'human' else 'Agent'}: {m.content}" for m in history_obj.messages[-4:]])

            self.after(0, lambda: self.status_indicator.configure(text="🧠 Researcher AI analyzing..."))
            try: researcher_draft = self.researcher_engine.invoke(f"You are a strict Researcher. User: {self.user_name}\nContext: {context}\nHistory: {history_text}\nQuestion: {query}\nCRITICAL: Answer ONLY using facts in the Context. If not there, reply EXACTLY: [NO_DATA].").content
            except Exception as e: researcher_draft = f"[NO_DATA] Error: {e}"

            self.after(0, lambda: self.status_indicator.configure(text="✨ Editor AI perfecting..."))
            self.after(0, lambda: self.chat_display.configure(state="normal")); self.after(0, lambda: self.chat_display.insert("end", "🤖 Agent:\n"))
            
            full_final_response = ""
            for chunk in self.editor_engine.stream(f"You are an Editor assisting {self.user_name}. Researcher Data: {researcher_draft}\nTask: 1. Format beautifully to answer '{query}'. 2. If data is [NO_DATA], state: '⚠️ *[ Note: Not in provided documents ]*' at the top, then answer using general knowledge."):
                full_final_response += chunk.content
                self.after(0, lambda t=self.format_ui_text(chunk.content): self.chat_display.insert("end", t)); self.after(0, lambda: self.chat_display.see("end"))

            history_obj.add_user_message(query); history_obj.add_ai_message(full_final_response)
            self.after(0, lambda: self.chat_display.insert("end", "\n\n")); self.after(0, lambda: self.chat_display.configure(state="disabled")); self.after(0, lambda: self.status_indicator.configure(text="🟢 Database Cached & Agent Ready"))

        except Exception as e:
            self.after(0, lambda: self.append_chat_to_ui(f"⚙️ Error: {str(e)}\n\n")); self.after(0, lambda: self.status_indicator.configure(text="❌ Agent Failure"))
            
        self.after(0, lambda: self.user_input.configure(state="normal")); self.after(0, lambda: self.send_btn.configure(state="normal")); self.after(0, lambda: self.user_input.focus_set())

    def append_chat_to_ui(self, text):
        self.chat_display.configure(state="normal"); self.chat_display.insert("end", text); self.chat_display.configure(state="disabled"); self.chat_display.see("end")

    # ==========================================
    # 6. WORKSPACE LOGIC & MASS DELETION UI
    # ==========================================
    def upload_files(self):
        if files := filedialog.askopenfilenames():
            self.status_indicator.configure(text="📥 Ingesting Files...")
            for f in files: shutil.copy(f, SOURCE_DIR)
            self.update_source_list()
            # Rebuild the database cache to include the new files
            threading.Thread(target=self.build_vector_db, daemon=True).start()

    def update_source_list(self):
        for w in self.source_list.winfo_children(): w.destroy()
        # Removed individual X buttons for cleaner UI
        for f in os.listdir(SOURCE_DIR): 
            ctk.CTkLabel(self.source_list, text=f"• {f}", font=(FONT_MAIN, 12)).pack(anchor="w", padx=5)

    def manage_sources(self):
        self.manage_win = ctk.CTkToplevel(self)
        self.manage_win.title("Manage Sources")
        self.manage_win.geometry("400x500")
        self.manage_win.attributes("-topmost", True)
        self.manage_win.grab_set()

        ctk.CTkLabel(self.manage_win, text="🗑️ Manage Knowledge Base", font=(FONT_MAIN, 20, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(self.manage_win, text="Select files to permanently remove from memory:", text_color=TEXT_MUTED).pack(pady=(0, 20))

        scroll = ctk.CTkScrollableFrame(self.manage_win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self.checkboxes = {}
        for f in os.listdir(SOURCE_DIR):
            var = tk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(scroll, text=f, variable=var, text_color=TEXT_MAIN, fg_color="#e74c3c", hover_color="#c0392b")
            cb.pack(anchor="w", pady=5)
            self.checkboxes[f] = var

        ctk.CTkButton(self.manage_win, text="Delete Selected", fg_color="#e74c3c", hover_color="#cYou have hit the nail on the head. As your "Knowledge Base" grows, the app starts to feel incredibly sluggish. 

**Here is exactly why it was slow:**
In version 4.2, every single time you hit "Send", the app would re-open your PDFs, re-read every single word, re-chop them into chunks, and re-embed them into the AI's math space. If you had 10 PDFs uploaded, it was reading all 10 of them from scratch *for every single question*.

**The v4.3 Optimization (The "Brain Cache"):**
We are introducing a **Vector Cache**. Now, the app only reads and embeds your files *once*. It saves that knowledge in its active memory. When you ask a second, third, or fourth question, it skips the reading phase entirely and instantly answers you. It will only re-read the files if it detects that you uploaded or deleted something!

**The v4.3 Bulk Deletion UI:**
I have completely removed the individual red "X" buttons. Instead, there is a slick new **"🗑️ Manage Sources"** button. Clicking it opens a beautiful popup window with checkboxes next to all your files, allowing you to bulk-delete multiple files at once. 

Here is your highly optimized **v4.3** code! Overwrite your GitHub `appupdate.py` file with this:

### **The Optimized Core: `appupdate.py` (v4.3)**

```python
import os, sys, subprocess, time, uuid, threading, json, datetime, urllib.request
import tkinter as tk 

# --- BOOTSTRAP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe") if os.name == 'nt' else os.path.join(BASE_DIR, ".venv", "bin", "python")

if sys.executable.lower() != VENV_PYTHON.lower() and os.path.exists(VENV_PYTHON):
    subprocess.Popen([VENV_PYTHON] + sys.argv)
    sys.exit()

import shutil
import customtkinter as ctk
from tkinter import filedialog
from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))
SOURCE_DIR = os.path.join(BASE_DIR, "source_docs")
SAVE_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_DIR = os.path.join(BASE_DIR, "chat_storage") 

for d in [SOURCE_DIR, HISTORY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# --- APP CONFIGURATION ---
APP_VERSION = "4.3" # Optimization & Bulk Delete Update
GITHUB_RAW_BASE_URL = "[https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/](https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/)"

# --- UI SETTINGS ---
BG_SIDEBAR = "#0b0b12"    
BG_SURFACE = "#161622"    
ACCENT_PRIMARY = "#6366f1" 
ACCENT_HOVER = "#4f46e5"  
TEXT_MAIN = "#f8fafc"     
TEXT_MUTED = "#94a3b8"    
FONT_MAIN = "Segoe UI"

def interpolate_color(color1, color2, factor):
    c1 = [int(color1[i:i+2], 16) for i in (1, 3, 5)]
    c2 = [int(color2[i:i+2], 16) for i in (1, 3, 5)]
    res = [int(c1[j] + (c2[j] - c1[j]) * factor) for j in range(3)]
    return f"#{res[0]:02x}{res[1]:02x}{res[2]:02x}"

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"SourceAgent Pro v{APP_VERSION} - Multi-Agent Edition")
        self.geometry("1300x850")
        
        # --- v4.3 OPTIMIZATION MEMORY ---
        self.cached_vectorstore = None
        self.cached_docs_hash = ""
        
        self.load_save_data()
        ctk.set_appearance_mode(self.app_theme)
        self.draw_gradient_background()

        if self.user_name: self.show_welcome_back_screen()
        else: self.show_boot_screen()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    # ==========================================
    # 0. UNIVERSAL NOTIFICATION SYSTEM
    # ==========================================
    def show_notification(self, message, is_alert=False, duration=None):
        if hasattr(self, 'active_notification') and self.active_notification.winfo_exists():
            self.active_notification.destroy()
            
        bg_color = "#e74c3c" if is_alert else ACCENT_PRIMARY
        self.active_notification = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=8, border_width=1, border_color="#ffffff")
        self.active_notification.place(relx=0.5, rely=0.06, anchor="center")
        
        ctk.CTkLabel(self.active_notification, text=message, font=(FONT_MAIN, 13, "bold"), text_color="white").pack(side="left", padx=(20, 10), pady=10)
        ctk.CTkButton(self.active_notification, text="Dismiss", width=60, fg_color="transparent", border_color="white", border_width=1, text_color="white", hover_color=ACCENT_HOVER, command=self.active_notification.destroy).pack(side="right", padx=(0, 20), pady=10)
        
        if duration:
            self.after(duration, lambda: self.active_notification.destroy() if self.active_notification.winfo_exists() else None)

    # ==========================================
    # 1. SETTINGS & CLOUD RADAR
    # ==========================================
    def open_settings_menu(self):
        self.settings_win = ctk.CTkToplevel(self)
        self.settings_win.title("Settings")
        self.settings_win.geometry("400x450")
        self.settings_win.attributes("-topmost", True)
        self.settings_win.grab_set()

        ctk.CTkLabel(self.settings_win, text="⚙️ Settings panel", font=(FONT_MAIN, 22, "bold")).pack(pady=(20, 30))
        ctk.CTkLabel(self.settings_win, text="Appearance Theme:", font=(FONT_MAIN, 14, "bold")).pack(anchor="w", padx=30)
        
        self.theme_menu = ctk.CTkOptionMenu(self.settings_win, values=["System", "Dark", "Light"], command=self.change_theme, fg_color=ACCENT_PRIMARY, button_color=ACCENT_HOVER)
        self.theme_menu.pack(fill="x", padx=30, pady=10)
        self.theme_menu.set(self.app_theme)

        ctk.CTkFrame(self.settings_win, height=1, fg_color="#333").pack(fill="x", padx=30, pady=25)
        ctk.CTkLabel(self.settings_win, text="System Updates:", font=(FONT_MAIN, 14, "bold")).pack(anchor="w", padx=30)
        
        ctk.CTkButton(self.settings_win, text="Check for Updates", fg_color="transparent", border_color=ACCENT_PRIMARY, border_width=1, hover_color="#222", command=lambda: self.check_for_updates(manual=True)).pack(fill="x", padx=30, pady=10)
        self.update_status_lbl = ctk.CTkLabel(self.settings_win, text=f"Current Build: v{APP_VERSION}", font=(FONT_MAIN, 12), text_color=TEXT_MUTED)
        self.update_status_lbl.pack(pady=5)

    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)
        self.app_theme = new_theme
        self.save_current_state()
        self._paint_gradient() 

    def check_for_updates(self, manual=False):
        try:
            req = urllib.request.Request(GITHUB_RAW_BASE_URL + "version.json", headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=5) as response:
                cloud_version = float(json.loads(response.read().decode('utf-8')).get("version", 0.0))
            if cloud_version > float(APP_VERSION):
                if manual and hasattr(self, 'update_status_lbl'): self.update_status_lbl.configure(text=f"Update v{cloud_version} found! Restart app.", text_color="#2ecc71")
                else: self.after(3000, lambda: self.show_notification(f"🚀 Update Available: v{cloud_version} found! Close and restart the app to install."))
            else:
                if manual and hasattr(self, 'update_status_lbl'): self.update_status_lbl.configure(text="You are on the latest version.", text_color=TEXT_MUTED)
        except Exception as e:
            if manual and hasattr(self, 'update_status_lbl'): self.update_status_lbl.configure(text="Cloud server unreachable.", text_color="#e74c3c")

    # ==========================================
    # 2. DATA PERSISTENCE
    # ==========================================
    def load_save_data(self):
        self.user_name, self.current_session_id, self.session_history, self.app_theme = None, str(uuid.uuid4()), [], "Dark"
        if os.path.exists(SAVE_FILE):
            try:
                data = json.load(open(SAVE_FILE, "r"))
                self.user_name, self.current_session_id, self.session_history, self.app_theme = data.get("user_name"), data.get("session_id", self.current_session_id), data.get("history_list", []), data.get("app_theme", "Dark")
            except: pass

    def save_current_state(self):
        json.dump({"user_name": self.user_name, "session_id": self.current_session_id, "history_list": self.session_history, "app_theme": self.app_theme}, open(SAVE_FILE, "w"), indent=4)

    def draw_gradient_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind("
