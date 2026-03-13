import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH            = os.getenv("DB_PATH", "medisafe.db")
INDIA_COMBOS_PATH  = os.getenv("INDIA_COMBOS_PATH", "india_combos.json")
CEREBRAS_API_KEY   = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_MODEL     = "llama3.1-8b"
LLM_TIMEOUT        = 30   # seconds — keeps total response well under 1 min
RAG_CHUNK_LIMIT    = 6    # chunks retrieved per drug pair
FUZZY_CUTOFF       = 94   # rapidfuzz WRatio score (0-100)
