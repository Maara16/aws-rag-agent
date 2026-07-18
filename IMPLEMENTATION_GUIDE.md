# 🎯 Implementation Guide: File-by-File

## Current Status ✅
- Project structure: Ready
- PDFs ingested into Chroma: Ready
- Vector search working: Ready
- SQLite database: Ready
- Configuration: Ready

## What's Missing (Phase 2)
- [ ] LLM integration (wrapper for Ollama/Claude)
- [ ] RAG Agent
- [ ] Quiz Agent
- [ ] Cheatsheet Agent
- [ ] Message Router
- [ ] FastAPI app + Twilio webhook

---

## 📋 Build Order (Dependency Chain)

```
1. src/llm_client.py          ← Start HERE (dependency for agents)
                               ↓
2. src/agents/rag_agent.py    ← Build next (core agent)
   src/agents/quiz_agent.py   ← Build together
   src/agents/cheatsheet_agent.py ← Build together
                               ↓
3. src/agents/router.py       ← Route messages to agents
                               ↓
4. src/main.py                ← FastAPI app + Twilio webhook
                               ↓
5. scripts/test_webhook.py    ← Test locally
```

---

## File 1: `src/llm_client.py` ⭐⭐⭐ START HERE

**Purpose**: Wrapper for LLM (Ollama or Claude API)  
**Dependencies**: `src/config.py` (already done)  
**Time**: 30-45 min  
**Difficulty**: Intermediate  

### Step 1: Create the file
```bash
touch src/llm_client.py
```

### Step 2: What to implement

```python
"""
LLM client wrapper supporting Ollama (local) and Claude (API).
Unified interface for both providers.
"""

import logging
from typing import Optional
from abc import ABC, abstractmethod
from src.config import Config

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Base class for LLM clients."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        pass


class OllamaClient(LLMClient):
    """Ollama client for local LLM inference."""
    
    def __init__(
        self,
        api_url: str = None,
        model: str = None,
        temperature: float = 0.3,
        max_tokens: int = 500
    ):
        self.api_url = api_url or Config.OLLAMA_API_URL
        self.model = model or Config.OLLAMA_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        logger.info(f"Initialized Ollama client: {self.model} at {self.api_url}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Ollama.
        
        Args:
            prompt: Input prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
        
        Returns:
            Generated text
        """
        import ollama
        
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens)
                }
            )
            return response["response"].strip()
        
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise


class ClaudeClient(LLMClient):
    """Claude API client."""
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.3,
        max_tokens: int = 500
    ):
        self.api_key = api_key or Config.ANTHROPIC_API_KEY
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        from anthropic import Anthropic
        self.client = Anthropic(api_key=self.api_key)
        
        logger.info(f"Initialized Claude client: {self.model}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Claude API.
        
        Args:
            prompt: Input prompt
            temperature: Override default
            max_tokens: Override default
        
        Returns:
            Generated text
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text.strip()
        
        except Exception as e:
            logger.error(f"Claude generation error: {e}")
            raise


def get_llm_client() -> LLMClient:
    """
    Factory function to get LLM client based on config.
    
    Returns:
        Configured LLM client (Ollama or Claude)
    """
    if Config.LLM_PROVIDER == "ollama":
        return OllamaClient()
    elif Config.LLM_PROVIDER == "claude":
        return ClaudeClient()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {Config.LLM_PROVIDER}")
```

### Step 3: Test locally
```python
# Create test_llm.py
import asyncio
from src.llm_client import get_llm_client

async def test():
    llm = get_llm_client()
    
    # Test 1: Simple generation
    response = await llm.generate("What is EC2 in AWS?")
    print("Test 1 - Simple generation:")
    print(response)
    print()
    
    # Test 2: With temperature override
    response = await llm.generate(
        "Generate a creative question about S3",
        temperature=0.8
    )
    print("Test 2 - Creative generation:")
    print(response)

asyncio.run(test())
```

**Expected output**:
```
Test 1 - Simple generation:
EC2 stands for Elastic Compute Cloud. It's AWS's virtual server service...

Test 2 - Creative generation:
Why do some people call S3 the "digital vault of AWS"?
```

