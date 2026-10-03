from app.agent import CineDataAgent


def main():
    agent = CineDataAgent()

    print("CineData Analytics — Text-to-SQL")
    print("Digite 'sair' para encerrar.\n")

    while True:
        try:
            question = input("Pergunta> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if question.lower() in {"sair", "exit", "quit"}:
            break

        if not question:
            continue

        try:
            print("\n" + agent.answer_text(question) + "\n")
        except Exception as exc:
            print(f"\nErro: {exc}\n")


if __name__ == "__main__":
    main()