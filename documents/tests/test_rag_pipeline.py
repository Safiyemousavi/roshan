from django.test import TestCase, override_settings
from django.utils import timezone

from documents.models import Document, QA_Record
from documents.rag_chain import generate_answer_for_question
import documents.rag_chain as rag_chain_module
import documents.retrieval as retrieval_module


@override_settings(USE_FAKE_LLM=True, HUGGINGFACE_API_TOKEN="")
class RAGPipelineTests(TestCase):
    def setUp(self):
        rag_chain_module._pipeline = None
        retrieval_module._retriever = None
        Document.objects.create(
            title="Incident Response Policy",
            full_text=(
                "Incidents are classified by severity and require initial triage "
                "within fifteen minutes."
            ),
            date=timezone.now(),
            tags="security,incident,response",
        )
        Document.objects.create(
            title="On-Call Runbook",
            full_text=(
                "The on-call engineer acknowledges alerts, investigates logs, "
                "and communicates status updates."
            ),
            date=timezone.now(),
            tags="operations,alerts,runbook",
        )

    def test_pipeline_creates_qa_record(self):
        qa_record, retrieved = generate_answer_for_question(
            question="How quickly should incident triage start?",
            top_k=2,
        )

        self.assertIsInstance(qa_record, QA_Record)
        self.assertTrue(qa_record.answer)
        self.assertGreaterEqual(len(retrieved), 1)
        self.assertEqual(QA_Record.objects.count(), 1)
        self.assertGreaterEqual(qa_record.retrieved_documents.count(), 1)

    def test_pipeline_handles_no_retrieval_matches(self):
        qa_record, retrieved = generate_answer_for_question(
            question="Explain marine biology in polar oceans.",
            top_k=2,
        )

        self.assertEqual(retrieved, [])
        self.assertIn("Not enough information", qa_record.answer)
