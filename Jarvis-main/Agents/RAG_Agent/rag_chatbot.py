## PDF RAG Agent - Interactive Q&A System
## run pip install -r requirements.txt to install the required packages

import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

import pdfplumber
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from langchain_core.runnables import RunnablePassthrough
import ollama

import ollama

def create_vector_db():
    """Create embeddings and vector database once"""
    doc_path = "./Data/BOI.pdf"
    
    print("Loading PDF...")
    documents = []
    with pdfplumber.open(doc_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                doc = Document(
                    page_content=text,
                    metadata={"page": page_num + 1, "source": doc_path}
                )
                documents.append(doc)
    
    print("Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300)
    chunks = text_splitter.split_documents(documents)
    
    print("Creating embeddings and vector database...")
    ollama.pull("nomic-embed-text")
    vector_db = FAISS.from_documents(
        documents=chunks,
        embedding=OllamaEmbeddings(model="nomic-embed-text"),
    )
    print("Vector database ready!")
    return vector_db

def setup_rag_chain(vector_db):
    """Setup RAG chain for question answering"""
    retriever = vector_db.as_retriever()
    
    template = """Answer the question based ONLY on the following context:
{context}
Question: {question}
"""
    
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOllama(model="llama3.1:8b")
    
    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain

def main():
    """Main interactive loop"""
    # Create embeddings once
    vector_db = create_vector_db()
    chain = setup_rag_chain(vector_db)
    
    print("\n" + "="*50)
    print("PDF RAG Agent Ready! Ask questions about the document.")
    print("Type 'quit' or 'exit' to stop.")
    print("="*50 + "\n")
    
    while True:
        question = input("Your question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if not question:
            continue
        
        print("\nThinking...")
        try:
            answer = chain.invoke(question)
            print(f"\nAnswer: {answer}\n")
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()

def query_documents(question: str) -> str:
    """Interface function to answer questions from active document via StudyEngine RAG."""
    from Agents.Study_Agent.study_engine import answer_document_query
    return answer_document_query(question)