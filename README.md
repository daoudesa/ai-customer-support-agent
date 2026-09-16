# AI Customer Support Agent

A backend service that answers customer support questions with a language
model, grounding every answer in the company's own data rather than the model's
training. Three sources feed each response: the customer's account record,
their order history, and the company policy document.

The goal is an agent that can say *"your order shipped Tuesday, tracking
TRK9400111899"* — and that refuses to invent an answer when the information
isn't there.

Ships with a chat UI and an evaluation suite that scores whether answers stay
grounded in the retrieved sources.

## How it works

A question arrives at `POST /chat` with the customer's email. The service then:

1. **Looks up the customer** in SQLite via SQLAlchemy, returning 404 if the
   account doesn't exist.
2. **Collects their orders** through the `Customer → Order` relationship —
   product, price, status, tracking number, order date.
3. **Retrieves relevant policy text.** The company policy PDF is split into
   1000-character chunks with 200 characters of overlap, embedded with OpenAI
   embeddings, and stored in a persistent Chroma vector database. Each question
   runs a similarity search and pulls the three closest passages.
4. **Loads that customer's conversation history** — the last ten turns, read
   from the database and scoped to their account.
5. **Builds a grounded prompt** from those sources and sends it to the model
   with instructions never to invent information and to escalate when something
   is missing.

The response names which sources it drew on, so a caller can tell whether a
policy passage was actually retrieved or the answer came from the account
record alone.

## Stack

| | |
|---|---|
| API | FastAPI, Pydantic validation |
| Language model | OpenAI |
| Vector store | Chroma, persisted to disk |
| Chunking & embeddings | LangChain, OpenAI embeddings |
| Database | SQLite via SQLAlchemy ORM |
| PDF parsing | pypdf |
| UI | Single-page chat client, no build step |
| Evals | YAML case file + runner over FastAPI's TestClient |

## Running it

Requires Python 3.12 and an OpenAI API key.

```bash
git clone https://github.com/daoudesa/ai-customer-support-agent.git
cd ai-customer-support-agent/backend

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

- **Chat UI** — http://localhost:8000/ui
- **API docs** — http://localhost:8000/docs

### Asking it something

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"email":"john.smith@example.com","question":"Where is my order?"}'
```

```json
{
  "answer": "Your Wireless Headphones order ORD-10001 shipped and is tracking under TRK9400111899.",
  "sources_used": ["customer record", "order history"]
}
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/chat` | ask a question as a given customer |
| `GET` | `/history/{email}` | that customer's conversation so far |
| `DELETE` | `/history/{email}` | start their conversation over |
| `GET` | `/health` | liveness check, does not call the model |

## Evaluations

Grounding is the whole point of the service, so it is tested rather than
assumed. `evals/cases.yaml` holds question/expectation pairs; each case states
what a correct answer must contain and — more importantly — what it must never
contain.

```bash
python -m evals.run            # every case
python -m evals.run --only refund
python -m evals.run -v         # print every answer
```

```
Running 16 cases against the live model…

  [PASS] order-tracking  (1.8s)
  [PASS] refund-window  (1.4s)
  [PASS] no-cross-customer-leak  (2.1s)
  ...

  16/16 passed (100%)
```

The `reject` cases are the ones that matter: they fail the run if the agent
quotes a tracking number for an order that doesn't exist, or lets one
customer's order details appear in another customer's answer. A suite that only
checked for helpful-sounding text would miss both.

Each run calls the live model, so it costs a small amount per execution.

## Sample data

`seed_data.py` creates five fictional customers with seven orders between them,
spanning active, suspended, and multiple membership tiers so the agent's
behaviour can be checked against different account states. All names, emails,
phone numbers, and tracking numbers are invented.

## Project layout

```
backend/
├── main.py           # FastAPI app: /chat, /history, /health
├── models.py         # Customer, Order, Message ORM models
├── database.py       # SQLAlchemy engine and session
├── init_db.py        # creates the database schema
├── seed_data.py      # loads sample customers and orders
├── knowledge/        # source PDFs for the knowledge base
├── static/           # chat UI
├── rag/
│   ├── ingest.py     # chunks, embeds, and stores the PDFs
│   └── search.py     # similarity search over the vector store
└── evals/
    ├── cases.yaml    # evaluation cases
    └── run.py        # scores answers, reports pass/fail
```

## Design notes

**Conversation history is per-customer and persisted.** An earlier version kept
it in a single module-level list shared by every request, which meant one
customer's messages — and the account details quoted in them — were replayed
into the next customer's prompt. History now lives in a `messages` table keyed
to the customer, and `no-cross-customer-leak` in the eval suite is the
regression test for it.

**Turns are written only after a successful answer,** so a failed model call
doesn't leave a dangling question in the history.

**The model is never the only line of defence.** The prompt forbids invention,
but the eval suite verifies it, because prompt instructions are not a
guarantee.
