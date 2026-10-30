"""Automatic static audit: bugs, security holes, optimization, modularization, scalability."""
from .checks import audit_file, audit_tree, Finding
from .report import render_report, score
__all__ = ["audit_file", "audit_tree", "Finding", "render_report", "score"]
