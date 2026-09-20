"""
⚔️ League of Legends RAG Knowledge Bot — CLI
Located at: src/chatbot/cli.py

Run command:
    python src/chatbot/cli.py
"""

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding = "utf-8")
        sys.stderr.reconfigure(encoding = "utf-8")
    except Exception:
        pass

# Ensure project root and src/ are on sys.path
chatbot_dir = Path(__file__).resolve().parent
src_dir = chatbot_dir.parent
project_root = src_dir.parent

for p in [str(project_root), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chatbot.bot import LoLBot, get_bot


def main():
    print("⚔️  LEAGUE OF LEGENDS RAG KNOWLEDGE BOT — CLI")
    print("Initializing system (FAISS Vector + Neo4j Graph + Cross-Encoder)...")

    bot = get_bot()

    print("\n[OK] System is ready!")
    print("Type your question in English. Enter 'exit', 'quit', or 'q' to quit.")
    print("Enter 'clear' to reset conversation history.")

    while True:
        try:
            query = input("\n🧑‍💻 You: ").strip()
            if not query:
                continue

            if query.lower() in ("exit", "quit", "q"):
                print("\n👋 Goodbye Summoner! See you on the Rift.")
                break

            if query.lower() == "clear":
                bot.reset_conversation()
                print("\n🧹 Conversation context cleared.")
                continue

            t0 = time.time()
            ans = bot.answer(query)
            elapsed_ms = (time.time() - t0) * 1000

            print(f"\n⚙️ [Intent: {ans.get('intent')}] [Latency: {elapsed_ms:.1f}ms] [RAG Contexts: {len(ans.get('rag_contexts', []))}]")
            print("⚔️ Bot:")
            print(ans.get("response", ""))

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye Summoner!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
