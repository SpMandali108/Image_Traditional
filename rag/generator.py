from pymongo import MongoClient
from rapidfuzz import process
import os
from dotenv import load_dotenv
from google import genai
from .retriver import retrive

load_dotenv()

# 🔹 MongoDB setup
mongo_client = MongoClient(os.getenv("client"))
db = mongo_client["Image_Traditional"]
collection = db["chat_cache"]

# 🔹 Gemini setup (NEW SDK)
client = genai.Client(api_key=os.getenv("CHATKEY"))

def is_greeting(query):
    greetings = ["hi", "hello", "hey", "namaste"]
    words = query.lower().split()
    return any(word in greetings for word in words)

def handle_general_queries(query):
    query = query.lower()

    if "price" in query or "pricing" in query or "cost" in query or "rate" in query:
        return (
            "Our pricing is as follows:\n\n"
            "• Kediya: ₹500 to ₹3500 per day\n\n"
            "• Chaniya Choli: ₹500 to ₹3500 per day\n\n"
            "• Fancy Dress: starting from ₹200 per day\n\n"
            "Pricing may vary depending on design and costume."
        )

    if "timing" in query or "time" in query:
        return "Our shop is open from 9:00 AM to 9:00 PM."

    if "offer" in query or "services" in query:
        return (
            "We offer rental of Kediya, Chaniya Choli, and Fancy Dress.\n"
            "We also provide group costumes require for school events, college events, etc.  "
            "We also provide bulk safa in weddind and religious events"
            "We also provide sublimation printing on T-shirts, mugs, keychains, pillows, bottles, and corporate gifts."
        )

    if "contact" in query or "phone" in query or "number" in query:
        return "You can contact us at 9428610384."

    if "location" in query or "where" in query or "address" in query:
        return (
        "📍 We are located in Ahmedabad, Gujarat.\n"
        "You can find us here:\n"
        "https://www.google.com/maps/search/?api=1&query=Image+Traditional+Ahmedabad"
    )

    if "wedding" in query or "sherwani" in query or "marraige" in query:
        return "Sorry, we do not provide wedding rentals."

    return None
def generate_answer(query):
    query = query.lower().strip()

    # 🔥 1. Greeting
    if is_greeting(query):
        return "Hello! 👋 How can I help you today?"

    # 🔥 2. General queries (FIX HERE)
    general = handle_general_queries(query)
    if general:
        return general

    # 🔥 3. Product DB (fuzzy)
    data = list(collection.find())
    queries = [d["query"] for d in data]

    match, score, idx = process.extractOne(query, queries)

    print(f"🔎 Match: {match} | Score: {score}")

    if score >= 85:
        return data[idx]["answer"]

    # 🔥 4. sample.txt fallback
    sample_results = retrive(query)
    if sample_results:
        return "Here’s what I found:\n" + "\n".join(sample_results)

    # 🔥 5. final fallback
    return (
        "Sorry, we couldn't find that.\n"
        "📍 Visit our store in Ahmedabad\n"
        "📞 Call: 9428610384"
    )