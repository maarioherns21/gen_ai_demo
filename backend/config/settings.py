from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI (optional until you enable LLM agents)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")

# Amadeus
AMADEUS_BASE = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

# App
APP_ENV = os.getenv("APP_ENV", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")