### Key Concepts You'll Learn
- ✅ Abstract base classes (ABC pattern)
- ✅ Multiple implementations (Ollama vs Claude)
- ✅ Factory pattern (get_llm_client)
- ✅ Async functions (async/await)
- ✅ Error handling

---

## File 2: `src/agents/__init__.py`

**Purpose**: Package initialization for agents  
**Time**: 2 min  

```python
"""Agents for handling different user intents."""

from src.agents.rag_agent import RAGAgent
from src.agents.quiz_agent import QuizAgent
from src.agents.cheatsheet_agent import CheatsheetAgent
from src.agents.router import MessageRouter

__all__ = [
    "RAGAgent",
    "QuizAgent", 
    "CheatsheetAgent",
    "MessageRouter"
]
```

---

## File 3: `src/agents/rag_agent.py` ⭐⭐⭐⭐

**Purpose**: Explain AWS concepts using retrieval-augmented generation  
**Dependencies**: `src/llm_client.py`, `src/vector_store.py`, `src/database.py`  
**Time**: 1-1.5 hours  
**Difficulty**: Advanced  

### What to implement

```python
"""
RAG Agent: Retrieve relevant documentation and generate explanations.
"""

import logging
import time
from typing import Optional, List, Tuple
from src.llm_client import LLMClient
from src.vector_store import VectorStore
from src.database import Database
from src.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


class RAGAgent:
    """
    Retrieval-Augmented Generation Agent.
    
    Workflow:
    1. User asks: "Explain EC2 pricing"
    2. Retrieve: Find top-5 relevant chunks from Chroma
    3. Rank: Re-rank by semantic + keyword relevance
    4. Augment: Add chunks to LLM prompt as context
    5. Generate: LLM generates answer based on context
    6. Format: Return WhatsApp-friendly response
    """
    
    SYSTEM_PROMPT = """You are an AWS Solutions Architect expert. 
Your task is to answer questions about AWS services based on provided documentation.

Guidelines:
- Be concise and clear (for WhatsApp)
- Use bullet points for lists
- Always cite the source when possible
- If you're unsure, say so - don't hallucinate
- Use technical language but explain terms"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        llm_client: LLMClient,
        db: Database,
        retrieval_k: int = 5,
        temperature: float = 0.3
    ):
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.db = db
        self.retrieval_k = retrieval_k
        self.temperature = temperature
    
    async def answer(
        self,
        user_id: str,
        question: str,
        max_response_length: int = 2000
    ) -> str:
        """
        Answer a user's question using RAG.
        
        Args:
            user_id: Phone number or user identifier
            question: User's question
            max_response_length: Max chars in response (WhatsApp limit ~4096)
        
        Returns:
            Generated answer
        """
        logger.info(f"RAG Agent: Question from {user_id}: {question}")
        
        start_time = time.time()
        
        try:
            # Step 1: Retrieve
            logger.info("Step 1: Retrieving relevant chunks...")
            chunks = self._retrieve(question)
            
            if not chunks:
                response = "Sorry, I couldn't find relevant documentation for that question. Try rephrasing?"
                logger.warning("No chunks retrieved")
            else:
                # Step 2: Rank (optional but improves quality)
                logger.info("Step 2: Re-ranking chunks...")
                ranked_chunks = self._rank_chunks(question, chunks)
                
                # Step 3: Augment
                logger.info("Step 3: Building context...")
                context = self._build_context(ranked_chunks)
                
                # Step 4: Generate
                logger.info("Step 4: Generating answer with LLM...")
                response = await self._generate(question, context)
                
                # Step 5: Format
                response = self._format_response(response)
                
                # Ensure length limit for WhatsApp
                if len(response) > max_response_length:
                    response = response[:max_response_length] + "\n...(truncated)"
            
            # Log interaction
            elapsed_time = (time.time() - start_time) * 1000  # ms
            self.db.log_interaction(
                phone_number=user_id,
                mode="rag",
                user_input=question,
                agent_output=response,
                response_time_ms=elapsed_time
            )
            
            logger.info(f"RAG Agent: Responded in {elapsed_time:.1f}ms")
            return response
        
        except Exception as e:
            logger.error(f"RAG Agent error: {e}")
            return f"Sorry, I encountered an error: {str(e)[:100]}"
    
    def _retrieve(self, question: str) -> List[Tuple[str, float, dict]]:
        """
        Retrieve top-k relevant chunks.
        
        Returns:
            List of (text, similarity_score, metadata)
        """
        results = self.vector_store.search(question, k=self.retrieval_k)
        logger.info(f"Retrieved {len(results)} chunks")
        
        for i, (text, distance, metadata) in enumerate(results, 1):
            logger.info(f"  Chunk {i}: distance={distance:.3f}, source={metadata.get('source')}")
        
        return results
    
    def _rank_chunks(
        self,
        question: str,
        chunks: List[Tuple[str, float, dict]]
    ) -> List[Tuple[str, float, dict]]:
        """
        Re-rank chunks by hybrid score (semantic + BM25).
        For now, just return top-3 by original ranking.
        """
        # TODO: Implement hybrid ranking
        # For now, return top-3 results
        return chunks[:3]
    
    def _build_context(self, chunks: List[Tuple[str, float, dict]]) -> str:
        """
        Format retrieved chunks into context string.
        """
        context_parts = []
        
        for i, (text, distance, metadata) in enumerate(chunks, 1):
            source_info = ""
            if metadata.get("source") == "course_slides":
                source_info = f"[Slides - Page {metadata.get('page', '?')}]"
            elif metadata.get("source") == "cheatsheet":
                source_info = f"[Cheatsheet - {metadata.get('domain', 'General')}]"
            
            formatted_chunk = f"{source_info}\n{text}\n"
            context_parts.append(formatted_chunk)
        
        return "\n---\n".join(context_parts)
    
    async def _generate(self, question: str, context: str) -> str:
        """
        Generate answer using LLM with context.
        """
        prompt = f"""{self.SYSTEM_PROMPT}

Documentation Context:
{context}

Question: {question}

Answer:"""
        
        response = await self.llm_client.generate(
            prompt,
            temperature=self.temperature,
            max_tokens=500
        )
        
        return response
    
    def _format_response(self, response: str) -> str:
        """
        Format response for WhatsApp (add line breaks, emojis, etc).
        """
        # Basic formatting
        response = response.strip()
        
        # Add emojis for AWS services
        replacements = {
            "EC2": "🖥️ EC2",
            "S3": "📦 S3",
            "RDS": "🗄️ RDS",
            "DynamoDB": "⚡ DynamoDB",
            "Lambda": "⚙️ Lambda",
            "VPC": "🌐 VPC",
            "IAM": "🔐 IAM",
        }
        
        for old, new in replacements.items():
            response = response.replace(old, new)
        
        return response
```

