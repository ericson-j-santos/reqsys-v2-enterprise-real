"""Entry point para uvicorn: uvicorn reqsys_ollama_gateway.main:app --host 0.0.0.0 --port 8008"""

from .app import app

__all__ = ['app']
