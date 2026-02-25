from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Case, IntegerField, Value, When
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Document, QA_Record
from .retrieval import get_retriever, search_documents


class TagFacetFilter(admin.SimpleListFilter):
    title = "tag facet"
    parameter_name = "tag"

    def lookups(self, request, model_admin):
        tags = set()
        for tag_blob in Document.objects.exclude(tags="").values_list("tags", flat=True):
            for raw_tag in tag_blob.split(","):
                tag = raw_tag.strip()
                if tag:
                    tags.add(tag)
        return [(tag, tag) for tag in sorted(tags)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tags__icontains=self.value())
        return queryset


class RelativeDateRangeFilter(admin.SimpleListFilter):
    title = "date range"
    parameter_name = "date_range"

    def lookups(self, request, model_admin):
        return [
            ("today", "Today"),
            ("7d", "Last 7 days"),
            ("30d", "Last 30 days"),
            ("90d", "Last 90 days"),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        selected = self.value()
        if selected == "today":
            return queryset.filter(date__date=now.date())
        if selected == "7d":
            return queryset.filter(date__gte=now - timedelta(days=7))
        if selected == "30d":
            return queryset.filter(date__gte=now - timedelta(days=30))
        if selected == "90d":
            return queryset.filter(date__gte=now - timedelta(days=90))
        return queryset


class RetrievalTestForm(forms.Form):
    retrieval_query = forms.CharField(
        label="Retrieval test query",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Try a user question to inspect ranked sources",
                "style": "min-width: 320px;",
            }
        ),
    )
    retrieval_top_k = forms.IntegerField(
        label="Top K",
        required=False,
        initial=5,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={"style": "width: 84px;"}),
    )


