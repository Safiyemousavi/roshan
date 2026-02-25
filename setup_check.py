#!/usr/bin/env python
"""
Quick setup verification script for Phase 1
"""
import os
import sys

def check_files():
    """Check if all required files exist."""
    required_files = [
        'manage.py',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml',
        'rag_backend/settings.py',
        'rag_backend/urls.py',
        'documents/models.py',
        'documents/admin.py',
    ]
    
    print("Checking required files...")
    all_exist = True
    for file in required_files:
        exists = os.path.exists(file)
        status = "✓" if exists else "✗"
        print(f"  {status} {file}")
        if not exists:
            all_exist = False
    
    return all_exist

if __name__ == '__main__':
    print("=" * 50)
    print("RAG Backend - Phase 1 Setup Verification")
    print("=" * 50)
    
    if check_files():
        print("\n✓ All Phase 1 files are in place!")
        print("\nNext steps:")
        print("1. Run: docker-compose up --build")
        print("2. Create superuser: docker-compose exec web python manage.py createsuperuser")
        print("3. Access admin at: http://localhost:8000/admin")
        sys.exit(0)
    else:
        print("\n✗ Some files are missing. Please check the setup.")
        sys.exit(1)
