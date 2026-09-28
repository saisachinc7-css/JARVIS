## 1. Ingest PDF Files
# 2. Extract Text from PDF Files and split into small chunks
# 3. Send the chunks to the embedding model
# 4. Save the embeddings to a vector database
# 5. Perform similarity search on the vector database to find similar documents
# 6. retrieve the similar documents and present them to the user
## run pip install -r requirements.txt to install the required packages

import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

import pdfplumber
from langchain_core.documents import Document

doc_path = "./Data/BOI.pdf"
model = "llama3.1:8b"

# Local PDF file uploads
if doc_path:
    # Use pdfplumber to extract text
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
    
    data = documents
    print("done loading....")
else:
    print("Upload a PDF file")

# Preview first page
if data:
    content = data[0].page_content
    print(content[:100])
else:
    print("No content extracted from PDF")

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Split and chunk
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300)
chunks = text_splitter.split_documents(data)
print("done splitting....")

# print(f"Number of chunks: {len(chunks)}") theese are to check the embedding
# print(f"Example chunk: {chunks[0]}")

# ===== Add to vector database ===
import ollama

ollama.pull("nomic-embed-text")

vector_db = FAISS.from_documents(
    documents=chunks,
    embedding=OllamaEmbeddings(model="nomic-embed-text"),
)
print("done adding to vector database....")


## === Retrieval ===
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from langchain_ollama import ChatOllama

from langchain_core.runnables import RunnablePassthrough
# MultiQueryRetriever not available - using basic retriever
retriever = vector_db.as_retriever()


# RAG prompt
template = """Answer the question based ONLY on the following context:
{context}
Question: {question}
"""

prompt = ChatPromptTemplate.from_template(template)

llm = ChatOllama(model=model)

chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)


res = chain.invoke("what are the policies mention ")
# res = chain.invoke(
#     "what are the main points as a business owner I should be aware of?"
# )
# res = chain.invoke("how to report BOI?")

print(res)