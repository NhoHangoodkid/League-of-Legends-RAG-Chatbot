"""
⚔️ League of Legends RAG Knowledge Bot — Interactive CLI Interface.

Usage:
    python app/cli.py
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
app_dir = Path(__file__).resolve().parent
project_root = app_dir.parent
src_dir = project_root / "src"

for p in [str(project_root), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chatbot.bot import LoLBot, get_bot


def main():
    print("⚔️  LEAGUE OF LEGENDS RAG KNOWLEDGE BOT — CLI")
    print("Khởi động hệ thống (FAISS Vector + Neo4j Graph + Cross-Encoder)...")

    bot = get_bot()

    print("\n[OK] Hệ thống đã sẵn sàng!")
    print("Gõ câu hỏi của bạn (EN hoặc VI). Nhập 'exit', 'quit' hoặc 'q' để thoát.")
    print("Nhập 'clear' để xóa lịch sử hội thoại.")

    while True:
        try:
            query = input("\n🧑‍💻 Bạn: ").strip()
            if not query:
                continue

            if query.lower() in ("exit", "quit", "q"):
                print("\n👋 Tạm biệt Summoner! Hẹn gặp lại trên Đấu Trường Công Lý.")
                break

            if query.lower() == "clear":
                bot.reset_conversation()
                print("\n🧹 Đã xóa sạch ngữ cảnh hội thoại.")
                continue

            t0 = time.time()
            ans = bot.answer(query)
            elapsed_ms = (time.time() - t0) * 1000

            print(f"\n⚙️ [Intent: {ans.get('intent')}] [Latency: {elapsed_ms:.1f}ms] [RAG Contexts: {len(ans.get('rag_contexts', []))}]")
            print("⚔️ Bot:")
            print(ans.get("response", ""))

        except KeyboardInterrupt:
            print("\n\n👋 Tạm biệt Summoner!")
            break
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")


if __name__ == "__main__":
    main()