### Step 3: Test locally
```python
# Create test_rag_agent.py
import asyncio
from src.vector_store import get_vector_store
from src.llm_client import get_llm_client
from src.database import get_db
from src.agents.rag_agent import RAGAgent

async def test():
    # Initialize
    vector_store = get_vector_store()
    llm_client = get_llm_client()
    db = get_db()
    
    # Create agent
    rag = RAGAgent(vector_store, llm_client, db)
    
    # Test questions
    questions = [
        "What is EC2?",
        "Explain RDS Multi-AZ",
        "How does S3 versioning work?",
    ]
    
    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")
        
        answer = await rag.answer("+1234567890", q)
        print(f"A: {answer}")

asyncio.run(test())
```

### Key Concepts You'll Learn
- ✅ RAG pipeline architecture
- ✅ Prompt engineering
- ✅ Context augmentation
- ✅ Response formatting
- ✅ Error handling in agents

---

## File 4: `src/agents/quiz_agent.py` ⭐⭐⭐⭐

**Purpose**: Generate quiz questions and track user progress  
**Dependencies**: `src/llm_client.py`, `src/vector_store.py`, `src/database.py`  
**Time**: 1.5-2 hours  
**Difficulty**: Advanced  

### What to implement

```python
"""
Quiz Agent: Generate multiple-choice questions and track progress.
"""

import logging
import time
import json
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from src.llm_client import LLMClient
from src.vector_store import VectorStore
from src.database import Database

logger = logging.getLogger(__name__)


class QuizAgent:
    """
    Quiz Agent: Generate AWS questions and track user progress.
    
    Features:
    - Generate multiple-choice questions from course material
    - Track quiz attempts in SQLite
    - Calculate accuracy per domain
    - Identify weak areas
    - Provide progressive difficulty
    """
    
    QUESTION_GENERATION_PROMPT = """You are an AWS Solutions Architect exam expert.
Generate a multiple-choice question based on the provided AWS documentation.

Rules:
1. Question should test understanding (not just memorization)
2. All options should be plausible
3. Only ONE correct answer
4. Include explanation in your response

Format your response EXACTLY like this:
QUESTION: Your question here?
A) Option A
B) Option B
C) Option C
D) Option D
CORRECT: A
EXPLANATION: Why A is correct and others are wrong.

Documentation:
{context}

AWS Domain: {domain}
Generate a question about this domain:"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        llm_client: LLMClient,
        db: Database,
        questions_per_session: int = 5
    ):
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.db = db
        self.questions_per_session = questions_per_session
    
    async def start_quiz(
        self,
        user_id: str,
        domain: str = None
    ) -> Tuple[str, Dict]:
        """
        Start a quiz session.
        
        Args:
            user_id: Phone number
            domain: AWS domain (e.g., "EC2", "S3", "RDS")
        
        Returns:
            (first_question_text, session_state)
        """
        logger.info(f"Quiz Agent: Starting quiz for {user_id}, domain={domain}")
        
        # Get or create user
        self.db.get_or_create_user(user_id)
        
        # Generate questions
        questions = []
        for i in range(self.questions_per_session):
            q = await self._generate_question(domain or self._random_domain())
            if q:
                questions.append(q)
        
        if not questions:
            return "Sorry, couldn't generate questions. Try again?", {}
        
        # Create session state
        session_state = {
            "user_id": user_id,
            "domain": domain,
            "questions": questions,
            "current_index": 0,
            "answers": [],
            "start_time": datetime.now().isoformat(),
            "session_id": None
        }
        
        # Format first question
        q1 = questions[0]
        question_text = self._format_question(q1, current=1, total=len(questions))
        
        # Store session (you'll need to implement session storage)
        # For now, return state for client to manage
        
        return question_text, session_state
    
    async def check_answer(
        self,
        user_id: str,
        session_state: Dict,
        user_answer: str
    ) -> Tuple[str, Optional[Dict]]:
        """
        Check user's answer and generate next question or end quiz.
        
        Args:
            user_id: Phone number
            session_state: Quiz session state
            user_answer: User's answer (A, B, C, or D)
        
        Returns:
            (response_text, updated_session_state or None if quiz ended)
        """
        current_idx = session_state["current_index"]
        current_q = session_state["questions"][current_idx]
        
        # Validate answer
        user_answer = user_answer.strip().upper()
        if user_answer not in ["A", "B", "C", "D"]:
            return "Please answer A, B, C, or D", session_state
        
        # Check correctness
        correct_answer = current_q["correct"]
        is_correct = user_answer == correct_answer
        
        # Record attempt
        self.db.record_quiz_attempt(
            phone_number=user_id,
            domain=session_state["domain"] or "General",
            question_number=current_idx + 1,
            question_text=current_q["question"],
            correct_answer=correct_answer,
            user_answer=user_answer,
            is_correct=is_correct,
            time_spent_seconds=10  # TODO: track actual time
        )
        
        # Build response
        result = "✅ Correct!" if is_correct else f"❌ Incorrect. Correct answer: {correct_answer}"
        response = f"{result}\n\n{current_q['explanation']}\n\n"
        
        # Check if quiz ended
        if current_idx + 1 >= len(session_state["questions"]):
            # Quiz ended - calculate score
            score = sum(1 for q, a in zip(session_state["questions"], session_state["answers"]) 
                       if a == q["correct"])
            total = len(session_state["questions"])
            percentage = 100 * score / total
            
            # Record session
            self.db.create_quiz_session(
                phone_number=user_id,
                domain=session_state["domain"],
                num_questions=total,
                score=score,
                total_time_seconds=60  # TODO: calculate
            )
            
            # Get weak areas
            weak_domains = self.db.get_weak_domains(user_id)
            weak_text = ""
            if weak_domains:
                weak_text = f"\n\nWeak areas to review: {', '.join(weak_domains)}"
            
            response += f"📊 Quiz Complete!\nScore: {score}/{total} ({percentage:.0f}%){weak_text}"
            
            return response, None  # None signals quiz ended
        
        # Generate next question
        session_state["current_index"] += 1
        session_state["answers"].append(user_answer)
        
        next_q = session_state["questions"][session_state["current_index"]]
        question_text = self._format_question(
            next_q,
            current=session_state["current_index"] + 1,
            total=len(session_state["questions"])
        )
        
        response += question_text
        return response, session_state
    
    async def _generate_question(self, domain: str = None) -> Optional[Dict]:
        """
        Generate a single multiple-choice question.
        
        Returns:
            Dict with keys: question, options, correct, explanation
        """
        try:
            # Retrieve relevant chunks for domain
            search_query = f"AWS {domain}" if domain else "AWS services architecture"
            chunks = self.vector_store.search(search_query, k=3)
            
            if not chunks:
                logger.warning(f"No chunks found for domain: {domain}")
                return None
            
            # Build context from chunks
            context = "\n\n".join([chunk[0] for chunk in chunks])
            
            # Generate question
            prompt = self.QUESTION_GENERATION_PROMPT.format(
                context=context,
                domain=domain or "AWS General Knowledge"
            )
            
            response = await self.llm_client.generate(prompt, max_tokens=800)
            
            # Parse response
            question_dict = self._parse_question_response(response)
            
            if question_dict:
                logger.info(f"Generated question for domain: {domain}")
                return question_dict
            else:
                logger.warning("Failed to parse LLM response as question")
                return None
        
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            return None
    
    def _parse_question_response(self, response: str) -> Optional[Dict]:
        """
        Parse LLM response into question dict.
        
        Expected format:
        QUESTION: ...
        A) ...
        B) ...
        C) ...
        D) ...
        CORRECT: A
        EXPLANATION: ...
        """
        try:
            lines = response.strip().split("\n")
            
            question = None
            options = {}
            correct = None
            explanation = None
            
            for i, line in enumerate(lines):
                if line.startswith("QUESTION:"):
                    question = line.replace("QUESTION:", "").strip()
                elif line.startswith("CORRECT:"):
                    correct = line.replace("CORRECT:", "").strip()
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
                elif line and line[0] in "ABCD" and ")" in line:
                    option = line[0]
                    text = line.split(")", 1)[1].strip()
                    options[option] = text
            
            if question and len(options) == 4 and correct and explanation:
                return {
                    "question": question,
                    "options": options,
                    "correct": correct,
                    "explanation": explanation
                }
        
        except Exception as e:
            logger.error(f"Error parsing question response: {e}")
        
        return None
    
    def _format_question(self, question_dict: Dict, current: int, total: int) -> str:
        """Format question for WhatsApp display."""
        q = question_dict["question"]
        opts = question_dict["options"]
        
        formatted = f"""
📝 Question {current}/{total}

{q}

A) {opts.get('A', '?')}
B) {opts.get('B', '?')}
C) {opts.get('C', '?')}
D) {opts.get('D', '?')}

Reply with A, B, C, or D"""
        
        return formatted.strip()
    
    def _random_domain(self) -> str:
        """Return a random AWS domain."""
        domains = ["EC2", "S3", "RDS", "DynamoDB", "Lambda", "VPC", "IAM", "CloudFormation"]
        import random
        return random.choice(domains)
```

