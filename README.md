# Policy Query Bot

Upload an insurance policy PDF, ask it questions in plain English, get answers grounded in the actual document text — not a generic LLM guess.

Under the hood it's a small RAG setup: the PDF gets chunked, each chunk is embedded and pushed into Pinecone, and at query time the top matching chunks get stuffed into a Gemini prompt along with your question. Gemini is told explicitly to answer only from that context, so it won't make things up when the policy doesn't cover something.

The repo has two parts: a FastAPI backend that does all the processing, and a React (Vite) frontend that gives you a chat-style UI to upload a file and ask questions.

## How it works

1. You upload a PDF and type a question.
2. The backend hashes the file content to get a stable document ID, then checks Pinecone to see if that exact file has already been processed.
3. If it's new, the text gets pulled out with PyMuPDF, split into overlapping chunks, embedded with Gemini's embedding model, and upserted into a Pinecone namespace keyed by that hash.
4. Your question gets embedded too, Pinecone returns the closest matching chunks, and those get passed to Gemini as context for the actual answer.
5. Re-upload the same file later and step 3 gets skipped entirely — it just goes straight to answering.

## Stack

- **Backend:** Python, FastAPI, PyMuPDF for PDF text extraction, Gemini for embeddings + generation, Pinecone as the vector store.
- **Frontend:** React + Vite, plain CSS, no UI framework.

## Running it locally

You'll need Python 3.9+, Node 18+, a Gemini API key, and a Pinecone API key.

**Backend**

```bash
python -m venv venv
venv\Scripts\activate      # or: source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
API_KEY="pick-any-secret-string"
GOOGLE_API_KEY="your-gemini-api-key"
PINECONE_API_KEY="your-pinecone-api-key"
```

`API_KEY` isn't tied to any external service — it's just the password your frontend uses to talk to your own backend, so make up whatever value you want.

```bash
uvicorn main:app --reload
```

Runs on `http://127.0.0.1:8000`.

**Frontend**

```bash
cd frontend
npm install
```

Create a `.env` file inside `frontend/`:

```
VITE_REACT_APP_API_URL_ENDPOINT=http://127.0.0.1:8000/api/run
VITE_REACT_APP_API_KEY="same-value-as-backend-API_KEY"
```

```bash
npm run dev
```

Runs on `http://localhost:5173` (Vite will bump the port if that one's taken).

## API

**POST** `/api/run`

Multipart form data:
- `file` — the PDF
- `question` — your question about it

Header: `Authorization: Bearer <your API_KEY>`

Response:

```json
{ "answers": ["The answer, based on the document."] }
```

## Deploying

Set up as two separate services (this was built against Render, but any host that does a Python web service + static site works the same way):

- **Backend** — web service pointed at the repo root, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **Frontend** — static site pointed at `frontend/`, build with `npm run build`, publish the `dist/` folder. Point its env vars at the live backend URL once that's deployed.

## Author

Akhil
