# Policy Query Bot backend

This directory contains the FastAPI service and LangChain retrieval pipeline.
See the [project README](../README.md) for configuration, local setup, the API
contract, and deployment instructions.

- [main.py](./main.py): API endpoint, authentication, document caching, retrieval,
  and answer generation.
- [data_processor.py](./data_processor.py): PDF extraction, text splitting,
  service clients, and Pinecone indexing.
- [requirements.txt](./requirements.txt): Python dependencies.
- [.env.example](./.env.example): configuration template; copy to `.env` here.
- [Procfile](./Procfile): production start command.

Run backend commands from this directory so `uvicorn main:app` can resolve the
entry point and its imports. Environment loading is relative to the Python files;
exported environment variables take precedence over `.env` values.