### Key Concepts You'll Learn
- ✅ Multi-turn conversation management
- ✅ Session state tracking
- ✅ LLM output parsing
- ✅ Progress tracking
- ✅ Analytics queries

---

## File 5: `src/agents/cheatsheet_agent.py` ⭐⭐

**Purpose**: Fast lookup in cheatsheet  
**Dependencies**: `src/vector_store.py`, `src/database.py`  
**Time**: 30 min  
**Difficulty**: Beginner  

```python
"""
Cheatsheet Agent: Fast lookup of key facts from cheatsheet.
"""

import logging
from typing import Optional
from src.vector_store import VectorStore
from src.database import Database

logger = logging.getLogger(__name__)


class CheatsheetAgent:
    """
    Quick lookup agent for cheatsheet.
    Returns concise, bullet-point answers.
    """
    
    def __init__(self, vector_store: VectorStore, db: Database):
        self.vector_store = vector_store
        self.db = db
    
    async def lookup(
        self,
        user_id: str,
        query: str,
        max_length: int = 500
    ) -> str:
        """
        Quick lookup in cheatsheet.
        
        Args:
            user_id: Phone number
            query: What to look up
            max_length: Max response length
        
        Returns:
            Quick answer from cheatsheet
        """
        logger.info(f"Cheatsheet Agent: Lookup '{query}' for {user_id}")
        
        # Search cheatsheet only
        results = self.vector_store.search(
            query,
            k=3,
            where={"source": "cheatsheet"}  # Filter for cheatsheet
        )
        
        if not results:
            return "Not found in cheatsheet. Try 'Explain' for more details."
        
        # Return first result (best match)
        answer = results[0][0]
        
        # Truncate if too long
        if len(answer) > max_length:
            answer = answer[:max_length] + "\n...(see docs for details)"
        
        # Log
        self.db.log_interaction(
            phone_number=user_id,
            mode="cheatsheet",
            user_input=query,
            agent_output=answer
        )
        
        return answer
```

