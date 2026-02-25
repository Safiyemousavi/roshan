"""
Document retrieval engine using TF-IDF for semantic search.
"""
import re
import unicodedata

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Document


_PERSIAN_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
    }
)
_ZERO_WIDTH_CHARS = ("\u200c", "\u200d", "\u200e", "\u200f", "\u2060", "\ufeff")


def normalize_persian_text(text: str) -> str:
    """Normalize Persian variants for stable TF-IDF indexing/search."""
    if text is None:
        return ""

    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.translate(_PERSIAN_CHAR_MAP)
    for char in _ZERO_WIDTH_CHARS:
        normalized = normalized.replace(char, " ")
    return re.sub(r"\s+", " ", normalized).strip()


class DocumentRetriever:
    """TF-IDF based document retrieval system."""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1
        )
        self.document_vectors = None
        self.documents = None
    
    def index_documents(self, documents=None):
        """Index documents for retrieval."""
        if documents is None:
            documents = Document.objects.all()
        
        self.documents = list(documents)
        
        if not self.documents:
            self.document_vectors = None
            return
        
        corpus = [
            normalize_persian_text(f"{doc.title} {doc.full_text}")
            for doc in self.documents
        ]
        self.document_vectors = self.vectorizer.fit_transform(corpus)
    
    def search(self, query, top_k=5):
        """Search for relevant documents using TF-IDF similarity."""
        if not self.documents or self.document_vectors is None:
            self.index_documents()
        
        if not self.documents:
            return []
        
        normalized_query = normalize_persian_text(query)
        if not normalized_query:
            return []

        query_vector = self.vectorizer.transform([normalized_query])
        similarities = cosine_similarity(query_vector, self.document_vectors)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = [
            (self.documents[idx], float(similarities[idx]))
            for idx in top_indices
            if similarities[idx] > 0
        ]
        
        return results
    
    def search_documents_only(self, query, top_k=5):
        """Search and return only Document objects."""
        results = self.search(query, top_k)
        return [doc for doc, score in results]


_retriever = None


def get_retriever():
    """Get or create the global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = DocumentRetriever()
    return _retriever


def search_documents(query, top_k=5):
    """Convenience function to search documents."""
    retriever = get_retriever()
    return retriever.search(query, top_k)
