import os
import pickle
import faiss
from sklearn.feature_extraction.text import TfidfVectorizer

BASE_DIR = os.path.dirname(__file__)

data_path = os.path.join(BASE_DIR, "..", "data", "sample.txt")
store_path = os.path.join(BASE_DIR, "..", "vector_store")

os.makedirs(store_path, exist_ok=True)

# Load data
with open(data_path, "r", encoding="utf-8") as f:
    documents = [line.strip() for line in f.readlines() if line.strip()]

# Vectorize
vectorizer = TfidfVectorizer()
vectors = vectorizer.fit_transform(documents).toarray()

# FAISS index
index = faiss.IndexFlatL2(vectors.shape[1])
index.add(vectors)

# Save everything
with open(os.path.join(store_path, "vectorizer.pkl"), "wb") as f:
    pickle.dump(vectorizer, f)

with open(os.path.join(store_path, "chunks.pkl"), "wb") as f:
    pickle.dump(documents, f)

faiss.write_index(index, os.path.join(store_path, "index.faiss"))

print("✅ Ingestion complete")