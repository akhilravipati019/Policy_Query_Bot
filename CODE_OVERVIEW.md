# Code Overview

What each file in this repo does and how they connect. Read this alongside README.md (README is for running it; this is for understanding it).

## Backend (project root)

### `main.py`

The FastAPI app and the only HTTP-facing file. Three things live here:

- **Client setup** (lines 18-26): loads `.env`, configures the Gemini SDK, opens a Pinecone client. Runs once at import time.
- **`create_doc_id_from_bytes(content)`**: SHA-256 hashes the raw PDF bytes. This hash is used as the Pinecone *namespace* for that document — it's how the app recognizes "I've seen this exact file before" without a database, and how two different users uploading the same PDF end up sharing the same indexed data instead of duplicating it.
- **`generate_answer_with_gemini(question, context)`**: builds the prompt that tells Gemini to answer strictly from the given context and calls `gemini-2.5-flash`. All the actual "prompt engineering" for this app lives in this one function.
- **`process_and_answer(file_content, questions)`**: the orchestration function. Checks whether this document's namespace already has vectors in Pinecone (`index.describe_index_stats()`); if not, runs the full pipeline — extract text, chunk it, embed the chunks, upsert to Pinecone — using functions imported from `data_processor.py`. Then, for each question, embeds it, does a similarity search (`top_k=5`) against that document's namespace, joins the matched chunks into a context string, and calls `generate_answer_with_gemini`.
- **`/api/run` endpoint**: the only route. Accepts `multipart/form-data` (`file` + `question`), checks the `Authorization: Bearer <API_KEY>` header against your own `API_KEY` env var (this has nothing to do with Google or Pinecone — it's just your app's own gatekeeping), rejects non-PDF uploads, reads the file into bytes, and calls `process_and_answer`.

### `data_processor.py`

The document-processing toolkit. `main.py` imports four functions from here; everything else in this file (`create_document_id`, the `if __name__ == "__main__"` block) is leftover/standalone-testing code not used by the live API.

- **`get_document_text(source)`**: extracts plain text from a PDF using PyMuPDF (`fitz`). Accepts either a URL string (downloads it first) or raw `bytes` (uses them directly) — the `bytes` path is what `main.py` actually uses now that uploads replaced URL input.
- **`split_text_into_chunks(text, chunk_size=1000, chunk_overlap=200)`**: a custom recursive splitter. It tries to break text on paragraph breaks first, then line breaks, then sentence-ends, then spaces — falling back to a hard wrap only if a piece still won't fit. This is what keeps chunks from being cut off mid-sentence when possible.
- **`generate_embeddings(text_chunks)`**: sends the chunk list to Gemini's `gemini-embedding-001` model in one batch call, gets back one vector per chunk.
- **`index_chunks_in_pinecone(chunks, embeddings, index_name, namespace)`**: creates the Pinecone index if it doesn't exist yet (sized to match the embedding dimension), then upserts each chunk as a vector with the chunk's own text stored in its metadata (`metadata={"text": chunk}`) — that's what lets `main.py` later pull the actual text back out of a similarity search result, since Pinecone only returns vectors + metadata, not your original chunks.

### `requirements.txt`

Pinned-ish dependency list: `fastapi`/`uvicorn` (web server), `requests` (unused now, was for URL downloads), `PyMuPDF` (PDF text extraction), `google-generativeai` (Gemini SDK), `pinecone` (vector DB SDK), `openai` (unused — leftover dependency, nothing in the code calls it), `python-dotenv` (`.env` loading).

### `ProcFile`

One line: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`. Tells a Render/Heroku-style host how to start the backend in production.

### `.gitignore` (root)

Keeps `.env` (your real API keys), `venv/`, and `__pycache__/` out of git.

## Frontend (`frontend/`)

### `index.html`

The single HTML page Vite serves. Just a `<div id="root">` and a script tag pointing at `src/main.jsx` — everything visible is rendered by React into that div. Page `<title>` is set here ("Policy Query Bot").

### `src/main.jsx`

The actual entry point. Mounts the `App` component into `#root` inside React's `StrictMode` (a dev-only wrapper that helps catch bugs by double-invoking some functions — has no effect on production behavior).

### `src/components/App.jsx`

The top-level component. Holds one piece of state — `currentChat` — and passes it plus a `startNewChat` resetter down to `ChatWindow`. Doesn't render any UI of its own beyond the `.app-container` wrapper.

### `src/components/ChatWindow.jsx`

Where all the actual logic lives:

- Local state: the selected PDF `File` object, the typed question, and an `isLoading` flag.
- `handleSubmit`: validates a file and question are present, builds a `FormData` (file + question), POSTs it to the backend with the `Authorization` header, and on success appends the Q&A pair into `currentChat.messages`.
- The JSX renders the message history, a loading bubble while waiting, and the input row: a circular 📎 button that wraps a hidden `<input type="file">`, a filename chip, the question text input, and the Send button.

### `src/App.css`

All the actual visual styling — chat bubbles, the input bar, the attach button, colors. `index.css` (below) is mostly vestigial from the default Vite template at this point.

### `src/index.css`

Vite's default template stylesheet (dark/light `prefers-color-scheme` root styles, default button styling). Still loaded, but `App.css` is what defines how this app actually looks.

### `vite.config.js`

Minimal Vite config — just registers the `@vitejs/plugin-react` plugin so JSX compiles and Fast Refresh works in dev.

### `eslint.config.js`

Lint rule config: React hooks rules, React Refresh rules, warns on unused variables (except ones starting with an uppercase letter or underscore, which is a common convention for intentionally-unused imports/constants).

### `package.json` / `package-lock.json`

Dependency manifest and lockfile — React 19, Vite 5, `uuid` (used to generate chat IDs), plus the ESLint tooling above as devDependencies.

### `.gitignore` (frontend)

Keeps `node_modules/`, `dist/` (build output), and `frontend/.env` (points at your local backend + holds the shared `API_KEY`) out of git.

## How a request actually flows

1. Browser: pick a PDF, type a question, hit Send → `ChatWindow.jsx` sends `FormData` to `POST /api/run`.
2. `main.py`'s `run_query` checks the auth header, reads the file bytes.
3. `process_and_answer` hashes the bytes → checks Pinecone for that namespace.
4. **New document:** `data_processor.py` extracts text → chunks it → embeds chunks → upserts to Pinecone under that namespace.
5. **Either way:** the question gets embedded, Pinecone returns the 5 closest chunks for that namespace, their text gets joined into a context block.
6. `generate_answer_with_gemini` sends that context + question to Gemini, gets an answer back.
7. `main.py` returns `{"answers": [...]}`, the frontend drops it into the chat as a bot message.
