from __future__ import annotations

import argparse

from it_assistant.agent import ITSupportAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Local AI IT Support Assistant")
    parser.add_argument("request", nargs="*", help="Employee support request")
    args = parser.parse_args()

    agent = ITSupportAgent()
    if args.request:
        print(agent.handle(" ".join(args.request)))
        return

    print("AI IT Support Assistant. Type 'exit' to quit.")
    while True:
        try:
            request = input("> ").strip()
        except EOFError:
            break
        if request.lower() in {"exit", "quit"}:
            break
        if not request:
            continue
        print(agent.handle(request))


if __name__ == "__main__":
    main()
