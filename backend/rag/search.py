from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()


embeddings = OpenAIEmbeddings()


db = Chroma(
    persist_directory="vector_db",
    embedding_function=embeddings
)


def search_company_docs(question):

    results = db.similarity_search(
        question,
        k=3
    )

    context = ""

    for doc in results:
        context += doc.page_content + "\n\n"

    return context