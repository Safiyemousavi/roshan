"""
LangChain-powered RAG pipeline.

Flow:
1) Receive user question
2) Retrieve relevant documents
3) Build strict prompt from context + question
4) Generate answer via local Hugging Face pipeline
5) Save answer in QA_Record
"""
from __future__ import annotations

import re
from typing import List, Tuple

from django.conf import settings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

from .models import Document, QA_Record
from .retrieval import search_documents


RAG_PROMPT_TEMPLATE = """You are a strict retrieval-augmented assistant.
Rules:
1) Use ONLY the context below to answer the question.
2) If context is missing or insufficient, respond exactly with:
   "{no_info_message}"
3) If the question is Persian (Farsi), answer in Persian.
4) Otherwise, answer in the same language as the question.
5) Keep the answer concise and factual.

Persian few-shot examples:
Example 1:
Context:
[1] Title: سیاست مدیریت رخداد
Score: 0.9142
Text: رخدادها باید در پانزده دقیقه اول بررسی اولیه شوند.
Question:
زمان بررسی اولیه رخداد چقدر است؟
Answer:
بر اساس سند بازیابی‌شده، بررسی اولیه رخداد باید در پانزده دقیقه اول انجام شود.

Example 2:
Context:
No relevant documents were found.
Question:
آب‌وهوای فردای تهران چگونه است؟
Answer:
"{no_info_message}"

Context:
{context}

Question:
{question}

Answer:
"""


class RAGPipeline:
    """RAG pipeline that retrieves documents and produces a persisted answer."""

    def __init__(self, top_k: int | None = None):
        self.top_k = top_k or getattr(settings, "RAG_DEFAULT_TOP_K", 5)
        self.model_id = getattr(settings, "HUGGINGFACE_REPO_ID", "google/flan-t5-base")
        self.use_fake_llm = getattr(settings, "USE_FAKE_LLM", True)
        self.hf_token = getattr(settings, "HUGGINGFACE_API_TOKEN", "")
        self.hf_client = None

        self.prompt = PromptTemplate(
            input_variables=["context", "question", "no_info_message"],
            template=RAG_PROMPT_TEMPLATE,
        )
        self.llm = self._build_llm_runnable()
        self.chain = self.prompt | self.llm | StrOutputParser()

    @staticmethod
    def _coerce_prompt(prompt_value: object) -> str:
        if hasattr(prompt_value, "to_string"):
            return prompt_value.to_string()
        return str(prompt_value)

    def _build_llm_runnable(self) -> RunnableLambda:
        """Build LLM runner with fake fallback and optional Hugging Face API path."""
        if self.use_fake_llm or not self.hf_token:
            return RunnableLambda(self._fake_generate)

        from huggingface_hub import InferenceClient

        self.hf_client = InferenceClient(model=self.model_id, token=self.hf_token)
        return RunnableLambda(self._hf_generate)

    def _fake_generate(self, prompt_value: object) -> str:
        prompt = self._coerce_prompt(prompt_value)
        question = "unknown question"
        marker = "\nQuestion:\n"
        if marker in prompt:
            question = prompt.rsplit(marker, 1)[1].split("\n", 1)[0].strip() or question
        return f"Fallback answer generated for: {question}"

    def _hf_generate(self, prompt_value: object) -> str:
        if self.hf_client is None:
            raise RuntimeError("Hugging Face client is not initialized.")

        prompt = self._coerce_prompt(prompt_value)
        response = self.hf_client.text_generation(
            prompt,
            max_new_tokens=256,
            temperature=0.2,
            do_sample=False,
        )
        return response.strip()

    @staticmethod
    def _is_persian_text(text: str) -> bool:
        """Return True if text contains Persian/Arabic script characters."""
        return re.search(r"[\u0600-\u06FF]", text) is not None

    @staticmethod
    def _build_context(retrieved: List[Tuple[Document, float]]) -> str:
        """Build context payload for the prompt from retrieved documents."""
        if not retrieved:
            return "No relevant documents were found."

        context_chunks: List[str] = []
        for index, (doc, score) in enumerate(retrieved, start=1):
            normalized_text = " ".join(doc.full_text.split())
            chunk = (
                f"[{index}] Title: {doc.title}\n"
                f"Score: {score:.4f}\n"
                f"Text: {normalized_text[:1200]}"
            )
            context_chunks.append(chunk)
        return "\n\n".join(context_chunks)

    @staticmethod
    def _normalize_answer(answer: object) -> str:
        """Normalize chain output to plain string."""
        if isinstance(answer, str):
            return answer.strip()
        return str(answer).strip()

    def answer_question(self, question: str, top_k: int | None = None):
        """Run full RAG flow and persist QA record with retrieved documents."""
        limit = top_k or self.top_k
        retrieved = search_documents(question, top_k=limit)

        no_info_message = (
            "\u0627\u0637\u0644\u0627\u0639\u0627\u062a \u06a9\u0627\u0641\u06cc "
            "\u062f\u0631 \u0627\u0633\u0646\u0627\u062f \u0628\u0627\u0632\u06cc\u0627"
            "\u0628\u06cc \u0634\u062f\u0647 \u0628\u0631\u0627\u06cc \u067e\u0627\u0633"
            "\u062e \u062f\u0642\u06cc\u0642 \u0648\u062c\u0648\u062f \u0646\u062f\u0627"
            "\u0631\u062f."
            if self._is_persian_text(question)
            else "Not enough information in retrieved documents to answer this question."
        )

        if not retrieved:
            qa_record = QA_Record.objects.create(question=question, answer=no_info_message)
            return qa_record, retrieved

        context = self._build_context(retrieved)
        payload = {
            "context": context,
            "question": question,
            "no_info_message": no_info_message,
        }

        try:
            raw_answer = self.chain.invoke(payload)
            answer = self._normalize_answer(raw_answer)
            if not answer:
                answer = no_info_message
        except Exception as exc:
            answer = (
                "\u062e\u0637\u0627 \u062f\u0631 \u062a\u0648\u0644\u06cc\u062f "
                "\u067e\u0627\u0633\u062e \u0645\u062f\u0644. \u0644\u0637\u0641\u0627 "
                "\u062f\u0648\u0628\u0627\u0631\u0647 \u062a\u0644\u0627\u0634 "
                "\u06a9\u0646\u06cc\u062f."
                if self._is_persian_text(question)
                else f"Model generation error: {exc}"
            )

        qa_record = QA_Record.objects.create(question=question, answer=answer)
        if retrieved:
            qa_record.retrieved_documents.set([doc for doc, _ in retrieved])
        return qa_record, retrieved


_pipeline = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or create a singleton RAG pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


def generate_answer_for_question(question: str, top_k: int = 5):
    """Convenience function for API and scripts."""
    pipeline = get_rag_pipeline()
    return pipeline.answer_question(question=question, top_k=top_k)
