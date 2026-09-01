import os
import time
import hashlib
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone
from fastapi.middleware.cors import CORSMiddleware

# Assuming data_processor.py is in the same directory
from data_processor import (
    get_document_text,
    split_text_into_chunks,
    generate_embeddings,
    index_chunks_in_pinecone,
)

# --- Load environment variables ---
load_dotenv()
API_KEY = os.environ.get("API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")

# --- Initialize clients ---
genai.configure(api_key=GOOGLE_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

app = FastAPI(
    title="ClarityClaim AI API",
    description="API for processing insurance policy documents and answering questions using AI.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_doc_id_from_bytes(content: bytes) -> str:
    """Creates a stable SHA256 hash of the file content to use as a document ID."""
    return hashlib.sha256(content).hexdigest()

def generate_answer_with_gemini(question: str, context: str) -> str:
    print(f"Generating answer for question: '{question}' with Gemini Pro...")
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""
    You are an expert insurance policy analyst.
    Based ONLY on the context provided below from an insurance document, answer the user's question.
    Do not use any external knowledge or make assumptions.
    If the answer cannot be found in the provided context, state that clearly.

    CONTEXT:
    ---
    {context}
    ---

    QUESTION: {question}

    ANSWER:
    """
    try:
        response = model.generate_content(prompt)
        if response.parts:
            return response.text.strip()
        else:
            return "The model's response was empty. This may be due to safety filters."
    except Exception as e:
        return "An error occurred while generating the answer with Gemini Pro."

async def process_and_answer(file_content: bytes, questions: list[str]) -> list[str]:
    index_name = "policy-index"

    doc_id_namespace = create_doc_id_from_bytes(file_content)
    print(f"Using Pinecone Namespace: {doc_id_namespace}")

    try:
        index_exists = index_name in pc.list_indexes().names()
        is_processed = False
        if index_exists:
            index = pc.Index(index_name)
            stats = index.describe_index_stats()
            vector_count = stats.get('namespaces', {}).get(doc_id_namespace, {}).get('vector_count', 0)
            is_processed = vector_count > 0

        if not is_processed:
            print(f"Namespace '{doc_id_namespace}' not processed. Starting full processing pipeline...")
            document_text = get_document_text(file_content)
            if not document_text:
                raise HTTPException(status_code=500, detail="Failed to retrieve or process document content.")

            chunks = split_text_into_chunks(document_text)
            if not chunks:
                raise HTTPException(status_code=500, detail="Failed to split document into chunks.")

            embeddings = generate_embeddings(chunks)
            if not embeddings:
                raise HTTPException(status_code=500, detail="Failed to generate embeddings for document chunks.")

            index_chunks_in_pinecone(chunks, embeddings, index_name, namespace=doc_id_namespace)
            index = pc.Index(index_name)
            print("--- New Document Processing and Indexing Complete ---")
        else:
            print(f"Document already processed in namespace '{doc_id_namespace}'. Skipping to question answering.")

        answers = []
        if questions:
            for question in questions:
                print(f"Received question for processing: '{question}'")
                question_embedding_response = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=question,
                    task_type="retrieval_query"
                )
                question_embedding = question_embedding_response['embedding']
                
                search_results = index.query(
                    vector=question_embedding,
                    top_k=5,
                    include_metadata=True,
                    namespace=doc_id_namespace
                )
                
                context_chunks = [match.metadata['text'] for match in search_results.matches]
                context = "\n\n".join(context_chunks)
                
                answer = generate_answer_with_gemini(question, context)
                answers.append(answer)
        else:
            print("No questions received, returning empty answer list.")

        return answers

    except Exception as e:
        print(f"An error occurred during the main process: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# --- Endpoints ---

@app.post("/api/run", tags=["Main Endpoint"])
async def run_query(
    file: UploadFile = File(...),
    question: str = Form(...),
    authorization: str = Header(None),
):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid.")

    token = authorization.split(" ")[1]
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key.")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_content = await file.read()

    answers = await process_and_answer(file_content, [question])
    return {"answers": answers}