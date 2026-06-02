import os
import textwrap
import subprocess
import sys
import time
import webbrowser

def generate_and_launch():
    print("Initiating V28 Local Enterprise Orchestrator...")
    
    base_dir = globals().get('VAULT_DIR', os.path.join(os.getcwd(), "Policy_Cluster"))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    source_dir = os.path.join(base_dir, "source_docs")
    
    for d in [base_dir, backend_dir, frontend_dir, source_dir]:
        os.makedirs(d, exist_ok=True)

    # ==========================================
    # FILE 1: FASTAPI BACKEND (The Brain)
    # ==========================================
    backend_main_content = textwrap.dedent(f"""\
    import os
    import shutil
    from fastapi import FastAPI, UploadFile, File, HTTPException
    from pydantic import BaseModel
    import uvicorn
    from langchain_openai import ChatOpenAI
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.document_loaders import PyMuPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_core.messages import HumanMessage, SystemMessage

    app = FastAPI(title="Local Policy API")

    SOURCE_DIR = r"{source_dir}"
    INDEX_DIR = os.path.join(SOURCE_DIR, "faiss_index")
    API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    class QueryRequest(BaseModel):
        query: str

    def get_db():
        if os.path.exists(INDEX_DIR):
            try:
                return FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
            except:
                return None
        return None

    @app.get("/")
    def read_root():
        return {{"status": "Backend Online"}}

    @app.post("/ingest/")
    async def ingest_document(file: UploadFile = File(...)):
        file_path = os.path.join(SOURCE_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process and Index
        try:
            docs = PyMuPDFLoader(file_path).load()
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            split_docs = splitter.split_documents(docs)
            
            # Clean metadata
            for d in split_docs:
                d.metadata['source'] = os.path.basename(d.metadata.get('source', 'Unknown'))
                
            db = get_db()
            if db:
                db.add_documents(split_docs)
            else:
                db = FAISS.from_documents(split_docs, embeddings)
                
            db.save_local(INDEX_DIR)
            return {{"status": "success", "filename": file.filename}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/query/")
    async def query_agent(req: QueryRequest):
        if not API_KEY:
            raise HTTPException(status_code=401, detail="Missing OpenRouter API Key in environment.")
            
        db = get_db()
        context = ""
        sources = []
        
        if db:
            docs = db.as_retriever(search_kwargs={{"k": 5}}).invoke(req.query)
            context = "\\n\\n".join([f"Source: {{d.metadata.get('source')}}\\n{{d.page_content}}" for d in docs])
            sources = list(set([d.metadata.get('source') for d in docs]))
            
        sys_prompt = "You are Policy Advisor. Answer using ONLY provided context. Quote verbatim. No hallucinations."
        
        try:
            llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY, model="google/gemini-1.5-flash:free", temperature=0.1)
            resp = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"Context:\\n{{context}}\\n\\nQuery: {{req.query}}")]).content
            return {{"answer": resp, "citations": sources}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    if __name__ == "__main__":
        uvicorn.run(app, host="127.0.0.1", port=8000)
    """)

    # ==========================================
    # FILE 2: STREAMLIT FRONTEND (The UI)
    # ==========================================
    frontend_app_content = textwrap.dedent("""\
    import streamlit as st
    import requests

    st.set_page_config(page_title="Policy Advisor 2026", layout="wide")
    st.title("🏛️ Enterprise Policy Advisor")

    # Sidebar Tools
    with st.sidebar:
        st.header("Control Panel")
        uploaded_file = st.file_uploader("Upload Policy Document", type=["pdf"])
        
        if uploaded_file and st.button("Ingest & Index"):
            with st.spinner("Processing document..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    res = requests.post("http://127.0.0.1:8000/ingest/", files=files)
                    if res.status_code == 200:
                        st.success(f"Indexed: {uploaded_file.name}")
                    else:
                        st.error(f"Error: {res.json().get('detail')}")
                except requests.exceptions.ConnectionError:
                    st.error("Backend server is not reachable.")

    # Main Chat Interface
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "System Online. Awaiting policy inquiry..."}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a compliance question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Auditing policies..."):
                try:
                    res = requests.post("http://127.0.0.1:8000/query/", json={"query": prompt})
                    if res.status_code == 200:
                        data = res.json()
                        answer = data.get("answer")
                        citations = data.get("citations", [])
                        
                        full_response = answer
                        if citations:
                            full_response += f"\\n\\n**Sources Referenced:** {', '.join(citations)}"
                            
                        st.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                    else:
                        error_msg = f"API Error: {res.json().get('detail')}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                except requests.exceptions.ConnectionError:
                    st.error("Backend server is offline.")
    """)

    # Write files
    with open(os.path.join(backend_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(backend_main_content)
    with open(os.path.join(frontend_dir, "app.py"), "w", encoding="utf-8") as f:
        f.write(frontend_app_content)

    print("[SUCCESS] Web Architecture Scaffolding Complete.")
    
    # Ensure dependencies for the web stack are installed
    print("Verifying web framework dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "fastapi", "uvicorn", "streamlit", "python-multipart"])

    # ==========================================
    # LAUNCH THE CLUSTER LOCALLY
    # ==========================================
    print("\nIgniting Local Enterprise Cluster...")
    
    # 1. Launch FastAPI Backend
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=backend_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(" -> Backend API active on Port 8000")
    
    time.sleep(3) # Wait for backend to warm up
    
    # 2. Launch Streamlit Frontend
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501", "--server.headless", "true"],
        cwd=frontend_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(" -> Frontend UI active on Port 8501")
    
    time.sleep(2)
    
    # 3. Open the browser for the user automatically
    print("\nOpening Dashboard in Default Web Browser...")
    webbrowser.open("http://localhost:8501")

    print("\n[CLUSTER RUNNING] Close this terminal window to shut down the servers.")
    
    try:
        # Keep the main script alive so the subprocesses don't die prematurely
        backend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down cluster...")
        backend_process.terminate()
        frontend_process.terminate()

if __name__ == "__main__":
    generate_and_launch()