class QARecordAdminForm(forms.ModelForm):
    top_k = forms.IntegerField(
        required=False,
        initial=getattr(settings, "RAG_DEFAULT_TOP_K", 5),
        min_value=1,
        max_value=20,
        help_text="Used for retrieval preview only. It does not persist to database.",
    )

    class Meta:
        model = QA_Record
        fields = ["question", "answer", "retrieved_documents"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    change_list_template = "admin/documents/document/change_list.html"
    list_display = ("title", "vectorized_status", "word_count", "date", "tags", "created_at")
    list_filter = (RelativeDateRangeFilter, ("date", admin.DateFieldListFilter), TagFacetFilter, "created_at")
    search_fields = ("title", "full_text", "tags")
    date_hierarchy = "date"
    ordering = ("-date",)
    actions = ["reindex_documents"]

    fieldsets = (
        (
            "Document Information",
            {
                "fields": ("title", "full_text", "date", "tags"),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "reindex-all/",
                self.admin_site.admin_view(self.reindex_all_view),
                name="documents_document_reindex_all",
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        retriever = get_retriever()
        if retriever.documents and retriever.document_vectors is not None:
            self._indexed_doc_ids = {doc.id for doc in retriever.documents}
        else:
            self._indexed_doc_ids = set()
        return queryset

    def _reindex(self):
        retriever = get_retriever()
        retriever.index_documents(Document.objects.all())
        return len(retriever.documents or [])

    @admin.action(description="Re-index selected documents for TF-IDF")
    def reindex_documents(self, request, queryset):
        indexed_count = self._reindex()
        selected_count = queryset.count()
        self.message_user(
            request,
            (
                f"TF-IDF index rebuilt from all documents. "
                f"Selected: {selected_count}, currently indexed: {indexed_count}."
            ),
            level=messages.SUCCESS,
        )

    def reindex_all_view(self, request):
        indexed_count = self._reindex()
        self.message_user(
            request,
            f"TF-IDF index rebuilt successfully. Indexed documents: {indexed_count}.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse("admin:documents_document_changelist"))

    @admin.display(boolean=True, description="Vectorized")
    def vectorized_status(self, obj):
        return obj.id in getattr(self, "_indexed_doc_ids", set())

    @admin.display(description="Word Count")
    def word_count(self, obj):
        return len((obj.full_text or "").split())

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        retrieval_form = RetrievalTestForm(request.GET or None)
        retrieval_submitted = "retrieval_query" in request.GET
        retrieval_results = []

        if retrieval_submitted and retrieval_form.is_valid():
            query = retrieval_form.cleaned_data.get("retrieval_query", "").strip()
            top_k = retrieval_form.cleaned_data.get("retrieval_top_k") or 5
            if query:
                retrieval_results = [
                    {
                        "document": doc,
                        "score": score,
                        "preview": " ".join(doc.full_text.split())[:300],
                    }
                    for doc, score in search_documents(query, top_k=top_k)
                ]

        extra_context.update(
            {
                "retrieval_form": retrieval_form,
                "retrieval_submitted": retrieval_submitted,
                "retrieval_results": retrieval_results,
                "reindex_all_url": reverse("admin:documents_document_reindex_all"),
            }
        )
        return super().changelist_view(request, extra_context=extra_context)

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            results = search_documents(search_term, top_k=20)
            doc_ids = [doc.id for doc, _ in results]
            if not doc_ids:
                return queryset.none(), False

            order_by_rank = Case(
                *[When(id=doc_id, then=Value(rank)) for rank, doc_id in enumerate(doc_ids)],
                output_field=IntegerField(),
            )
            queryset = queryset.filter(id__in=doc_ids).order_by(order_by_rank)
            return queryset, False
        return super().get_search_results(request, queryset, search_term)


@admin.register(QA_Record)
class QA_RecordAdmin(admin.ModelAdmin):
    form = QARecordAdminForm
    change_form_template = "admin/documents/qa_record/change_form.html"
    list_display = ("question_preview", "answer_preview", "confidence_score", "retrieved_docs_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("question", "answer")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    filter_horizontal = ("retrieved_documents",)

    readonly_fields = ("confidence_score", "retrieved_context_preview", "created_at")
    fieldsets = (
        (
            "Inference Input",
            {
                "fields": ("question", "top_k"),
            },
        ),
        (
            "Model Output",
            {
                "fields": ("answer",),
            },
        ),
        (
            "Source Documents",
            {
                "fields": ("retrieved_documents",),
            },
        ),
        (
            "Debug Context",
            {
                "fields": ("confidence_score", "retrieved_context_preview", "created_at"),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "test-retrieval/",
                self.admin_site.admin_view(self.test_retrieval_view),
                name="documents_qarecord_test_retrieval",
            ),
        ]
        return custom_urls + urls

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial["top_k"] = getattr(settings, "RAG_DEFAULT_TOP_K", 5)
        return initial

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["test_retrieval_url"] = reverse("admin:documents_qarecord_test_retrieval")
        context["default_top_k"] = getattr(settings, "RAG_DEFAULT_TOP_K", 5)
        context["existing_context_preview"] = self._context_preview_text(obj)
        return super().render_change_form(request, context, add, change, form_url, obj)

    def test_retrieval_view(self, request):
        query = (request.GET.get("query") or "").strip()
        top_k_raw = request.GET.get("top_k") or str(getattr(settings, "RAG_DEFAULT_TOP_K", 5))
        try:
            top_k = max(1, min(20, int(top_k_raw)))
        except ValueError:
            top_k = getattr(settings, "RAG_DEFAULT_TOP_K", 5)

        results = search_documents(query, top_k=top_k) if query else []
        context = {
            "query": query,
            "top_k": top_k,
            "results": results,
        }
        return TemplateResponse(request, "admin/documents/qa_record/retrieval_preview.html", context)

    def _context_preview_text(self, obj):
        if not obj or not obj.pk:
            return "No context yet. Ask a question or click 'Test Retrieval' to preview chunks."

        docs = obj.retrieved_documents.all()
        if not docs:
            return "No documents are linked to this QA record."

        lines = []
        for index, doc in enumerate(docs, start=1):
            snippet = " ".join((doc.full_text or "").split())[:500]
            lines.append(f"[{index}] {doc.title}\n{snippet}")
        return "\n\n".join(lines)

    @admin.display(description="Question")
    def question_preview(self, obj):
        return obj.question[:75] + "..." if len(obj.question) > 75 else obj.question

    @admin.display(description="Answer")
    def answer_preview(self, obj):
        if not obj.answer:
            return "(No answer yet)"
        return obj.answer[:75] + "..." if len(obj.answer) > 75 else obj.answer

    @admin.display(description="Retrieved Docs")
    def retrieved_docs_count(self, obj):
        return obj.retrieved_documents.count()

    @admin.display(description="Confidence")
    def confidence_score(self, obj):
        if not obj.question:
            return "-"
        results = search_documents(obj.question, top_k=1)
        if not results:
            return "0.0000"
        return f"{results[0][1]:.4f}"

    @admin.display(description="Retrieved Context")
    def retrieved_context_preview(self, obj):
        return format_html(
            '<pre style="margin:0; white-space:pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;">{}</pre>',
            self._context_preview_text(obj),
        )
