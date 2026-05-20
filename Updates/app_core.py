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
        self.orbs = [self.bg_canvas.create_oval(0,0,0,0, outline="", fill="#
