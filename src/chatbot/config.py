"""
Chatbot Configuration.

LLM: Qwen 8B via Ollama (OpenAI-compatible API)
Language: English queries, English responses
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration (Qwen 3 8B via Ollama)
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
llm_model = os.getenv("LLM_MODEL", "qwen3:4b-chat")

# Paths
project_root = Path(__file__).parent.parent
data_dir = project_root / "data"
knowledge_base_dir = data_dir / "knowledge_base"
champions_kb_dir = knowledge_base_dir / "champions"
processors_dir = project_root / "processors"
processed_dir = processors_dir / "processed"

# Chatbot Settings
max_history_turns = 6
llm_temperature = 0.4

llm_num_ctx = int(os.getenv("LLM_NUM_CTX", "4096"))
llm_num_predict = int(os.getenv("LLM_NUM_PREDICT", "2048"))

response_language = "English"

# Neo4j Graph DB
neo4j_uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
neo4j_user = os.getenv("NEO4J_USER", "neo4j")
neo4j_password = os.getenv("NEO4J_PASSWORD") or os.getenv("neo4j_password") or ""
neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

# Vector and Embeddings
embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
vector_index_dir = data_dir / "vector_index"
lora_adapter_dir = project_root / "models" / "lora_embedding"

# Retrieval Settings
enable_graph_rag = os.getenv("ENABLE_GRAPH_RAG", "false").lower() == "true"
enable_vector_rag = os.getenv("ENABLE_VECTOR_RAG", "true").lower() == "true"
enable_reranker = os.getenv("ENABLE_RERANKER", "true").lower() == "true"

graph_top_k = 10
vector_top_k = 10
rerank_top_k = 5
rrf_k = 60
