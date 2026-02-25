from django.test import TestCase
from django.utils import timezone

from documents.models import Document
from documents.retrieval import normalize_persian_text, search_documents
import documents.retrieval as retrieval_module


class DocumentRetrievalTests(TestCase):
    def setUp(self):
        retrieval_module._retriever = None
        Document.objects.create(
            title="Django REST Framework Guide",
            full_text="Build APIs with Django REST Framework serializers and views.",
            date=timezone.now(),
            tags="django,api,rest",
        )
        Document.objects.create(
            title="PostgreSQL Performance Tuning",
            full_text="Use indexes and query plans to optimize PostgreSQL workloads.",
            date=timezone.now(),
            tags="database,postgresql,performance",
        )
        Document.objects.create(
            title="Docker Compose Basics",
            full_text="Container orchestration with docker compose for local development.",
            date=timezone.now(),
            tags="docker,containers,devops",
        )

    def test_search_returns_ranked_documents(self):
        results = search_documents("How do I build a Django API?", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertIn("Django", results[0][0].title)
        self.assertGreater(results[0][1], 0.0)

    def test_search_returns_empty_for_unrelated_query(self):
        results = search_documents("quantum entanglement in satellites", top_k=3)
        self.assertEqual(results, [])

    def test_normalize_persian_text_unifies_variants(self):
        normalized = normalize_persian_text("اين متن مي‌كند")
        self.assertEqual(normalized, "این متن می کند")

    def test_search_matches_persian_with_arabic_forms_and_half_space(self):
        Document.objects.create(
            title="راهنمای پاسخ‌گویی سامانه",
            full_text="این سامانه به کاربر کمک می‌کند و گزارش‌گیری دقیق دارد.",
            date=timezone.now(),
            tags="راهنما,سامانه",
        )

        results = search_documents(
            "اين سامانه به كاربر كمك ميكند و گزارش گيري دقيق دارد",
            top_k=5,
        )

        self.assertGreater(len(results), 0)
        self.assertIn("راهنمای", results[0][0].title)
        self.assertGreater(results[0][1], 0.0)
