from flask import Blueprint, request, jsonify
from rag.generator import generate_answer

chatbot = Blueprint("chatbot", __name__)

@chatbot.route("/chat", methods=["POST"])
def chat_api():
    try:
        user_msg = request.json.get("message")
        reply = generate_answer(user_msg)
        return jsonify({"reply": reply})
    except Exception as e:
        print("ERROR:", e)
        return jsonify({"reply": "Server error occurred"})