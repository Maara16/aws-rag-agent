import streamlit as st
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import OllamaLLM

# Page configuration
st.set_page_config(page_title="AWS RAG Agent", layout="wide")
st.title("🤖 AWS RAG Agent Chat")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "qa_chain" not in st.session_state:
    st.session_state.qa_chain = None

if "db_status" not in st.session_state:
    st.session_state.db_status = "Not loaded"

# Load the RAG chain once
@st.cache_resource
def load_rag_chain():
    # Load embeddings
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    persist_directory = "./chroma_db_clean"
    
    # Load vector database
    if os.path.exists(persist_directory):
        st.session_state.db_status = f"Loaded existing vector database from {persist_directory}"
        vector_db = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )
    else:
        st.session_state.db_status = "Vector database not found"
        st.error("Vector database not found. Please run app.py first to create it.")
        st.stop()
    
    # Load LLM
    llm = OllamaLLM(model="llama3.2:1b")
    
    # Create prompt template
    template = """You are an AWS expert assistant. Use the following pieces of context to answer the question. 
If you don't know the answer, just say that you don't know.

Context:
{context}

Question:
{question}"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # Create RAG chain
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
    
    return qa_chain, retriever

# Load the chain
qa_chain, retriever = load_rag_chain()

st.info(st.session_state.db_status)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me anything about AWS..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Retrieve documents for debugging
    with st.chat_message("assistant"):
        with st.spinner("Retrieving context from the vector DB..."):
            retrieved_docs = retriever.invoke(prompt)
            if retrieved_docs:
                st.markdown(f"**Retrieved {len(retrieved_docs)} documents from the vector DB.**")
                for i, doc in enumerate(retrieved_docs):
                    st.markdown(f"**Document {i+1} metadata:** {doc.metadata}")
                    st.markdown(f"{doc.page_content[:400]}...")
            else:
                st.warning("No documents were retrieved for this query.")
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = qa_chain.invoke(prompt)
            st.markdown(response)
    
    # Add assistant message to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
