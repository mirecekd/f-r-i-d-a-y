# backend/app/files/__init__.py
"""Any file can be dropped: type detection, text extraction, the file_card tile and the model tools."""

from app.files.tools import register_file_tools
from app.files.upload import router

__all__ = ["register_file_tools", "router"]
