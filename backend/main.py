"""FastAPI entry point for the LangChain policy question-answering service."""

from functools import lru_cache
import hashlib
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from data_processor import (
    get_document_text,
    get_pinecone,
    get_vector_store,
    index_chunks_in_pinecone,
    split_text_into_chunks,
)

load_dotenv(Path(__file__).with_name(".env"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "policy-index-langchain")

app = FastAPI(
    title="ClarityClaim AI API",
    description="Ask questions about uploaded insurance policies.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def document_namespace(pdf_bytes: bytes) -> str:
    """Use the PDF contents as a stable Pinecone namespace."""
    return hashlib.sha256(pdf_bytes).hexdigest()


@lru_cache
def answer_chain():
    """Build the prompt/model pipeline once and reuse it for future questions."""
    prompt = ChatPromptTemplate.from_template(
        """
You are an insurance policy analyst.
Answer the question using only the policy excerpts below.
Do not use outside knowledge or make assumptions. If the excerpts do not contain
the answer, say that the policy text provided does not answer the question.

Policy excerpts:
{context}

Question: {question}

Answer:
"""
    )
    model = ChatGoogleGenerativeAI(model=os.getenv("CHAT_MODEL", "gemini-2.5-flash"))
    return prompt | model | StrOutputParser()


def answer_question(question: str, context: str) -> str:
    try:
        answer = answer_chain().invoke({"question": question, "context": context})
        return answer.strip() or "The model returned an empty answer."
    except Exception:
        logger.exception("Gemini answer generation failed")
        return "I could not generate an answer right now."


def document_is_indexed(pinecone, namespace: str) -> bool:
    if INDEX_NAME not in pinecone.list_indexes().names():
        return False
    stats = pinecone.Index(INDEX_NAME).describe_index_stats()
    count = stats.get("namespaces", {}).get(namespace, {}).get("vector_count", 0)
    return count > 0


def process_document(pdf_bytes: bytes, question: str) -> str:
    namespace = document_namespace(pdf_bytes)
    pinecone = get_pinecone()

    if document_is_indexed(pinecone, namespace):
        logger.info("Using existing Pinecone namespace %s", namespace)
        store = get_vector_store(INDEX_NAME, namespace)
    else:
        logger.info("Indexing a new policy in namespace %s", namespace)
        text = get_document_text(pdf_bytes)
        if not text.strip():
            raise HTTPException(500, "Could not extract text from the PDF.")
        chunks = split_text_into_chunks(text)
        if not chunks:
            raise HTTPException(500, "Could not split the PDF text into chunks.")
        store = index_chunks_in_pinecone(chunks, INDEX_NAME, namespace)

    retriever = store.as_retriever(search_kwargs={"k": 5})
    documents = retriever.invoke(question)
    context = "\n\n".join(document.page_content for document in documents)
    return answer_question(question, context)


async def process_and_answer(pdf_bytes: bytes, question: str) -> str:
    """Run blocking PDF and vector-store work away from FastAPI's event loop."""
    try:
        return await run_in_threadpool(process_document, pdf_bytes, question)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Policy processing failed")
        raise HTTPException(500, "The policy could not be processed.")


@app.post("/api/run", tags=["Main Endpoint"])
async def run_query(
    file: UploadFile = File(...),
    question: str = Form(...),
    authorization: str | None = Header(default=None),
):
    """Accept one PDF question and return the original response shape."""
    expected_key = os.getenv("API_KEY")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization header missing or invalid.")
    if not expected_key or authorization.removeprefix("Bearer ") != expected_key:
        raise HTTPException(401, "Invalid API key.")
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are supported.")
    if not question.strip():
        raise HTTPException(400, "Please enter a question.")

    answer = await process_and_answer(await file.read(), question.strip())
    return {"answers": [answer]}