---

## File 6: `src/agents/router.py` ⭐⭐⭐

**Purpose**: Route user messages to correct agent  
**Time**: 45 min  
**Difficulty**: Intermediate  

```python
"""
Message Router: Detect user intent and route to correct agent.
"""

import logging
import re
from typing import Tuple, Optional
from src.agents.rag_agent import RAGAgent
from src.agents.quiz_agent import QuizAgent
from src.agents.cheatsheet_agent import CheatsheetAgent
from src.database import Database

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Route user messages to appropriate agent based on intent.
    """
    
    def __init__(
        self,
        rag_agent: RAGAgent,
        quiz_agent: QuizAgent,
        cheatsheet_agent: CheatsheetAgent,
        db: Database
    ):
        self.rag_agent = rag_agent
        self.quiz_agent = quiz_agent
        self.cheatsheet_agent = cheatsheet_agent
        self.db = db
    
    async def route_message(
        self,
        user_id: str,
        message: str
    ) -> str:
        """
        Route message to correct agent.
        
        Intent patterns:
        - "Explain ..." or "What is ..." or "Tell me about ..." → RAG
        - "Quiz on ..." or "Give me questions on ..." → Quiz
        - "Quick: ..." or "Quick facts about ..." → Cheatsheet
        - Random message → Suggest options
        """
        message_lower = message.lower().strip()
        
        logger.info(f"Router: Processing message from {user_id}: {message[:50]}...")
        
        # Pattern 1: Quiz intent
        if self._matches_quiz_intent(message_lower):
            domain = self._extract_domain(message_lower)
            logger.info(f"Routing to Quiz Agent (domain: {domain})")
            first_q, session_state = await self.quiz_agent.start_quiz(user_id, domain)
            
            # TODO: Store session_state in database/cache
            # For now, return first question
            return first_q
        
        # Pattern 2: Cheatsheet intent
        elif self._matches_cheatsheet_intent(message_lower):
            query = message_lower.replace("quick:", "").replace("quick facts", "").strip()
            logger.info(f"Routing to Cheatsheet Agent: {query}")
            return await self.cheatsheet_agent.lookup(user_id, query)
        
        # Pattern 3: RAG intent (default)
        elif self._matches_rag_intent(message_lower):
            logger.info(f"Routing to RAG Agent")
            return await self.rag_agent.answer(user_id, message)
        
        # Pattern 4: Help/options
        else:
            return self._show_options()
    
    @staticmethod
    def _matches_quiz_intent(message: str) -> bool:
        """Check if message indicates quiz mode."""
        patterns = [
            r"quiz",
            r"give me.*question",
            r"test.*knowledge",
            r"exam question",
        ]
        return any(re.search(p, message) for p in patterns)
    
    @staticmethod
    def _matches_cheatsheet_intent(message: str) -> bool:
        """Check if message indicates cheatsheet mode."""
        patterns = [
            r"^quick:",
            r"quick facts",
            r"quick summary",
        ]
        return any(re.search(p, message) for p in patterns)
    
    @staticmethod
    def _matches_rag_intent(message: str) -> bool:
        """Check if message is a question."""
        patterns = [
            r"^(explain|what|tell|how|why|describe|define)",
            r"\?$",  # Ends with question mark
        ]
        return any(re.search(p, message) for p in patterns)
    
    @staticmethod
    def _extract_domain(message: str) -> Optional[str]:
        """Extract AWS domain from message (e.g., 'EC2', 'S3')."""
        domains = ["EC2", "S3", "RDS", "DynamoDB", "Lambda", "VPC", "IAM", "CloudFormation"]
        for domain in domains:
            if domain.lower() in message.lower():
                return domain
        return None
    
    @staticmethod
    def _show_options() -> str:
        """Show user available options."""
        return """Hi! I can help you study for AWS Solutions Architect exam. Try:

📚 Explain mode: "Explain EC2" or "What is S3?"
📝 Quiz mode: "Quiz on RDS" or "Give me questions"
⚡ Quick mode: "Quick: DynamoDB" or "Quick facts on VPC"

What would you like to do?"""
```

