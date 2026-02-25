from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('search/', views.search_documents_view, name='search'),
    path('documents/', views.list_documents_view, name='list_documents'),
    path('ask/', views.ask_question_view, name='ask_question'),
    path('qa-records/', views.list_qa_records_view, name='list_qa_records'),
]
