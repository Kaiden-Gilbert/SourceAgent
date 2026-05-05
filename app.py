import os
import sys
import subprocess
import time
import uuid 
import threading
import json
import datetime
import tkinter as tk 
import re 

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
APP_VERSION = "3.0" 

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
        
        self.load_save_data()
        
        ctk.set_appearance_mode(self.app_theme)
        self.draw_gradient_background()

        if self.user_name:
            self.show_welcome_back_screen()
        else:
            self.show_boot_screen()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    # ==========================================
    # 0. SETTINGS & UPDATE LOGIC
    # ==========================================
    def open_settings_menu(self):
        self.settings_win = ctk.CTkToplevel(self)
        self.settings_win.title("Settings")
        self.settings_win.geometry("400x450")
        self.settings_win.attributes("-topmost", True)
        self.settings_win.grab_set()

        ctk.CTkLabel(self.settings_win, text="⚙️ Settings panel", font=(FONT_MAIN, 22, "bold")).pack(pady=(20, 30))

        ctk.CTkLabel(self.settings_win, text="Appearance Theme:", font=(FONT_MAIN, 14, "bold")).pack(anchor="w", padx=30)
        
        self.theme_menu = ctk.CTkOptionMenu(
            self.settings_win, 
            values=["System", "Dark", "Light"], 
            command=self.change_theme,
            fg_color=ACCENT_PRIMARY, button_color=ACCENT_HOVER
        )
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
            version_file = os.path.join(BASE_DIR, "latest_version.txt")
            if os.path.exists(version_file):
                with open(version_file, "r") as f:
                    latest_version = f.read().strip()
                
                if float(latest_version) > float(APP_VERSION):
                    if manual and hasattr(self, 'update_status_lbl'):
                        self.update_status_lbl.configure(text=f"Update v{latest_version} found! Restart required.", text_color="#2ecc71")
                    else:
                        self.after(3000, lambda: self.show_update_notification(latest_version))
                else:
                    if manual and hasattr(self, 'update_status_lbl'):
                        self.update_status_lbl.configure(text="You are on the latest version.", text_color=TEXT_MUTED)
            else:
                if manual and hasattr(self, 'update_status_lbl'):
                    self.update_status_lbl.configure(text="Update server unreachable.", text_color="#e74c3c")
        except Exception as e:
            print(f"Update check failed: {e}")

    def show_update_notification(self, latest_version):
        self.update_banner = ctk.CTkFrame(self, fg_color=ACCENT_PRIMARY, corner_radius=8, border_width=1, border_color="#ffffff")
        self.update_banner.place(relx=0.5, rely=0.06, anchor="center")
        lbl = ctk.CTkLabel(self.update_banner, text=f"🚀 Update Available: v{latest_version} is ready for installation!", font=(FONT_MAIN, 13, "bold"), text_color="white")
        lbl.pack(side="left", padx=(20, 10), pady=10)
        btn = ctk.CTkButton(self.update_banner, text="Dismiss", width=60, fg_color="transparent", border_color="white", border_width=1, text_color="white", hover_color=ACCENT_HOVER, command=self.update_banner.destroy)
        btn.pack(side="right", padx=(0, 20), pady=10)

    # ==========================================
    # 1. DATA PERSISTENCE
    # ==========================================
    def load_save_data(self):
        self.user_name = None
        self.current_session_id = str(uuid.uuid4())
        self.session_history = [] 
        self.app_theme = "Dark" 
        
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    data = json.load(f)
                    self.user_name = data.get("user_name")
                    self.current_session_id = data.get("session_id", self.current_session_id)
                    self.session_history = data.get("history_list", [])
                    self.app_theme = data.get("app_theme", "Dark")
            except: pass

    def save_current_state(self):
        data = {
            "user_name": self.user_name,
            "session_id": self.current_session_id,
            "history_list": self.session_history,
            "app_theme": self.app_theme
        }
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def draw_gradient_background(self):
        self.bg_canvas = tk.Canvas(self, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._paint_gradient)

    def _paint_gradient(self, event=None):
        self.bg_canvas.delete("gradient")
        h = self.winfo_height()
        if h == 0: return 
        
        mode = ctk.get_appearance_mode()
        if mode == "Light":
            top_color, mid_color, bot_color = "#e0eafc", "#cfdef3", "#e0eafc" 
        else:
            top_color, mid_color, bot_color = "#0f0c29", "#302b63", "#24243e" 
            
        for i in range(int(h/2)):
            c = interpolate_color(top_color, mid_color, i / (h/2))
            self.bg_canvas.create_line(0, i, self.winfo_width(), i, fill=c, tags="gradient")
        for i in range(int(h/2), h):
            c = interpolate_color(mid_color, bot_color, (i - h/2) / (h/2))
            self.bg_canvas.create_line(0, i, self.winfo_width(), i, fill=c, tags="gradient")
        self.bg_canvas.lower("all") 

    # ==========================================
    # 2. BOOT SCREENS
    # ==========================================
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
        name = self.name_entry.get().strip()
        if name:
            self.user_name = name
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
            c = interpolate_color("#0f0c29", "#ffffff", step / 30)
            self.welcome_label.configure(text_color=c)
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
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="📚 SourceAgent", font=(FONT_MAIN, 20, "bold")).pack(pady=(30, 20), padx=20, anchor="w")
        
        ctk.CTkButton(self.sidebar, text="+ New Session", fg_color=ACCENT_PRIMARY, command=self.start_new_session).pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="CHAT HISTORY", font=(FONT_MAIN, 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(20, 5))
        self.history_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=200)
        self.history_list.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="KNOWLEDGE BASE", font=(FONT_MAIN, 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(10, 5))
        self.source_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", height=150)
        self.source_list.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(self.sidebar, text="📄 Upload Files", command=self.upload_files, fg_color=BG_SURFACE).pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(self.sidebar, text="⚙️ Settings", command=self.open_settings_menu, fg_color="transparent", border_color="#333", border_width=1).pack(side="bottom", fill="x", padx=20, pady=20)

        self.chat_container = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_container.grid_rowconfigure(0, weight=1)
        self.chat_container.grid_columnconfigure(0, weight=1)
        
        self.chat_display = ctk.CTkTextbox(self.chat_container, state="disabled", font=(FONT_MAIN, 15), wrap="word", fg_color="transparent", spacing1=4, spacing3=4)
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 20))
        
        self.status_indicator = ctk.CTkLabel(self.chat_container, text="🟢 Initializing Multi-Agent Core...", text_color=TEXT_MUTED)
        self.status_indicator.grid(row=1, column=0, sticky="w", padx=15, pady=(0,5))

        self.input_wrapper = ctk.CTkFrame(self.chat_container, fg_color=BG_SURFACE, corner_radius=12, border_width=1, border_color="#333")
        self.input_wrapper.grid(row=2, column=0, sticky="ew")
        self.input_wrapper.grid_columnconfigure(0, weight=1)
        
        self.user_input = ctk.CTkEntry(self.input_wrapper, placeholder_text="Ask the Agent Brain Trust...", height=55, border_width=0, fg_color="transparent")
        self.user_input.grid(row=0, column=0, sticky="ew", padx=15)
        self.user_input.bind("<Return>", lambda e: self.send_message())
        
        self.send_btn = ctk.CTkButton(self.input_wrapper, text="Send", width=80, command=self.send_message)
        self.send_btn.grid(row=0, column=1, padx=10)

        self.update_sidebar_history()
        self.update_source_list()
        self.load_active_chat_to_display()

    # ==========================================
    # 4. CHAT HISTORY LOGIC & TEXT SANITIZER
    # ==========================================
    def format_ui_text(self, text):
        text = text.replace("**", "")       
        text = text.replace("* ", "• ")     
        text = text.replace("- ", "• ")     
        text = text.replace("### ", "")     
        text = text.replace("## ", "")      
        text = text.replace("# ", "")       
        return text

    def update_sidebar_history(self):
        for w in self.history_list.winfo_children(): w.destroy()
        for entry in reversed(self.session_history):
            btn = ctk.CTkButton(
                self.history_list, text=entry['title'], anchor="w", 
                fg_color="transparent", text_color=TEXT_MAIN, hover_color="#222",
                command=lambda sid=entry['id']: self.switch_to_session(sid)
            )
            btn.pack(fill="x", pady=2)

    def switch_to_session(self, sid):
        self.current_session_id = sid
        self.save_current_state()
        self.load_active_chat_to_display()

    def load_active_chat_to_display(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        
        history_file = os.path.join(HISTORY_DIR, f"{self.current_session_id}.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    messages = json.load(f)
                    for msg in messages:
                        role = "👤 You" if msg['type'] == 'human' else "🤖 Agent"
                        clean_content = self.format_ui_text(msg['data']['content'])
                        self.chat_display.insert("end", f"{role}:\n{clean_content}\n\n")
            except: pass
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def start_new_session(self):
        new_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%b %d, %H:%M")
        self.session_history.append({"id": new_id, "timestamp": timestamp, "title": f"Chat {timestamp}"})
        self.current_session_id = new_id
        self.save_current_state()
        self.update_sidebar_history()
        self.load_active_chat_to_display()

    # ==========================================
    # 5. THE MULTI-AGENT BRAIN TRUST
    # ==========================================
    def setup_ai(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        
        r_primary = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="google/gemma-3-27b-it:free", max_retries=2, timeout=45.0)
        r_fallback = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="mistralai/mistral-small-3.1-24b:free", max_retries=2)
        self.researcher_engine = r_primary.with_fallbacks([r_fallback])

        e_primary = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="meta-llama/llama-3.3-70b-instruct:free", streaming=True, max_retries=2, timeout=60.0)
        e_fallback = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key, model="openrouter/auto", streaming=True, max_retries=2)
        self.editor_engine = e_primary.with_fallbacks([e_fallback])
        
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.after(0, lambda: self.status_indicator.configure(text="🟢 Dual-Agent Core Ready"))

    def send_message(self):
        query = self.user_input.get().strip()
        if not query: return
        self.user_input.delete(0, "end")
        
        self.user_input.configure(state="disabled")
        self.send_btn.configure(state="disabled")
        
        self.append_chat_to_ui(f"👤 You:\n{query}\n\n")
        threading.Thread(target=self.run_agentic_workflow, args=(query,), daemon=True).start()

    def run_agentic_workflow(self, query):
        try:
            self.after(0, lambda: self.status_indicator.configure(text="🔍 Scanning files..."))
            docs = []
            for f in os.listdir(SOURCE_DIR):
                path = os.path.join(SOURCE_DIR, f)
                if f.endswith(".pdf"): docs.extend(PyMuPDFLoader(path).load())
                elif f.endswith(".txt"): docs.extend(TextLoader(path, encoding="utf-8").load())
            
            context = "No documents provided."
            if docs:
                splits = RecursiveCharacterTextSplitter(chunk_size=1000).split_documents(docs)
                vs = FAISS.from_documents(splits, self.embeddings)
                relevant = vs.as_retriever(search_kwargs={"k": 5}).invoke(query)
                context = "\n\n".join([d.page_content for d in relevant])

            history_obj = FileChatMessageHistory(os.path.join(HISTORY_DIR, f"{self.current_session_id}.json"))
            history_text = "\n".join([f"{'User' if m.type == 'human' else 'Agent'}: {m.content}" for m in history_obj.messages[-4:]])

            self.after(0, lambda: self.status_indicator.configure(text="🧠 Researcher AI (Gemma) analyzing data..."))
            researcher_prompt = f"""You are the Researcher AI.
            User: {self.user_name}
            Context: {context}
            Chat History: {history_text}
            Question: {query}
            
            Task: Ignore formatting. Extract all raw facts, logic, and answers required to answer the User's question based ONLY on the context and history provided.
            """
            
            try:
                researcher_draft = self.researcher_engine.invoke(researcher_prompt).content
            except Exception as e:
                researcher_draft = f"[Researcher Failed to connect, proceed with general knowledge. Error: {str(e)}]"

            self.after(0, lambda: self.status_indicator.configure(text="✨ Editor AI (Llama) perfecting response..."))
            editor_prompt = f"""You are the Editor AI assisting {self.user_name}.
            The internal Researcher AI has provided this raw data draft: 
            "{researcher_draft}"
            
            Task: Write the perfect, final response to {self.user_name}'s question: "{query}"
            Use the Researcher's data to ensure accuracy. Make it highly conversational, helpful, and format it beautifully using Markdown. Do not mention the Researcher AI, just provide the final answer.
            """
            
            self.after(0, lambda: self.chat_display.configure(state="normal"))
            self.after(0, lambda: self.chat_display.insert("end", "🤖 Agent:\n"))
            
            full_final_response = ""
            
            for chunk in self.editor_engine.stream(editor_prompt):
                token = chunk.content
                full_final_response += token
                
                ui_token = self.format_ui_text(token)
                
                self.after(0, lambda t=ui_token: self.chat_display.insert("end", t))
                self.after(0, lambda: self.chat_display.see("end"))

            history_obj.add_user_message(query)
            history_obj.add_ai_message(full_final_response)

            self.after(0, lambda: self.chat_display.insert("end", "\n\n"))
            self.after(0, lambda: self.chat_display.configure(state="disabled"))
            self.after(0, lambda: self.status_indicator.configure(text="🟢 Dual-Agent Core Ready"))

        except Exception as e:
            self.after(0, lambda: self.append_chat_to_ui(f"⚙️ Error: {str(e)}\n\n"))
            self.after(0, lambda: self.status_indicator.configure(text="❌ Agent Failure"))
            
        self.after(0, lambda: self.user_input.configure(state="normal"))
        self.after(0, lambda: self.send_btn.configure(state="normal"))
        self.after(0, lambda: self.user_input.focus_set())

    def append_chat_to_ui(self, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", text)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    # ==========================================
    # 6. WORKSPACE LOGIC
    # ==========================================
    def upload_files(self):
        files = filedialog.askopenfilenames()
        if not files: return
        self.status_indicator.configure(text="📥 Ingesting Files...")
        for f in files: shutil.copy(f, SOURCE_DIR)
        self.update_source_list()
        self.status_indicator.configure(text="🟢 Dual-Agent Core Ready")

    def update_source_list(self):
        for w in self.source_list.winfo_children(): w.destroy()
        files = os.listdir(SOURCE_DIR)
        for f in files:
            ctk.CTkLabel(self.source_list, text=f"• {f}", font=(FONT_MAIN, 12)).pack(anchor="w", padx=5)

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()