---

## File 7: `src/main.py` ⭐⭐⭐

**Purpose**: FastAPI app + Twilio webhook  
**Time**: 1 hour  
**Difficulty**: Intermediate  

```python
"""
FastAPI application with Twilio WhatsApp webhook.
"""

import logging
from fastapi import FastAPI, Request, HTTPException
from src.config import Config
from src.database import get_db
from src.vector_store import get_vector_store
from src.llm_client import get_llm_client
from src.agents.rag_agent import RAGAgent
from src.agents.quiz_agent import QuizAgent
from src.agents.cheatsheet_agent import CheatsheetAgent
from src.agents.router import MessageRouter

# Setup logging
logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="AWS SAA Exam Agent", version="0.1.0")

# Initialize dependencies
db = get_db(Config.SQLITE_DB_PATH)
vector_store = get_vector_store(Config.CHROMA_DB_PATH)
llm_client = get_llm_client()

# Initialize agents
rag_agent = RAGAgent(vector_store, llm_client, db)
quiz_agent = QuizAgent(vector_store, llm_client, db)
cheatsheet_agent = CheatsheetAgent(vector_store, db)

# Initialize router
router = MessageRouter(rag_agent, quiz_agent, cheatsheet_agent, db)


@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup."""
    logger.info("Starting AWS SAA Agent...")
    try:
        Config.validate()
        logger.info("✅ Configuration validated")
    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "environment": Config.ENVIRONMENT
    }


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receive messages from Twilio WhatsApp and respond.
    
    Flow:
    1. Receive WhatsApp message from Twilio
    2. Extract sender + message
    3. Route to correct agent
    4. Send response back via Twilio
    """
    try:
        # Parse Twilio request
        data = await request.form()
        sender = data.get("From")
        message_text = data.get("Body", "").strip()
        
        logger.info(f"Received message from {sender}: {message_text[:50]}")
        
        if not message_text:
            logger.warning("Empty message received")
            return {"status": "ok"}
        
        # Route message to agent
        try:
            response = await router.route_message(sender, message_text)
        except Exception as e:
            logger.error(f"Error routing message: {e}")
            response = f"Sorry, I encountered an error: {str(e)[:100]}"
        
        # Send response via Twilio
        _send_whatsapp_message(sender, response)
        
        logger.info(f"Sent response to {sender}")
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"error": str(e)}, 400


def _send_whatsapp_message(recipient: str, message: str):
    """
    Send WhatsApp message via Twilio.
    
    TODO: Implement when Twilio credentials are ready.
    For now, just log.
    """
    logger.info(f"[WHATSAPP RESPONSE] To: {recipient}")
    logger.info(f"Message: {message}")
    
    # Production implementation:
    # from twilio.rest import Client
    # client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    # client.messages.create(
    #     body=message,
    #     from_=f"whatsapp:{Config.TWILIO_WHATSAPP_NUMBER}",
    #     to=recipient
    # )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
```

