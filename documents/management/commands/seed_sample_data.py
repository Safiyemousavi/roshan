from django.core.management.base import BaseCommand
from django.utils import timezone

import documents.rag_chain as rag_chain_module
import documents.retrieval as retrieval_module
from documents.models import Document, QA_Record
from documents.rag_chain import generate_answer_for_question


class Command(BaseCommand):
    help = "Populate database with exactly 3 sample documents and 2 sample questions."

    def handle(self, *args, **options):
        self.stdout.write("Resetting documents and QA records...")

        QA_Record.objects.all().delete()
        Document.objects.all().delete()
        retrieval_module._retriever = None
        rag_chain_module._pipeline = None

        sample_documents = [
            {
                "title": "Django Security Practices",
                "full_text": (
                    "Use CSRF protection, secure session cookies, and strict input "
                    "validation to protect Django applications."
                ),
                "date": timezone.now(),
                "tags": "django,security,backend",
            },
            {
                "title": "PostgreSQL Indexing Guide",
                "full_text": (
                    "B-tree indexes accelerate equality and range filters. Analyze "
                    "query plans before adding indexes."
                ),
                "date": timezone.now(),
                "tags": "postgresql,database,indexing",
            },
            {
                "title": "Docker Compose for Development",
                "full_text": (
                    "Docker Compose defines multi-service development environments "
                    "with shared networks, volumes, and environment variables."
                ),
                "date": timezone.now(),
                "tags": "docker,devops,containers",
            },
        ]

        for doc_data in sample_documents:
            Document.objects.create(**doc_data)

        sample_questions = [
            "How can I secure a Django backend application?",
            "When should I add PostgreSQL indexes?",
        ]

        for question in sample_questions:
            generate_answer_for_question(question=question, top_k=3)

        self.stdout.write(
            self.style.SUCCESS(
                "Seed complete: 3 documents and 2 question records created."
            )
        )
