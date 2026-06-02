import os
import textwrap

def generate_enterprise_cluster():
    print("Initiating Enterprise Genesis Protocol...")
    
    # Define the target directory
    base_dir = os.path.join(os.getcwd(), "Policy_Enterprise_Cluster")
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    
    # Create directory structure
    for d in [base_dir, backend_dir, frontend_dir]:
        os.makedirs(d, exist_ok=True)
        print(f"[CREATED] Directory: {d}")

    # ==========================================
    # FILE 1: DOCKER COMPOSE (Infrastructure)
    # ==========================================
    docker_compose_content = textwrap.dedent("""\
    version: '3.8'
    services:
      backend:
        build: ./backend
        ports:
          - "8000:8000"
        environment:
          - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
        volumes:
          - ./backend:/app
        depends_on:
          - vector_db

      frontend:
        build: ./frontend
        ports:
          - "8501:8501"
        volumes:
          - ./frontend:/app
        depends_on:
          - backend

      vector_db:
        image: qdrant/qdrant:latest
        ports:
          - "6333:6333"
        volumes:
          - qdrant_data:/qdrant/storage

    volumes:
      qdrant_data:
    """)

    # ==========================================
    # FILE 2: FASTAPI BACKEND (The Brain)
    # ==========================================
    backend_main_content = textwrap.dedent("""\
    from fastapi import FastAPI, UploadFile, File
    from pydantic import BaseModel
    import uvicorn

    app = FastAPI(title="Policy Advisor Enterprise API", version="1.0")

    class QueryRequest(BaseModel):
        query: str
        session_id: str

    @app.get("/")
    def read_root():
        return {"status": "Enterprise API Online", "vector_db": "Connected"}

    @app.post("/ingest/")
    async def ingest_document(file: UploadFile = File(...)):
        # TODO: Implement LangChain PDF parsing, Chunking, and Qdrant ingestion here
        return {"filename": file.filename, "status": "Ingested and Indexed successfully."}

    @app.post("/query/")
    async def query_agent(req: QueryRequest):
        # TODO: Implement Agentic Retrieval Loop and Reranking here
        simulated_response = f"Verified Agent Response for: '{req.query}'. [Source: Enterprise_Doc.pdf]"
        return {"answer": simulated_response, "citations": ["Enterprise_Doc.pdf"]}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)
    """)

    # ==========================================
    # FILE 3: STREAMLIT FRONTEND (The UI)
    # ==========================================
    frontend_app_content = textwrap.dedent("""\
    import streamlit as st
    import requests

    st.set_page_config(page_title="Policy Advisor 2026", layout="wide")
    st.title("🏛️ Enterprise Policy Advisor")

    st.sidebar.header("Control Panel")
    uploaded_file = st.sidebar.file_uploader("Upload Policy Document", type=["pdf", "docx", "txt"])

    if uploaded_file is not None:
        if st.sidebar.button("Ingest Document"):
            files = {"file": uploaded_file.getvalue()}
            # Send to FastAPI backend
            # res = requests.post("http://backend:8000/ingest/", files={"file": (uploaded_file.name, uploaded_file.getvalue())})
            st.sidebar.success(f"Successfully ingested {uploaded_file.name}")

    st.subheader("Secure Agentic Terminal")
    query = st.text_input("Ask a compliance question:")

    if st.button("Submit Query"):
        if query:
            with st.spinner("Agentic Retrieval Loop Active..."):
                # Call FastAPI backend
                # res = requests.post("http://backend:8000/query/", json={"query": query, "session_id": "123"})
                # answer = res.json().get("answer")
                
                # Simulated response for scaffold
                st.info(f"**Advisor:** This is a simulated response bridging to the FastAPI backend for: '{query}'")
                st.caption("Sources: Example_Policy.pdf | Confidence: 98%")
    """)

    # ==========================================
    # FILE 4 & 5: DEPENDENCIES
    # ==========================================
    backend_reqs = "fastapi\nuvicorn\npydantic\nlangchain\nlangchain-openai\nqdrant-client\npython-multipart\n"
    frontend_reqs = "streamlit\nrequests\n"

    # Write files to disk
    files_to_create = {
        os.path.join(base_dir, "docker-compose.yml"): docker_compose_content,
        os.path.join(backend_dir, "main.py"): backend_main_content,
        os.path.join(backend_dir, "requirements.txt"): backend_reqs,
        os.path.join(frontend_dir, "app.py"): frontend_app_content,
        os.path.join(frontend_dir, "requirements.txt"): frontend_reqs,
    }

    for file_path, content in files_to_create.items():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[CREATED] File: {file_path}")

    print("\n" + "="*50)
    print("✅ ENTERPRISE GENESIS COMPLETE")
    print("="*50)
    print(f"Your new distributed architecture has been generated at:\n{base_dir}\n")
    print("Next Steps to launch your Enterprise Cluster:")
    print("1. Open your terminal and navigate to the new folder:")
    print(f"   cd {base_dir}")
    print("2. (If you have Docker installed) Run:")
    print("   docker-compose up --build")
    print("3. Alternatively, run the backend and frontend separately using pip and uvicorn/streamlit.")

if __name__ == "__main__":
    generate_enterprise_cluster()