---

## File 8: `scripts/test_webhook.py`

**Purpose**: Test webhook locally  
**Time**: 30 min  

```python
"""
Test webhook locally without Twilio.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.router import MessageRouter
from src.agents.rag_agent import RAGAgent
from src.agents.quiz_agent import QuizAgent
from src.agents.cheatsheet_agent import CheatsheetAgent
from src.vector_store import get_vector_store
from src.llm_client import get_llm_client
from src.database import get_db


async def test_webhook():
    """Test webhook with various messages."""
    
    # Initialize
    db = get_db()
    vector_store = get_vector_store()
    llm_client = get_llm_client()
    
    rag = RAGAgent(vector_store, llm_client, db)
    quiz = QuizAgent(vector_store, llm_client, db)
    cheatsheet = CheatsheetAgent(vector_store, db)
    
    router = MessageRouter(rag, quiz, cheatsheet, db)
    
    # Test messages
    test_cases = [
        ("Explain EC2", "RAG mode"),
        ("What is S3?", "RAG mode"),
        ("Quiz on RDS", "Quiz mode"),
        ("Quick: VPC", "Cheatsheet mode"),
        ("Hello", "Help mode"),
    ]
    
    user_id = "+1234567890"
    
    for message, expected_mode in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {message} (expected: {expected_mode})")
        print(f"{'='*60}")
        
        try:
            response = await router.route_message(user_id, message)
            print(f"Response:\n{response}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_webhook())
```

