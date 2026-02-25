from rest_framework import serializers
from .models import Document, QA_Record


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'full_text', 'date', 'tags', 'created_at']


class DocumentSearchResultSerializer(serializers.Serializer):
    document = DocumentSerializer()
    similarity_score = serializers.FloatField()


class SearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    top_k = serializers.IntegerField(default=5, min_value=1, max_value=20)


class QuestionRequestSerializer(serializers.Serializer):
    question = serializers.CharField(required=True)
    top_k = serializers.IntegerField(default=5, min_value=1, max_value=20)


class QARecordSerializer(serializers.ModelSerializer):
    retrieved_documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = QA_Record
        fields = ['id', 'question', 'answer', 'retrieved_documents', 'created_at']
