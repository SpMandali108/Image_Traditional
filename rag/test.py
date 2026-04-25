from generator import generate_answer

print("🤖 RAG Bot Ready (type 'exit' to quit)\n")

while True:
    query = input("You: ")

    if query.lower() == "exit":
        break

    answer = generate_answer(query)

    print("Bot:", answer, "\n")