# Policy Query Bot

Upload an insurance policy PDF, ask a question in plain English, and get an answer
based on the relevant sections of the document.

This is a small retrieval-augmented generation (RAG) application. Instead of
sending the entire policy to an LLM for every question, it finds the most relevant
chunks first and passes those to Gemini as context. The prompt asks Gemini to use
only that context and say when the answer is not available.

The project has a FastAPI backend and a React chat interface. The application
code is organized into [backend/](./backend/) and [frontend/](./frontend/).

## How it works

1. You select a PDF, type a question, and hit Send.
2. The backend hashes the PDF bytes with SHA-256. That hash becomes the document's
   Pinecone namespace, keeping searches scoped to that policy.
3. If the namespace already contains vectors, the backend skips document processing.
4. For a new PDF, PyMuPDF extracts the text and LangChain's recursive text splitter
   divides it into chunks, configured for 1,000 characters with 200-character overlap.
5. LangChain's Gemini embedding integration converts the chunks into vectors, and
   its Pinecone vector store saves them alongside the original chunk text.
6. The retriever embeds your question and finds the five closest chunks in that
   document's namespace.
7. A LangChain prompt/model pipeline sends the question and retrieved text to Gemini.
   The backend returns the answer, and React displays it in the chat.

Uploading the exact same file again reuses its indexed chunks. A different filename
does not change the document ID; different file contents do.

## Stack

| Part | Technology |
| --- | --- |
| API | FastAPI and Uvicorn |
| PDF text extraction | PyMuPDF |
| Chunking | LangChain `RecursiveCharacterTextSplitter` |
| Embeddings | Gemini through `GoogleGenerativeAIEmbeddings` |
| Vector storage and retrieval | Pinecone through `PineconeVectorStore` |
| Answer generation | `ChatPromptTemplate`, `ChatGoogleGenerativeAI`, and `StrOutputParser` |
| Frontend | React, Vite, and plain CSS |

The configured defaults are `models/gemini-embedding-001` for embeddings and
`gemini-2.5-flash` for answers. Both can be changed through environment variables.

## Project layout

```text
Policy_Query_Bot/
|-- backend/                 # FastAPI service and RAG pipeline
|   |-- main.py
|   |-- data_processor.py
|   |-- requirements.txt
|   |-- .env.example
|   |-- Procfile
|   `-- README.md
|-- frontend/                # React application
|   |-- src/
|   |   |-- components/
|   |   |-- main.jsx
|   |   |-- App.css
|   |   `-- index.css
|   |-- .env.example
|   |-- index.html
|   |-- package.json
|   |-- package-lock.json
|   |-- eslint.config.js
|   `-- vite.config.js
|-- .gitignore
`-- README.md
```

Local environments, caches, and build output are omitted from this tree.

- [main.py](./backend/main.py): API endpoint, authentication, document
  caching checks, retrieval, and the answer-generation chain.
- [data_processor.py](./backend/data_processor.py): PDF extraction,
  text splitting, reusable service clients, and Pinecone indexing.
- [frontend/](./frontend/): the React chat interface.
- [requirements.txt](./backend/requirements.txt): backend dependencies.
- [.env.example](./backend/.env.example): backend configuration template.
- [Procfile](./backend/Procfile): production backend start command.

## Running locally

You'll need Python 3.10+, Node.js compatible with Vite 5, a Google Gemini API key,
and a Pinecone API key. The commands below use PowerShell and start from the
repository root.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` with your values:

```dotenv
API_KEY=choose-a-shared-app-secret
GOOGLE_API_KEY=your-google-api-key
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=policy-index-langchain
CHAT_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/gemini-embedding-001
```

`API_KEY` is your app's own shared key, not a Google or Pinecone key. The frontend
sends it in the authorization header. Because it is included in the browser app,
it is not a replacement for per-user authentication.

Start the API from the same terminal:

```powershell
uvicorn main:app --reload --port 8001
```

The backend runs at http://127.0.0.1:8001, with interactive API documentation at
http://127.0.0.1:8001/docs.

### Frontend

Open a second terminal at the repository root:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
```

Edit `frontend/.env`:

```dotenv
VITE_REACT_APP_API_URL_ENDPOINT=http://127.0.0.1:8001/api/run
VITE_REACT_APP_API_KEY=choose-a-shared-app-secret
```

Use the same shared key as the backend's `API_KEY`, then start Vite:

```powershell
npm run dev -- --port 5174
```

Open http://localhost:5174, attach a PDF, and ask a question. The first question
for a new document takes longer because it also runs extraction and indexing.
Keep real credentials out of Git; the environment files are ignored.

## API

**POST `/api/run`**

Send `multipart/form-data` with:

| Field | Value |
| --- | --- |
| `file` | The policy PDF |
| `question` | Your question about the policy |

Include the header `Authorization: Bearer <API_KEY>`.

Example response:

```json
{
  "answers": ["The policy covers hospitalization subject to the listed conditions."]
}
```

The endpoint accepts one question per request. Missing or incorrect authorization
returns `401`; a non-PDF upload or blank question returns `400`.

## Deployment

Deploy the backend and frontend as separate services:

- **Backend:** use `backend/` as the service root, install with
  `pip install -r requirements.txt`, and start with
  `uvicorn main:app --host 0.0.0.0 --port $PORT`. Set the backend environment
  variables in your hosting provider's configuration.
- **Frontend:** use `frontend/` as the service root, install with
  `npm ci`, build with `npm run build`, and publish `dist/`. Set the Vite
  environment variables before building, with the endpoint pointing to the
  deployed backend's `/api/run` route.

The backend currently allows all CORS origins. For deployment, restrict that list
to the frontend's actual origin.

## Things to know

- PDF extraction reads embedded text; there is no OCR step for scanned pages.
- Chat history is displayed in the UI, but previous messages are not sent to the
  model. Each question should make sense on its own.
- Answers depend on the five retrieved chunks. The prompt encourages grounded
  answers, but does not guarantee correctness or coverage of the entire policy.
- The cache considers a document indexed when its namespace has any vectors. It
  does not verify that a previous upload completed successfully.
- Pinecone writes can take time to become searchable, so an immediate first query
  may not see newly uploaded chunks yet.
- Client objects and the answer chain are reused with `@lru_cache` within each
  server process. This does not cache answers or question embeddings.
- The default Pinecone index is created on demand. Gemini requests and Pinecone
  storage use your accounts' quotas. Use a fresh index when changing embedding
  models or vector dimensions.

## Author

Akhil
