import re
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import OllamaLLM

def clean_and_tag_page(text):
    """Removes unwanted noise and extracts basic metadata."""
    # 1. Strip repetitive headers, footers, and copyright notices
    text = re.sub(r'NOT FOR DISTRIBUTION.*?www\.datacumulus\.com', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'© Stephane Maarek', '', text, flags=re.IGNORECASE)
    
    # 2. Consolidate broken sentences (removes single line breaks, keeps double for paragraphs)
    # This prevents sentences from being chopped in half by PDF formatting
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    
    # Clean up any extra white spaces left behind
    text = text.strip()
    
    # 3. Extract the slide title (usually the first line of the clean text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    slide_title = lines[0] if lines else "Unknown Topic"
    
    return text, slide_title

print("1. Loading the AWS PDF...")
loader = PyPDFLoader("AWS Certified Solutions Architect Slides v47.pdf")
docs = loader.load()

print("2. Cleaning data and adding metadata...")
cleaned_docs = []
for doc in docs:
    # Pass the raw PDF text through our cleaning function
    clean_text, title = clean_and_tag_page(doc.page_content)
    
    # Update the document with the clean text and new metadata
    doc.page_content = clean_text
    doc.metadata['slide_title'] = title
    
    # Add a simple topic tag based on keywords for Step 3 (Metadata Tagging)
    if "EC2" in clean_text: doc.metadata['service'] = 'EC2'
    elif "S3" in clean_text: doc.metadata['service'] = 'S3'
    elif "RDS" in clean_text or "Database" in clean_text: doc.metadata['service'] = 'Database'
    else: doc.metadata['service'] = 'General AWS'
    
    cleaned_docs.append(doc)

print("3. Chopping the text into semantic chunks...")
# We increased the chunk size to capture whole concepts and added a 15% overlap 
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800, 
    chunk_overlap=120,
    separators=["\n\n", "\n", ".", " "] # Tries to split at paragraphs first, then sentences
)
chunks = text_splitter.split_documents(cleaned_docs)

print("4. Creating the local vector database...")
# Note: If you run this multiple times, delete the "chroma_db" folder first 
# to prevent duplicates, or use a new directory name.
embeddings = OllamaEmbeddings(model="nomic-embed-text")
persist_directory = "./chroma_db_clean"

# Check if the vector database already exists
if os.path.exists(persist_directory):
    print(f"Vector database already exists at {persist_directory}. Loading from disk...")
    vector_db = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
else:
    print(f"Creating new vector database at {persist_directory}...")
    vector_db = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings, 
        persist_directory=persist_directory
    )

print("5. Connecting to the Local LLM...")
llm = OllamaLLM(model="llama3.2:1b")

print("6. Building the RAG Agent...")
# Create a prompt template for the chain
template = """You are an AWS expert assistant. Use the following pieces of context to answer the question. 
If you don't know the answer, just say that you don't know.

Context:
{context}

Question:
{question}"""

prompt = ChatPromptTemplate.from_template(template)

# Create a simple RAG chain using LCEL (LangChain Expression Language)
retriever = vector_db.as_retriever(search_kwargs={"k": 4})

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

qa_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

# Test it out!
print("\n=========================================\n")
question = "Explain the difference between EBS General Purpose SSD (gp2/gp3) and Provisioned IOPS SSD (io1/io2) volumes."
print(f"Question: {question}\n")

# Debug: Check what documents are being retrieved
print("Debug: Retrieving relevant documents...\n")
retrieved_docs = retriever.invoke(question)
print(f"Retrieved {len(retrieved_docs)} documents:")
for i, doc in enumerate(retrieved_docs):
    print(f"\nDocument {i+1} (Score/Distance):")
    print(f"Content preview: {doc.page_content[:200]}...")
    print(f"Metadata: {doc.metadata}")

print("\nAgent is thinking...\n")
response = qa_chain.invoke(question)

print(f"Answer:\n{response}")