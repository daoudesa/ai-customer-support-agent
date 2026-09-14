from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os

load_dotenv()


def create_knowledge_base():

    documents = []

    folder = "knowledge"

    for filename in os.listdir(folder):

        if filename.endswith(".pdf"):

            print("Loading:", filename)

            loader = PyPDFLoader(
                os.path.join(folder, filename)
            )

            documents.extend(loader.load())


    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )


    chunks = splitter.split_documents(documents)


    embeddings = OpenAIEmbeddings()


    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="vector_db"
    )


    print("Knowledge base created!")
    print("Chunks:", len(chunks))


if __name__ == "__main__":
    create_knowledge_base()