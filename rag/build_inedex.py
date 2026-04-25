import os
import json
import re

BASE_DIR = os.path.dirname(__file__)

products_path = os.path.join(BASE_DIR, "..", "website", "static", "products")
output_file = os.path.join(BASE_DIR, "qa_data.json")

qa_data = []
seen = set()   # prevent duplicates


for root, dirs, files in os.walk(products_path):
    relative_path = os.path.relpath(root, products_path)
    categories = relative_path.split(os.sep)

    for file in files:
        name, _ = os.path.splitext(file)

        # 🔥 remove suffix like _1, _2, _10
        name = re.sub(r'_\d+$', '', name)

        # clean names
        item = name.replace("_", " ").strip().lower()
        item_title = name.replace("_", " ").strip().title()

        # 🔥 get subcategory (Bhagwan, Superhero, etc.)
        if len(categories) >= 2:
            subcategory = categories[1]
        elif len(categories) == 1:
            subcategory = categories[0]
        else:
            subcategory = "General"

        # 🔥 avoid duplicates
        key = (item, subcategory)
        if key in seen:
            continue
        seen.add(key)

        # 🔥 FINAL CUSTOMER RESPONSE FORMAT
        answer_text = (
            f"Yes, we do offer {item_title} dress under {subcategory} category! "
            "For booking, you can contact us or visit our shop."
        )

        # 🔥 generate variations
        qa_data.append({
            "query": f"{item} dress",
            "answer": answer_text,
            "category": subcategory
        })

        qa_data.append({
            "query": f"{item} costume",
            "answer": answer_text,
            "category": subcategory
        })

        qa_data.append({
            "query": f"{item} for kids",
            "answer": answer_text,
            "category": subcategory
        })


# save file
with open(output_file, "w") as f:
    json.dump(qa_data, f, indent=2)

print(f"✅ Generated {len(qa_data)} QA entries (clean + customer-ready)")