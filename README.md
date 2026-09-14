# AI Customer Support Agent

A backend service that answers customer support questions with a language model,
grounding every answer in the company's own data rather than the model's
training. Three sources feed each response: the customer's account record, their
order history, and the company policy document.

The goal is an agent that can say *"your order shipped Tuesday, tracking
TRK9400111899"* — and that refuses to invent an answer when the information
isn't there.

## How it works

A question arrives at `POST /chat` with the customer's email. The service then:

1. **Looks up the customer** in SQLite via SQLAlchemy, returning early if the
   account doesn't exist.
2. **Collects their orders** through the `Customer → Order` relationship —
   product, price, status, tracking number, order date.
3. **Retrieves relevant policy text.** The company policy PDF is split into
   1000-character chunks with 200 characters of overlap, embedded with OpenAI
   embeddings, and stored in a persistent Chroma vector database. Each question
   runs a similarity search and pulls the three closest chunks.
4. **Builds a grounded prompt** from those three sources and sends it to the
   model with instructions never to invent information and to escalate when
   something is missing.

Retrieval happens against a vector store built ahead of time, so the model sees
only the policy passages relevant to the question instead of the whole document.

## Stack

| | |
|---|---|
| API | FastAPI |
| Language model | OpenAI |
| Vector store | Chroma, persisted to disk |
| Chunking & embeddings | LangChain, OpenAI embeddings |
| Database | SQLite via SQLAlchemy ORM |
| PDF parsing | pypdf |

## Running it

Requires Python 3.12 and an OpenAI API key.

```bash
git clone <repo-url>
cd AI-Customer-Support-Agent/backend

python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
```

Add your API key:

```bash
cp ../.env.example .env
# then edit .env and paste in your key
```

Create the database, load sample customers, and build the vector store:

```bash
python init_db.py
python seed_data.py
python -m rag.ingest
```

Start the service:

```bash
uvicorn main:app --reload
```

### Asking it something

```bash
curl -X POST "http://localhost:8000/chat?email=john.smith@example.com&question=Where%20is%20my%20order?"
```

```json
{ "answer": "Your Wireless Headphones order ORD-10001 shipped and is tracking under TRK9400111899." }
```

Interactive API docs are at `http://localhost:8000/docs`.

## Sample data

`seed_data.py` creates five fictional customers with seven orders between them,
spanning active, suspended, and multiple membership tiers so the agent's
behavior can be checked against different account states. All names, emails,
phone numbers, and tracking numbers are invented.

## Project layout

```
backend/
├── main.py           # FastAPI app and the /chat endpoint
├── models.py         # Customer and Order ORM models
├── database.py       # SQLAlchemy engine and session
├── init_db.py        # creates the database schema
├── seed_data.py      # loads sample customers and orders
├── knowledge/        # source PDFs for the knowledge base
└── rag/
    ├── ingest.py     # chunks, embeds, and stores the PDFs
    └── search.py     # similarity search over the vector store
```

## Known limitations

Two things I would fix before this ran against real traffic:

- **Conversation history is process-global.** `chat_history` is a single module
  level list shared by every request, so one customer's messages — and the
  account details in them — leak into the next customer's context. It needs to
  be keyed per customer and persisted alongside the other data.
- **No evaluation harness.** There is no automated way to check whether answers
  stay grounded in the retrieved sources. A fixed question set with expected
  citations, scored on each change, would catch regressions in retrieval quality
  that are otherwise invisible.
