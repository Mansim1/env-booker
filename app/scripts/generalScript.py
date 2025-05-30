#!/usr/bin/env python3
import os
import sys

# Add project root to PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import Environment

app = create_app("development")
with app.app_context():
    db.drop_all()      # drops ALL tables defined in your metadata
    db.create_all() 