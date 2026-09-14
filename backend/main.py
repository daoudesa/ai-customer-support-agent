from fastapi import FastAPI
from openai import OpenAI
from dotenv import load_dotenv
from database import SessionLocal
from models import Customer

from rag.search import search_company_docs

import os


load_dotenv()


app = FastAPI()


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# Simple conversation memory
chat_history = []



@app.get("/")
def home():

    return {
        "message": "AI Customer Support Agent Running"
    }



@app.post("/chat")
def chat(email: str, question: str):

    db = SessionLocal()

    customer = db.query(Customer).filter(
        Customer.email == email
    ).first()


    if not customer:
        db.close()
        return {
            "answer": "I could not find your account."
        }


    customer_context = f"""
Customer Information:

Name:
{customer.first_name} {customer.last_name}

Email:
{customer.email}

Phone:
{customer.phone}

Address:
{customer.street}
{customer.city}, {customer.state} {customer.zip_code}

Account Status:
{customer.account_status}

Membership:
{customer.membership_level}

Last Login:
{customer.last_login}
"""


    order_context = ""

    for order in customer.orders:

        order_context += f"""

Order Number:
{order.order_number}

Product:
{order.product}

Price:
${order.price}

Status:
{order.status}

Tracking:
{order.tracking_number}

Order Date:
{order.order_date}

"""


    # Get company docs
    company_context = search_company_docs(question)


    chat_history.append({
        "role": "user",
        "content": question
    })


    response = client.responses.create(

        model="gpt-5-mini",

        instructions=f"""
You are a professional customer support agent.

Use ONLY the information provided.

Customer Information:

{customer_context}


Customer Orders:

{order_context}


Company Knowledge:

{company_context}


Conversation History:

{chat_history}


Rules:
- Never invent information.
- Never guess order details.
- If information is missing, say you need to escalate.
- Be friendly and concise.
""",

        input=question
    )


    answer = response.output_text


    chat_history.append({
        "role": "assistant",
        "content": answer
    })


    db.close()


    return {
        "answer": answer
    }