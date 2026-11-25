"""PDF extraction, chunking, and Pinecone access for the policy bot."""

from functools import lru_cache
import os
import time
from pathlib import Path

import fitz
import requests
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec

load_dotenv(Path(__file__).with_name(".env"))


@lru_cache
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Create the embedding service once and reuse it for this process."""
    model_name = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    return GoogleGenerativeAIEmbeddings(model=model_name)


@lru_cache
def get_pinecone() -> Pinecone:
    """Create one Pinecone client for the running API process."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY is not set.")
    return Pinecone(api_key=api_key)


def get_document_text(source: str | bytes) -> str:
    """Return the text from a PDF URL or uploaded PDF bytes."""
    if isinstance(source, str): 
        response = requests.get(source, timeout=60)
        response.raise_for_status()
        pdf_bytes = response.content
    elif isinstance(source, bytes):
        pdf_bytes = source
    else:
        raise TypeError("The document must be a URL or PDF bytes.")

    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        page_texts = []

        for page in pdf:
            text = page.get_text()
            page_texts.append(text)

        document_text = "\n\n".join(page_texts)
        return document_text


def split_text_into_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """Split policy text while keeping nearby paragraphs and sentences together."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def get_vector_store(index_name: str, namespace: str) -> PineconeVectorStore:
    """Return a LangChain vector store scoped to one uploaded PDF."""
    return PineconeVectorStore(
        index=get_pinecone().Index(index_name),
        embedding=get_embeddings(),
        namespace=namespace,
        text_key="text",
    )


def _wait_for_index(index_name: str, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while not get_pinecone().describe_index(index_name).status.ready:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Pinecone index '{index_name}' was not ready in time.")
        time.sleep(1)


def index_chunks_in_pinecone(
    chunks: list[str],
    index_name: str,
    namespace: str,
) -> PineconeVectorStore:
    """Create the index if needed, then embed and store the policy chunks."""
    pinecone = get_pinecone()
    if index_name not in pinecone.list_indexes().names():
        dimension = len(get_embeddings().embed_query("dimension check"))
        pinecone.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        _wait_for_index(index_name)

    store = get_vector_store(index_name, namespace)
    store.add_texts(
        texts=chunks,
        ids=[f"chunk-{namespace}-{number}" for number in range(len(chunks))],
    )
    return store