---

## 🚀 EXECUTION PLAN

### This Week

**Monday:**
- [ ] Implement `src/llm_client.py` (30 min)
- [ ] Test with `test_llm.py` (10 min)

**Tuesday:**
- [ ] Implement `src/agents/rag_agent.py` (1 hour)
- [ ] Test with `test_rag_agent.py` (15 min)

**Wednesday:**
- [ ] Implement `src/agents/quiz_agent.py` (1.5 hours)
- [ ] Test locally (30 min)

**Thursday:**
- [ ] Implement `src/agents/cheatsheet_agent.py` (30 min)
- [ ] Implement `src/agents/router.py` (45 min)
- [ ] Test routing logic (30 min)

**Friday:**
- [ ] Implement `src/main.py` (1 hour)
- [ ] Test with `test_webhook.py` (30 min)
- [ ] Debug and polish (1 hour)

### Next Week (Phase 3)

**Docker + Deployment** (3-4 hours)

---

## 💡 Tips While Building

1. **Start simple**: Get basic RAG working first, then add bells and whistles
2. **Test each agent independently**: Don't integrate until each works alone
3. **Log everything**: Use logger.info() liberally for debugging
4. **Handle errors gracefully**: Always return helpful error messages
5. **Use type hints**: Python type hints help catch bugs early

---

## ✅ Success Criteria

After implementing all files:

- [ ] `llm_client.py`: Can call Ollama/Claude and get responses
- [ ] `rag_agent.py`: Can retrieve and explain AWS concepts
- [ ] `quiz_agent.py`: Can generate Q&A and track progress
- [ ] `cheatsheet_agent.py`: Fast lookup in cheatsheet
- [ ] `router.py`: Routes messages to correct agent
- [ ] `main.py`: FastAPI server runs without errors
- [ ] `test_webhook.py`: All test cases pass

When all files are done → **You're ready for Phase 3 (Deployment)!** 🎉

---

## Questions?

When stuck:
1. Check the docstrings in the code examples
2. Look at `LEARNING_OBJECTIVES.md` for concepts
3. Test each function individually
4. Add `logger.info()` statements to trace execution

**You got this!** 💪
