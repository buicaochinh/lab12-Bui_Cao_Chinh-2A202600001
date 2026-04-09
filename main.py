import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agent import graph


def run():
    print("=" * 55)
    print("  Vinmec AI - Tro ly dat lich kham")
    print("  Go 'quit' de thoat")
    print("=" * 55)

    history = []

    while True:
        user_input = input("\nBan: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q", "thoat"):
            print("Tam biet! Chuc ban suc khoe.")
            break

        history.append(("human", user_input))

        result = graph.invoke({"messages": history})
        final = result["messages"][-1]

        print(f"\nVinmec: {final.content}")

        history = [(m.type, m.content) for m in result["messages"]
                   if hasattr(m, "type") and m.type in ("human", "ai")
                   and m.content]


if __name__ == "__main__":
    run()