# ⚔️ League of Legends Hybrid GraphRAG AI Assistant

A production-grade **Hybrid GraphRAG** tactical coach and conversational assistant for **League of Legends**, combining **Neo4j Knowledge Graph**, **fine-tuned LoRA dense retrieval (FAISS)**, **cross-encoder neural re-ranking**, and **multi-store persistence** behind a sleek **Void Glassmorphism UI**.

![League of Legends Hybrid GraphRAG Assistant Demo](./assets/demo.gif)

---

## 🛠️ Tools & Technologies Used

The assistant is built on a high-performance, modular AI & Data ecosystem:

* **LLM Inference**: **[Ollama](https://ollama.com/)** running **Qwen 2.5 / 3 4B** locally for fast, privacy-preserving tactical reasoning and conversational synthesis.
* **Knowledge Graph**: **[Neo4j](https://neo4j.com/)** with **Cypher** queries to traverse complex multi-hop relationships (champion counters, duo synergies, item builds, and team composition dynamics).
* **Vector Store**: **[Meta FAISS](https://github.com/facebookresearch/faiss)** (`faiss-cpu`) providing sub-millisecond dense semantic retrieval across 2,500+ tactical knowledge chunks.
* **Domain Embeddings**: **`BAAI/bge-small-en-v1.5`** fine-tuned via **LoRA (PEFT)** on curated League of Legends domain triplets.
* **Neural Re-ranker**: **`cross-encoder/ms-marco-MiniLM-L-6-v2`** to score and prioritize combined graph and vector candidates before generation.
* **Document Store**: **[MongoDB](https://www.mongodb.com/)** storing unified JSON schemas for 173 champions, 254 items, rune trees, and detailed ability mechanics.
* **Chat Persistence**: **[PostgreSQL](https://www.postgresql.org/)** managing conversation histories, user sessions, and latency metrics.
* **Frontend UI**: **[Streamlit](https://streamlit.io/)** crafted with custom Void Glassmorphism styling (Kai'Sa aesthetic), recommendation cards, and session history management.
* **ETL & Data Gathering**: **Requests**, **BeautifulSoup4**, and **PyYAML** ingesting and merging multi-source data from Riot Data Dragon, Community Dragon, Meraki Analytics, OP.GG, and Blitz.gg.

---

## ⚡ Quick Start

### 1. Prerequisites
Ensure you have the following minimum versions installed and running:
* **Python**: `>= 3.10`
* **Ollama**: `>= 0.1.30`
* **MongoDB**: `>= 6.0`
* **Neo4j**: `>= 5.0`
* **PostgreSQL**: `>= 14.0`

### 2. Installation & Environment
```bash
# Clone & install dependencies
git clone https://github.com/your-username/Learning-English-ChatBot.git
cd "Learning-English-ChatBot"
python -m venv venv
.\venv\Scripts\activate   # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```
*(Edit `.env` with your database credentials and Ollama endpoint if different from default)*.

### 3. Launch the Application
```bash
# Web UI (Streamlit - Recommended)
streamlit run app/streamlit_app.py

# Or Terminal CLI
python app/cli.py
```
Access the web interface at **`http://localhost:8501`**.

---

## License & Disclaimer

* **License**: MIT License.
* **Disclaimer**: This project is not affiliated with or endorsed by Riot Games. League of Legends and all related assets are trademarks or registered trademarks of Riot Games, Inc.
