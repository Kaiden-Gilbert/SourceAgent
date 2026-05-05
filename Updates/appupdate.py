import os, sys, subprocess, time, uuid, threading, json, datetime, urllib.request, math
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
APP_VERSION = "4.4" # Cinematic Animated UI Update
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Kaiden-Gilbert/SourceAgent/main/Updates/"

# --- UI SETTINGS ---
BG_SIDEBAR = "#09090e"    
BG_SURFACE = "#12121c"    
ACCENT_PRIMARY = "#6366f1" 
ACCENT_HOVER = "#4f46e5"  
TEXT_MAIN = "#f8fafc"     
TEXT_MUTED = "#94a3b8"    
FONT_MAIN = "Segoe UI"

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"SourceAgent Pro v{APP_VERSION} - Cinematic Edition")
        self.geometry("1300x850")
        
        self.cached_vectorstore = None
        self.cached_docs_hash = ""
        
        self.load_save_data()
        ctk.set_appearance_mode(self.app_theme)
        
        # Initialize the Animated Nebula Background
        self.draw_dynamic_background()

        if self.user_name: self.show_welcome_back_screen()
        else: self.show_boot_screen()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    # ==========================================
    # 0. ANIMATED NEBULA BACKGROUND ENGINE
    # ==========================================
    def draw_dynamic_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Create three invisible floating orbs
        self.orbs = [
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", tags="orb"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", tags="orb"),
            self.bg_canvas.create_oval(0, 0, 0, 0, outline="", tags="orb")
        ]
        
        self.update_bg_theme()
        self.anim_step = 0
        self.animate_bg()

    def update_bg_theme(self):
        is_dark = ctk.get_appearance_mode() == "Dark"
        self.bg_canvas.configure(bg="#050509" if is_dark else "#f0f4f8")
        colors = ["#1e1b4b", "#312e81", "#171033"] if is_dark else ["#e0e7ff", "#c7d2fe", "#dbeafe"]
        for i, c in enumerate(colors):
            self.bg_canvas.itemconfig(self.orbs[i], fill=c)

    def animate_bg(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w > 100 and h > 100:
            self.anim_step += 0.015  # Speed of the animation
            
            # Math to calculate smooth, drifting elliptical orbits
            x1 = (math.sin(self.anim_step) * (w/3)) + (w/2)
            y1 = (math.cos(self.anim_step * 0.8) * (h/3)) + (h/2)
            self.bg_canvas.coords(self.orbs[0], x1-400, y1-400, x1+400, y1+400)

            x2 = (math.cos(self.anim_step * 1.2) * (w/4)) + (w/2)
            y2 = (math.sin(self.anim_step * 0.9) * (h/4)) + (h/2)
            self.bg_canvas.coords(self.orbs[1], x2-300, y2-300, x2+300, y2+300)

            x3 = (math.sin(self.anim_step * 0.5 + 2) * (w/2.5)) + (w/2)
            y3 = (math.cos(self.anim_step * 1.1 + 1) * (h/2.5)) + (h/2)
            self.bg_canvas.coords(self.orbs[2], x3-500, y3-500, x3+500, y3+500)

        self.bg_canvas.lower("all")
        self.after(40, self.animate_bg) # 25 FPS refresh rate

    # ==========================================
    # 1. UNIVERSAL NOTIFICATION SYSTEM
    # ==========================================
    def show_notification(self, message, is_alert=False, duration=None):
        if hasattr(self, 'active_notification') and self.active_notification.winfo_exists():
            self.active_notification.destroy()
            
        bg_color = "#e74c3c" if is_alert else ACCENT_PRIMARY
        self.active_notification = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=12, border_width=1, border_color="#ffffff")
        self.active_notification.place(relx=0.5, rely=0.06, anchor="center")
        
        ctk.CTkLabel(self.active_notification, text=message, font=(FONT_MAIN, 13, "bold"), text_color="white").pack(side="left", padx=(20, 10), pady=12)
        ctk.CTkButton(self.active_notification, text="Dismiss", width=60, fg_color="transparent", border_color="white", border_width=1, text_color="white", hover_color=ACCENT_HOVER, command=self.active_notification.destroy).pack(side="right", padx=(0, 20), pady=12)
        
        if duration:
            self.after(duration, lambda: self.active_notification.destroy() if self.active_notification.winfo_exists() else None)

    # ==========================================
    # 2. SETTINGS & CLOUD RADAR
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
        self.update_bg_theme() # Instantly swap the nebula colors

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
    # 3. DATA PERSISTENCE & BOOT SCREENS
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

    def show_boot_screen(self):
        self.boot_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.boot_frame.pack(fill="both", expand=True)
        box = ctk.CTkFrame(self.boot_frame, fg_color=BG_SURFACE, corner_radius=20, border_width=1, border_color="#333")
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="📚 SourceAgent", font=(FONT_MAIN, 32, "bold"), text_color=ACCENT_PRIMARY).pack(pady=(50, 10), padx=60)
        self.name_entry = ctk.CTkEntry(box, placeholder_text="Enter your name...", width=320, height=50, corner_radius=10)
        self.name_entry.pack(pady=35, padx=50)
        ctk.CTkButton(box, text="Launch Workspace", height=45, corner_radius=10, command=self.first_time_launch).pack(pady=(0, 50))

    def first_time_launch(self):
        if self.name_entry.get().strip(): 
            self.user_name = self.name_entry.get().strip()
            self.save_current_state()
        self.boot_frame.destroy()
        self.show_welcome_back_screen()

    def show_welcome_back_screen(self):
        self.welcome_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.welcome_frame.pack(fill="both", expand=True)
        
        self.welcome_label = ctk.CTkLabel(self.welcome_frame, text=f"Welcome back, {self.user_name}.", font=(FONT_MAIN, 42, "bold"), text_color="#ffffff")
        self.welcome_label.place(relx=0.5, rely=0.5, anchor="center")
        self.after(1200, self.launch_workspace)

    def launch_workspace(self):
        if hasattr(self, 'welcome_frame'): self.welcome_frame.destroy()
        self.build_main_ui()
        threading.Thread(target=self.setup_ai, daemon=True).start()

    # ==========================================
    # 4. MAIN UI (GLASSMORPHISM STYLING)
    # ==========================================
    def build_main_ui(self):
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=BG_SIDEBAR, border_width=1, border_color="#1a1a24")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="📚 SourceAgent", font=(FONT_MAIN, 22, "bold")).pack(pady=(35, 25), padx=20, anchor="w")
        ctk.CTkButton(self.sidebar, text="+ New Session", fg_color=ACCENT_PRIMARY, height=40, corner_radius=8, command=self.start_new_session).pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="CHAT HISTORY", font=(FONT_MAIN, 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(25, 5))
        self.history_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=220); self.history_list.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="KNOWLEDGE BASE", font=(FONT_MAIN, 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(15, 5))
        self.source_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=130); self.source_list.pack(fill="x", padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="📄 Upload", width=125, height=35, command=self.upload_files, fg_color=BG_SURFACE, border_width=1, border_color="#333").pack(side="left", expand=True)
        ctk.CTkButton(btn_frame, text="🗑️ Manage", width=125, height=35, command=self.open_manage_sources_menu, fg_color="transparent", hover_color="#333", border_width=1, border_color="#e74c3c", text_color="#e74c3c").pack(side="right", expand=True)

        ctk.CTkButton(self.sidebar, text="⚙️ Settings", command=self.open_settings_menu, fg_color="transparent", border_color="#333", border_width=1).pack(side="bottom", fill="x", padx=20, pady=20)

        # Faux-Glass Container for Chat
        self.chat_container = ctk.CTkFrame(self, fg_color=BG_SURFACE, corner_radius=15, border_width=1, border_color="#2a2a36")
        self.chat_container.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
        self.chat_container.grid_rowconfigure(0, weight=1); self.chat_container.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(self.chat_container, state="disabled", font=(FONT_MAIN, 16), wrap="word", fg_color="transparent", spacing1=6, spacing3=6)
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=15, pady=(15, 20))
        
        self.status_indicator = ctk.CTkLabel(self.chat_container, text="🟢 Initializing Multi-Agent Core...", text_color=TEXT_MUTED, font=(FONT_MAIN, 12, "italic"))
        self.status_indicator.grid(row=1, column=0, sticky="w", padx=20, pady=(0,8))

        self.input_wrapper = ctk.CTkFrame(self.chat_container, fg_color="#0b0b12", corner_radius=12, border_width=1, border_color="#333")
        self.input_wrapper.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15)); self.input_wrapper.grid_columnconfigure(0, weight=1)
        
        self.user_input = ctk.CTkEntry(self.input_wrapper, placeholder_text="Ask the Agent Brain Trust...", height=60, border_width=0, fg_color="transparent", font=(FONT_MAIN, 15))
        self.user_input.grid(row=0, column=0, sticky="ew", padx=15); self.user_input.bind("<Return>", lambda e: self.send_message())
        self.send_btn = ctk.CTkButton(self.input_wrapper, text="Send", width=90, height=40, corner_radius=8, command=self.send_message); self.send_btn.grid(row=0, column=1, padx=10)

        self.update_sidebar_history(); self.update_source_list(); self.load_active_chat_to_display()

    # ==========================================
    # 5. CHAT HISTORY LOGIC
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
            ctk.CTkButton(frame, text="✏️", width=25, fg_color="transparent", hover_color="#333", command=lambda sid=entry['id']: self.rename_chat(sid)).pack(side="right", padx=2)

    def rename_chat(self, sid):
        if new_title := ctk.CTkInputDialog(text="Enter new chat name:", title="Rename Session").get_input():
            for entry in self.session_history:
                if entry['id'] == sid: entry['title'] = new_title.strip(); break
            self.save_current_state(); self.update_sidebar_history(); self.show_notification(f"✏️ Chat renamed to '{new_title.strip()}'", duration=3000)

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
    # 6. VECTOR CACHE & AI CORE
    # ==========================================
    def setup_ai(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.researcher_engine = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="google/gemma-3-27b-it:free", max_retries=2, timeout=45.0).with_fallbacks([ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="mistralai/mistral-small-3.1-24b:free", max_retries=2)])
        self.editor_engine = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="meta-llama/llama-3.3-70b-instruct:free", streaming=True, max_retries=2, timeout=60.0).with_fallbacks([ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="openrouter/auto", streaming=True, max_retries=2)])
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.after(0, lambda: self.status_indicator.configure(text="🟢 Dual-Agent Core Ready"))

    def get_cached_vectorstore(self):
        current_hash = str(sorted(os.listdir(SOURCE_DIR)))
        if self.cached_vectorstore is not None and self.cached_docs_hash == current_hash:
            return self.cached_vectorstore

        self.after(0, lambda: self.status_indicator.configure(text="🔄 Analyzing Knowledge Base into Memory..."))
        docs = []
        for f in os.listdir(SOURCE_DIR):
            path = os.path.join(SOURCE_DIR, f)
            try:
                if f.lower().endswith(".pdf"): docs.extend(PyMuPDFLoader(path).load())
                elif f.lower().endswith(".txt"): docs.extend(TextLoader(path, encoding="utf-8").load())
                elif f.lower().endswith(".docx"): docs.extend(Docx2txtLoader(path).load())
            except Exception as e: print(f"Failed to load {f}: {e}")
        
        if docs:
            splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs)
            self.cached_vectorstore = FAISS.from_documents(splits, self.embeddings)
            self.cached_docs_hash = current_hash
            return self.cached_vectorstore
        
        self.cached_vectorstore = None
        self.cached_docs_hash = current_hash
        return None

    def send_message(self):
        query = self.user_input.get().strip()
        if not query: return
        self.user_input.delete(0, "end"); self.user_input.configure(state="disabled"); self.send_btn.configure(state="disabled")
        self.append_chat_to_ui(f"👤 You:\n{query}\n\n")
        threading.Thread(target=self.run_agentic_workflow, args=(query,), daemon=True).start()

    def run_agentic_workflow(self, query):
        try:
            vs = self.get_cached_vectorstore()
            context = "\n\n".join([d.page_content for d in vs.as_retriever(search_kwargs={"k": 5}).invoke(query)]) if vs else "No documents provided."

            history_obj = FileChatMessageHistory(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json"))
            history_text = "\n".join([f"{'User' if m.type == 'human' else 'Agent'}: {m.content}" for m in history_obj.messages[-4:]])

            self.after(0, lambda: self.status_indicator.configure(text="🧠 Researcher AI pulling facts..."))
            try: researcher_draft = self.researcher_engine.invoke(f"You are a strict Researcher. User: {self.user_name}\nContext: {context}\nHistory: {history_text}\nQuestion: {query}\nCRITICAL: Answer ONLY using facts in the Context. If not there, reply EXACTLY: [NO_DATA].").content
            except Exception as e: researcher_draft = f"[NO_DATA] Error: {e}"

            self.after(0, lambda: self.status_indicator.configure(text="✨ Editor AI streaming response..."))
            self.after(0, lambda: self.chat_display.configure(state="normal")); self.after(0, lambda: self.chat_display.insert("end", "🤖 Agent:\n"))
            
            full_final_response = ""
            for chunk in self.editor_engine.stream(f"You are an Editor assisting {self.user_name}. Researcher Data: {researcher_draft}\nTask: 1. Format beautifully to answer '{query}'. 2. If data is [NO_DATA], state: '⚠️ *[ Note: Not in provided documents ]*' at the top, then answer using general knowledge."):
                full_final_response += chunk.content
                self.after(0, lambda t=self.format_ui_text(chunk.content): self.chat_display.insert("end", t)); self.after(0, lambda: self.chat_display.see("end"))

            history_obj.add_user_message(query); history_obj.add_ai_message(full_final_response)
            self.after(0, lambda: self.chat_display.insert("end", "\n\n")); self.after(0, lambda: self.chat_display.configure(state="disabled")); self.after(0, lambda: self.status_indicator.configure(text="🟢 Dual-Agent Core Ready"))

        except Exception as e:
            self.after(0, lambda: self.append_chat_to_ui(f"⚙️ Error: {str(e)}\n\n")); self.after(0, lambda: self.status_indicator.configure(text="❌ Agent Failure"))
            
        self.after(0, lambda: self.user_input.configure(state="normal")); self.after(0, lambda: self.send_btn.configure(state="normal")); self.after(0, lambda: self.user_input.focus_set())

    def append_chat_to_ui(self, text):
        self.chat_display.configure(state="normal"); self.chat_display.insert("end", text); self.chat_display.configure(state="disabled"); self.chat_display.see("end")

    # ==========================================
    # 7. WORKSPACE UI
    # ==========================================
    def upload_files(self):
        if files := filedialog.askopenfilenames():
            self.status_indicator.configure(text="📥 Ingesting Files...")
            for f in files: shutil.copy(f, SOURCE_DIR)
            self.update_source_list()
            self.cached_vectorstore = None
            self.status_indicator.configure(text="🟢 Knowledge Base Updated")

    def update_source_list(self):
        for w in self.source_list.winfo_children(): w.destroy()
        for f in os.listdir(SOURCE_DIR): ctk.CTkLabel(self.source_list, text=f"• {f}", font=(FONT_MAIN, 12)).pack(anchor="w", padx=5)

    def open_manage_sources_menu(self):
        files = os.listdir(SOURCE_DIR)
        if not files:
            self.show_notification("⚠️ No files to delete.", is_alert=True, duration=3000)
            return

        win = ctk.CTkToplevel(self)
        win.title("Manage Sources")
        win.geometry("400x500")
        win.attributes("-topmost", True)
        win.grab_set()

        ctk.CTkLabel(win, text="Select files to delete:", font=(FONT_MAIN, 16, "bold")).pack(pady=15)
        
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        checkboxes = {}
        for f in files:
            var = tk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(scroll, text=f, variable=var, text_color=TEXT_MAIN, fg_color=ACCENT_PRIMARY, hover_color=ACCENT_HOVER)
            cb.pack(anchor="w", pady=5)
            checkboxes[f] = var
            
        def confirm_delete():
            deleted_count = 0
            for f, var in checkboxes.items():
                if var.get():
                    try:
                        os.remove(os.path.join(SOURCE_DIR, f))
                        deleted_count += 1
                    except: pass
            
            if deleted_count > 0:
                self.update_source_list()
                self.cached_vectorstore = None 
                self.show_notification(f"🗑️ Removed {deleted_count} file(s)", duration=3000)
            win.destroy()

        ctk.CTkButton(win, text="Delete Selected", fg_color="#e74c3c", hover_color="#c0392b", command=confirm_delete).pack(pady=20)

if __name__ == "__main__":
    ChatApp().mainloop()
