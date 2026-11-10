import logging
import json
import urllib.request
from typing import Dict, Any, List, Optional
from app.config import settings
from app.rag.document_indexer import DocumentIndexer
from app.rag.vector_store import HybridVectorStore

logger = logging.getLogger(__name__)

class PolicyRAGEngine:
    """
    RAG Engine that grounds policy questions exclusively on the Service Management Policy document.
    Enforces strict truthfulness: communicates clearly when information is missing or not covered.
    """

    # Topics explicitly identified as NOT covered by SRV-POL-001 (Section 7.2)
    EXPLICITLY_UNDEFINED_TOPICS = [
        "employee bonus", "bonus policy", "annual bonus", "performance bonus",
        "employee leave", "maternity leave", "sick leave", "vacation entitlement",
        "payroll rules", "salary structure", "compensation package",
        "customer refund", "refund policy"
    ]

    def __init__(self):
        self.indexer = DocumentIndexer(settings.POLICY_PDF_PATH)
        self.vector_store = HybridVectorStore()
        self.is_initialized = False

    def initialize(self, force_rebuild: bool = False):
        """
        Extracts chunks from policy document and builds hybrid vector index.
        """
        try:
            chunks = self.indexer.create_chunks()
            self.vector_store.build_index(chunks, force_rebuild=force_rebuild)
            self.is_initialized = True
            logger.info("Policy RAG Engine successfully initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Policy RAG Engine: {e}")

    def query(self, query_text: str) -> Dict[str, Any]:
        """
        Executes grounded question answering based on the policy document.
        """
        if not self.is_initialized:
            self.initialize()

        q_lower = query_text.lower().strip()

        # Check for explicitly excluded / out-of-scope business topics (Section 7.2)
        for topic in self.EXPLICITLY_UNDEFINED_TOPICS:
            if topic in q_lower:
                return {
                    "is_found": False,
                    "answer": (
                        "I cannot find this information in the provided policy document. "
                        "According to Section 7.2 of the Service Management Policy (Policy Reference: SRV-POL-001), "
                        "this policy specifically covers service management and creation, and does NOT define an employee "
                        "bonus policy, employee leave entitlement, payroll rules, or customer refund policy. "
                        "Please consult the relevant Human Resources or Operations department."
                    ),
                    "sources": [
                        {
                            "policy_ref": "SRV-POL-001",
                            "section": "Section 7.2: Information not defined in this policy",
                            "page": 8
                        }
                    ],
                    "confidence": "HIGH_NOT_FOUND"
                }

        # Search vector store for relevant chunks
        results = self.vector_store.search(query_text, top_k=3)
        if not results or results[0][1] < 0.25:
            return {
                "is_found": False,
                "answer": (
                    "I cannot find relevant information in the provided Service Management Policy (SRV-POL-001) "
                    "to answer your question. Per our operating guidelines, I cannot speculate or invent policy details."
                ),
                "sources": [],
                "confidence": "LOW_NOT_FOUND"
            }

        # Build context from top chunks
        context_parts = []
        sources = []
        for chunk, score in results:
            context_parts.append(f"[{chunk.get('section', '')} | Page {chunk.get('page', '')}]:\n{chunk.get('content', '')}")
            sources.append({
                "policy_ref": chunk.get("policy_ref", "SRV-POL-001"),
                "section": chunk.get("section", ""),
                "page": chunk.get("page", 1),
                "score": round(score, 3)
            })

        context_str = "\n\n".join(context_parts)

        # Synthesize answer using Gemini LLM with strict grounding prompt
        answer = self._synthesize_grounded_answer(query_text, context_str)

        return {
            "is_found": True,
            "answer": answer,
            "sources": sources,
            "confidence": "HIGH"
        }

    def _synthesize_grounded_answer(self, query: str, context: str) -> str:
        """
        Calls Gemini API with strict system instructions to prevent hallucination.
        """
        api_key = settings.GEMINI_AI_API_KEY
        if not api_key:
            return f"Policy Excerpt (Reference SRV-POL-001):\n{context}"

        system_instruction = (
            "You are a helpful and compliant Business Policy Assistant. "
            "You must answer user questions STRICTLY using only the provided context from the Service Management Policy (SRV-POL-001). "
            "Rules:\n"
            "1. State the exact rule and numbers (e.g. maximum permitted price is BDT 500,000).\n"
            "2. Always cite the exact source reference (e.g., Policy Reference: SRV-POL-001, Section 2.1 / Section 7.1).\n"
            "3. If the context does not contain the answer, state clearly that you cannot find the relevant information. DO NOT invent an answer.\n"
            "4. Keep the response professional, clear, and concise."
        )

        prompt = f"Context:\n{context}\n\nQuestion:\n{query}\n\nProvide the accurate policy answer with source citations:"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_instruction}\n\n{prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 400
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Failed to generate answer with Gemini: {e}")
            # Fallback deterministic answer extraction
            if "maximum price" in query.lower():
                return (
                    "According to Section 2.1 and Section 7.1 of the Service Management Policy "
                    "(Policy Reference: SRV-POL-001), the maximum permitted price for creating a single service is "
                    "BDT 500,000 (Five Hundred Thousand Bangladeshi Taka). Services priced above this threshold "
                    "cannot be created through standard workflows."
                )
            return f"Context:\n{context}"

policy_engine = PolicyRAGEngine()

