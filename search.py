import streamlit as st
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

st.set_page_config(page_title="AWS Vector DB Viewer", layout="wide")
st.title("🔍 AWS RAG Database Viewer")

# Cache the database connection so it doesn't reload on every keystroke
@st.cache_resource
def get_db():
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    # Make sure this matches the folder name where your full DB is saved
    return Chroma(persist_directory="./chroma_db_clean", embedding_function=embeddings)

vector_db = get_db()

# Create a search bar in the web app
search_term = st.text_input("Search for an AWS Concept (e.g., 'Application Load Balancer'):")

if search_term:
    st.write(f"### Top 5 Matches for '{search_term}'")
    
    # Retrieve the top 5 chunks
    results = vector_db.similarity_search(search_term, k=5)
    
    for i, doc in enumerate(results):
        # Create a nice visual card for each chunk
        with st.expander(f"Result {i+1}: {doc.metadata.get('slide_title', 'Unknown Slide')}", expanded=True):
            st.markdown(f"**Text Content:**\n\n{doc.page_content}")
            st.caption(f"Metadata Tags: {doc.metadata}")