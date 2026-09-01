import requests
import fitz
import textwrap
import os
import google.generativeai as genai
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
import hashlib
import time

# Load environment variables from .env file
load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.environ.get("PINECONE_ENVIRONMENT")

# Initialize clients
genai.configure(api_key=GOOGLE_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# --- CORRECTED FUNCTION: Handles both URLs and binary file content ---
def get_document_text(source) -> str:
    """
    Extracts text from a document, handling either a URL or raw binary content.
    """
    document_content = None

    if isinstance(source, str):  # If the source is a URL string
        print(f"Downloading document from {source}...")
        try:
            response = requests.get(source)
            response.raise_for_status()
            document_content = response.content
        except requests.exceptions.RequestException as e:
            print(f"Error downloading the document: {e}")
            return ""
    elif isinstance(source, bytes):  # If the source is raw file content (from upload)
        print("Processing uploaded document content...")
        document_content = source
    else:
        print("Invalid source type provided to get_document_text.")
        return ""

    if not document_content:
        return ""

    print("Extracting text from the document...")
    document_text = ""
    try:
        pdf_document = fitz.open(stream=document_content, filetype="pdf")
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            document_text += page.get_text()
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""

    return document_text

def create_document_id(source: str) -> str:
    """Creates a stable SHA256 hash of the URL to use as a document ID."""
    return hashlib.sha256(source.encode()).hexdigest()

def split_text_into_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """
    Splits a large text document into smaller, overlapping chunks using a recursive strategy.
    """
    def _recursive_split(t, separators, size, overlap):
        if not separators:
            return textwrap.wrap(t, size)
        
        current_sep = separators[0]
        other_seps = separators[1:]
        
        parts = t.split(current_sep)
        chunks = []
        
        for part in parts:
            if len(part) > size:
                chunks.extend(_recursive_split(part, other_seps, size, overlap))
            else:
                chunks.append(part)
        
        final_chunks = []
        if chunks:
            current_chunk = chunks[0]
            for i in range(1, len(chunks)):
                if len(current_chunk) + len(chunks[i]) <= size + overlap:
                    current_chunk += current_sep + chunks[i]
                else:
                    final_chunks.append(current_chunk)
                    current_chunk = chunks[i]
            final_chunks.append(current_chunk)

        return [c for c in final_chunks if c.strip()]

    separators = ["\n\n", "\n", ". ", " "]
    chunks = _recursive_split(text, separators, chunk_size, chunk_overlap)
    
    return chunks

def generate_embeddings(text_chunks: list[str]) -> list:
    """
    Generates vector embeddings for a list of text chunks using Gemini Pro API.
    """
    print(f"Generating embeddings for {len(text_chunks)} chunks using Gemini Pro...")
    embeddings = []
    try:
        response = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text_chunks
        )
        embeddings = response['embedding']
        print("Embeddings generated successfully.")
    except Exception as e:
        print(f"Error generating embeddings: {e}")
    
    return embeddings

def index_chunks_in_pinecone(chunks: list[str], embeddings: list, index_name: str, namespace: str):
    """
    Indexes the text chunks and their embeddings in a specific Pinecone namespace.
    """
    print(f"Indexing {len(chunks)} chunks in Pinecone index '{index_name}' under namespace '{namespace}'...")
    try:
        # Check if index exists, and create if it doesn't
        if index_name not in pc.list_indexes().names():
            print(f"Creating new Pinecone index: '{index_name}'")
            pc.create_index(
                name=index_name,
                dimension=len(embeddings[0]),
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-east-1')
            )
            print("Index created successfully. Waiting for it to become ready...")
            # Wait for index to be ready
            while not pc.describe_index(index_name).status.ready:
                time.sleep(1)

        index = pc.Index(index_name)
        
        # Prepare data for upsert
        vectors_to_upsert = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors_to_upsert.append({
                "id": f"chunk-{namespace}-{i}", # Make ID unique across namespaces
                "values": embedding,
                "metadata": {"text": chunk}
            })
        
        # Upsert in batches
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i + batch_size]
            index.upsert(vectors=batch, namespace=namespace) # <-- USE THE NAMESPACE
            print(f"Upserted batch {i // batch_size + 1} into namespace '{namespace}'")

        print(f"Successfully indexed {len(chunks)} chunks in namespace '{namespace}'.")
        # Give a moment for the index to become queryable
        time.sleep(5)
        
    except Exception as e:
        print(f"Error indexing in Pinecone: {e}")
        
if __name__ == "__main__":
    sample_url = "https://example.com/sample-policy.pdf"
    index_name = "policy-index"

    document_content = get_document_text(sample_url)
    
    if document_content:
        chunks = split_text_into_chunks(document_content)
        print(f"\n--- Document Split into {len(chunks)} Chunks ---")
        
        embeddings = generate_embeddings(chunks)

        if embeddings:
            print(f"Generated {len(embeddings)} embeddings.")
            print(f"Size of each embedding vector: {len(embeddings[0])}")

            # Index the chunks in Pinecone
            print("--- Running standalone script test ---")
            test_namespace = create_document_id(sample_url) # Use the new function!
            index_chunks_in_pinecone(chunks, embeddings, index_name, namespace=test_namespace)
        else:
            print("Failed to generate embeddings. Pinecone indexing skipped.")

    else:
        print("Failed to process document content.")