import os

BASE_DIR = os.path.dirname(__file__)
file_path = os.path.join(BASE_DIR, "..", "data", "sample.txt")


def load_sample():
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


data = load_sample()


def retrive(query):
    query = query.lower()

    results = []

    for line in data:
        if any(word in line.lower() for word in query.split()):
            results.append(line)

    return results[:3]   # top 3 lines