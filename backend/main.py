"""FastAPI service: customer support answers grounded in company data.

Every answer is built from three sources — the customer's account record, their
order history, and the passages retrieved from the company policy PDF. The
model is instructed to use only what it is given and to escalate rather than
guess.
"""
import logging
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Customer, Message
from rag.search import search_company_docs

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
# How many past turns to replay. Enough for a follow-up like "what about the
# other one?" without letting the prompt grow without bound.
HISTORY_TURNS = 10

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Copy .env.example to backend/.env and add your key."
    )

client = OpenAI(api_key=_api_key)

app = FastAPI(
    title="AI Customer Support Agent",
    description="Answers customer questions grounded in account records, "
                "order history, and company policy.",
    version="1.0.0",
)

# The bundled UI is served from the same origin, but allow others so the API
# can be called from a separately hosted front end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    email: EmailStr
    question: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    sources_used: list[str]


def _customer_context(customer: Customer) -> str:
    return f"""Name: {customer.first_name} {customer.last_name}
Email: {customer.email}
Phone: {customer.phone}
Address: {customer.street}, {customer.city}, {customer.state} {customer.zip_code}
Account status: {customer.account_status}
Membership: {customer.membership_level}
Last login: {customer.last_login}"""


def _order_context(customer: Customer) -> str:
    if not customer.orders:
        return "This customer has no orders on file."

    lines = []
    for order in customer.orders:
        lines.append(
            f"- Order {order.order_number}: {order.product}, ${order.price}, "
            f"status {order.status}, tracking {order.tracking_number}, "
            f"ordered {order.order_date}"
        )
    return "\n".join(lines)


def _history_context(customer: Customer) -> str:
    """The last few turns of THIS customer's conversation, oldest first."""
    recent = customer.messages[-HISTORY_TURNS:]
    if not recent:
        return "No previous messages in this conversation."
    return "\n".join(f"{m.role}: {m.content}" for m in recent)


@app.get("/health")
def health():
    """Liveness check that does not call the model."""
    return {"status": "ok", "model": MODEL}


@app.get("/")
def home():
    return {"message": "AI Customer Support Agent running. See /docs for the API."}


@app.get("/history/{email}")
def history(email: str, db: Session = Depends(get_db)):
    """Everything this customer has said, and every answer they were given."""
    customer = db.query(Customer).filter(Customer.email == email).first()
    if not customer:
        raise HTTPException(status_code=404, detail="No account found for that email.")

    return {
        "email": customer.email,
        "messages": [
            {"role": m.role, "content": m.content, "at": m.created_at}
            for m in customer.messages
        ],
    }


@app.delete("/history/{email}")
def clear_history(email: str, db: Session = Depends(get_db)):
    """Start the conversation over for one customer."""
    customer = db.query(Customer).filter(Customer.email == email).first()
    if not customer:
        raise HTTPException(status_code=404, detail="No account found for that email.")

    removed = len(customer.messages)
    customer.messages.clear()
    db.commit()
    return {"cleared": removed}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.email == req.email).first()
    if not customer:
        raise HTTPException(status_code=404, detail="No account found for that email.")

    passages = search_company_docs(req.question)

    sources = ["customer record", "order history"]
    if passages.strip():
        sources.append("company policy")

    instructions = f"""You are a customer support agent for Acme Software.

Answer using ONLY the information below. If the answer is not there, say you
need to escalate to a human agent — never guess, and never invent an order
number, tracking number, date, or price.

CUSTOMER RECORD
{_customer_context(customer)}

ORDER HISTORY
{_order_context(customer)}

COMPANY POLICY (retrieved passages)
{passages or "No relevant policy passages found for this question."}

EARLIER IN THIS CONVERSATION
{_history_context(customer)}

Be friendly and concise."""

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=req.question,
        )
        answer = response.output_text
    except OpenAIError as exc:
        log.error("model call failed for %s: %s", req.email, exc)
        raise HTTPException(
            status_code=502,
            detail="The assistant is unavailable right now. Please try again.",
        )

    # Persist the turn only after a successful answer, so a failed call does
    # not leave a dangling question in the history.
    db.add(Message(customer_id=customer.id, role="user", content=req.question))
    db.add(Message(customer_id=customer.id, role="assistant", content=answer))
    db.commit()

    return ChatResponse(answer=answer, sources_used=sources)


# Serve the chat UI at / if it has been built. Mounted last so it cannot
# shadow the API routes above.
_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/ui", StaticFiles(directory=_static, html=True), name="ui")
