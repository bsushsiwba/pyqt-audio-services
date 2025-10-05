from fastapi import FastAPI,status,BackgroundTasks,Query,UploadFile,Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader,TextLoader,Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.chains import RetrievalQA
from openai import OpenAI
import os
from langchain.agents import initialize_agent, AgentType
import os
from langchain.tools import Tool
from langchain.schema import Document
from typing import Optional
import uuid
from Langchain_workers.shared_transcription_rag import shared_state
import shutil
from dotenv import load_dotenv

app=FastAPI()
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
CHROMA_PATH = "./chroma_store"
RESULTS = {}
AZURE_KEY =  os.getenv("AZURE_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")           
AUDIO_FILE = "conversation.wav"
vectordb = None

def delete_chroma_next_start():
    if os.path.exists(CHROMA_PATH):
        try:
            shutil.rmtree(CHROMA_PATH, ignore_errors=True)
            print("🗑️ Deleted old Chroma DB folder (startup cleanup).")
        except Exception as e:
            print(f"[WARN] Could not delete old chroma_store: {e}")

# ✅ Run at app startup (before DB init)
delete_chroma_next_start()
LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class TranscriptionUpdate(BaseModel):
    new_text: str

@app.post("/update_transcription")
def update_transcription(req: TranscriptionUpdate):
    shared_state.set_transcription(req.new_text)
    return {"status": "ok"}
@app.get("/get_transcription")
def get_transcription():
    return {"transcription": shared_state.get_transcription()}

# ----------------- REQUEST MODEL ----------------- #
class QueryRequest(BaseModel):
    query: str
    transcription: Optional[str] = None
    tone: str = "Neutral"
    word_limit: Optional[int] = None
    num_alternatives: int = 1

# ----------------- TOOL FUNCTIONS ----------------- #
def get_info_from_document(query: str) -> str:
    try:
        EMBEDDINGS = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        VECTORDB = Chroma(persist_directory=CHROMA_PATH, embedding_function=EMBEDDINGS)
        RETRIEVER = VECTORDB.as_retriever(search_kwargs={"k": 2})
        docs = RETRIEVER.get_relevant_documents(query)
        return " ".join([doc.page_content for doc in docs])
    except Exception as e:
        return f"[Doc Tool error]: {e}"

def get_info_from_transcription(query: str) -> str:
    transcription = shared_state.get_transcription()

    if not transcription:
        print("[Tool] No transcription found!")
        return ""
    return transcription

# ----------------- BACKGROUND TASK ----------------- #
def process_query_background(task_id: str, req: QueryRequest):
    try:
        # Collect tools
        tools = [Tool.from_function(
            func=get_info_from_document,
            name="get_info_from_document",
            description="Retrieve info from the PDF/Docs vector DB"
        )]

       # if shared_state.get_transcription():
        tools.append(
            Tool.from_function(
                func=get_info_from_transcription,
                name="get_info_from_transcription",
                description="Use this tool if the user query might relate to anything recently spoken or transcribed in the live session. It contains raw or polished conversation text, not documents."
            ))

        # Initialize agent (agent-centric design)
        agent = initialize_agent(
            tools,
            LLM,
            agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True
        )

        # Step 1: Agent retrieves relevant context
        raw_response = agent.invoke(req.query)
        if isinstance(raw_response, str):
            context = raw_response
        elif isinstance(raw_response, dict):
            context = raw_response.get("output", str(raw_response))
        else:
            context = str(raw_response)

        # Step 2: Fallback if nothing retrieved
        if not context.strip():
            context = f"No relevant info found in tools. Answer using GPT:\n{req.query}"

        # Step 3: Polish answer
        polish_prompt = f"""
        You are a helpful assistant.
        Context: {context}

        Task:
        - Answer the query: "{req.query}"
        - Tone: {req.tone}
        - Word Limit: {req.word_limit if req.word_limit else "No limit"}
        - Provide exactly {req.num_alternatives} different phrasings of the answer
        """
        final_answer = LLM.invoke(polish_prompt)
        RESULTS[task_id] = final_answer.content

    except Exception as e:
        RESULTS[task_id] = f"[Error]: {e}"

# ----------------- ENDPOINTS ----------------- #
@app.post("/query")
def start_query(req: QueryRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(process_query_background, task_id, req)
    return JSONResponse(status_code=200, content={"message": "Processing started", "task_id": task_id})

@app.get("/query_result/{task_id}")
def get_query_result(task_id: str):
    result = RESULTS.get(task_id)
    if result:
        return JSONResponse(status_code=200, content={"status": "Completed", "answer": result})
    else:
        return JSONResponse(status_code=200, content={"status": "Processing", "answer": None})


def process_file(file_path: str):
    global vectordb
    ext = os.path.splitext(file_path)[1].lower()

    # Pick loader
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
    elif ext == ".docx":
        loader = Docx2txtLoader(file_path)
    else:
        raise Exception("Unsupported file type")

    docs = loader.load()

    # Split pages
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    split_docs = splitter.split_documents(docs)

    # Embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # ✅ Always initialize with from_documents on empty DB
    if not os.path.exists(CHROMA_PATH) or not os.listdir(CHROMA_PATH):
        vectordb = Chroma.from_documents(split_docs, embeddings, persist_directory=CHROMA_PATH)
        print(f"✅ Vector DB created at {file_path}")
    else:
        vectordb = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
        vectordb.add_documents(split_docs)
        print(f"✅ Following document added to DB {file_path}")

    # ❌ Don't call persist() anymore (Chroma 0.4+ auto-persists)


class FileRequest(BaseModel):
    file_path: str

@app.post("/rag_initiate")
def make_vector_db(req: FileRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_file, req.file_path)
    return JSONResponse(status_code=200, content={"message": "DB creation started"})
TRANSCRIPTS = {}


summary_tasks = {}  # task_id: {"status": "Pending/Completed", "summary": str}

# Simulated background summary function
def generate_summary(task_id: str,diarized:str,language:str,prompt:str):
    """Simulate time-consuming summary generation"""
    

    # Set your API key
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # or just assign your key as a string
    # Call ChatGPT
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You have to summarize the paragrpah which will be provided to you as meeting of meetings in the following language:{language}"},
            {"role": "user", "content":  f"{prompt} here is the diarization {diarized}"}
        ]
        #max_tokens=300
    )

    # Extract the reply
    reply = response.choices[0].message.content

    summary_tasks[task_id]["summary"] = reply
    summary_tasks[task_id]["status"] = "Completed"
class summary_trans(BaseModel):
    diarized:str
    language:str
    prompt:str
# --- START SUMMARY ---
@app.post("/start_summary")
async def start_summary(background_tasks: BackgroundTasks,sum:summary_trans):
    task_id = str(uuid.uuid4())
    summary_tasks[task_id] = {"status": "Pending", "summary": None}


    # Run summary in background
    background_tasks.add_task(generate_summary, task_id,sum.diarized,sum.language,sum.prompt)
    
    return {"task_id": task_id, "status": "Started"}

# --- GET SUMMARY ---
@app.get("/get_summary/{task_id}")
async def get_summary(task_id: str):
    if task_id not in summary_tasks:
        return {"status": "Error", "message": "Task ID not found"}
    
    return summary_tasks[task_id]