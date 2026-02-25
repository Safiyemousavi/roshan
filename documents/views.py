from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Document, QA_Record
from .serializers import (
    DocumentSerializer,
    QARecordSerializer,
    QuestionRequestSerializer,
    SearchRequestSerializer,
)
from .retrieval import search_documents
from .rag_chain import generate_answer_for_question


@api_view(['POST'])
def search_documents_view(request):
    """
    API endpoint to search documents using TF-IDF.
    
    POST /api/search/
    Body: {"query": "your search query", "top_k": 5}
    """
    serializer = SearchRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    query = serializer.validated_data['query']
    top_k = serializer.validated_data.get('top_k', 5)
    
    # Perform search
    results = search_documents(query, top_k)
    
    # Format response
    response_data = {
        'query': query,
        'results_count': len(results),
        'results': [
            {
                'document': DocumentSerializer(doc).data,
                'similarity_score': round(score, 4)
            }
            for doc, score in results
        ]
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
def list_documents_view(request):
    """List all documents."""
    documents = Document.objects.all()
    serializer = DocumentSerializer(documents, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def ask_question_view(request):
    """
    API endpoint to run retrieval + LLM answer generation.

    POST /api/ask/
    Body: {"question": "your question", "top_k": 5}
    """
    serializer = QuestionRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    question = serializer.validated_data['question']
    top_k = serializer.validated_data.get('top_k', 5)

    qa_record, retrieved = generate_answer_for_question(question=question, top_k=top_k)

    response_data = {
        'qa_record_id': qa_record.id,
        'question': qa_record.question,
        'answer': qa_record.answer,
        'retrieved_count': len(retrieved),
        'retrieved_documents': [
            {
                'document': DocumentSerializer(doc).data,
                'similarity_score': round(score, 4),
            }
            for doc, score in retrieved
        ],
    }
    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def list_qa_records_view(request):
    """List all generated QA records."""
    qa_records = QA_Record.objects.prefetch_related('retrieved_documents').all()
    serializer = QARecordSerializer(qa_records, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
