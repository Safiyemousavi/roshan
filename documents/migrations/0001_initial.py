from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=255)),
                ('full_text', models.TextField()),
                ('date', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('tags', models.CharField(blank=True, help_text='Comma-separated tags', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Document',
                'verbose_name_plural': 'Documents',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='QA_Record',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.TextField()),
                ('answer', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('retrieved_documents', models.ManyToManyField(blank=True, related_name='qa_records', to='documents.document')),
            ],
            options={
                'verbose_name': 'QA Record',
                'verbose_name_plural': 'QA Records',
                'ordering': ['-created_at'],
            },
        ),
    ]
