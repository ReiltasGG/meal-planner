import requests
import json
import os
import random
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable
from reportlab.lib import colors
from PIL import Image as PILImage
import io
from dotenv import load_dotenv
load_dotenv()

# ── pantry helpers ──────────────────────────────────────────────
PANTRY_FILE = os.path.join(os.path.dirname(__file__), "pantry.txt")

def load_pantry():
    if not os.path.exists(PANTRY_FILE):
        return []
    with open(PANTRY_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_pantry(ingredients):
    with open(PANTRY_FILE, "w") as f:
        for ing in ingredients:
            f.write(ing + "\n")

def update_pantry(existing):
    print("\nYour current pantry:")
    if existing:
        for i, ing in enumerate(existing, 1):
            print(f"  {i}. {ing}")
    else:
        print("  (empty)")

    print("\nWhat's changed? (press Enter to skip a section)")

    new_items = []
    print("\nAdd new ingredients (comma separated, or press Enter to skip):")
    raw = input("  > ").strip()
    if raw:
        new_items = [i.strip() for i in raw.split(",") if i.strip()]

    remove_items = []
    if existing:
        print("\nAnything you've run out of? (comma separated, or press Enter to skip):")
        raw = input("  > ").strip()
        if raw:
            remove_items = [i.strip().lower() for i in raw.split(",") if i.strip()]

    updated = [i for i in existing if i.lower() not in remove_items]
    updated += new_items
    save_pantry(updated)
    return updated

# ── TheMealDB helpers ───────────────────────────────────────────
CUISINE_MAP = {
    "american": "American",
    "mexican": "Mexican",
    "italian": "Italian",
    "asian": "Chinese",
    "japanese": "Japanese",
    "indian": "Indian",
    "french": "French",
    "mediterranean": "Greek",
    "thai": "Thai",
    "spanish": "Spanish",
    "british": "British",
    "canadian": "Canadian",
}

def get_meals_by_cuisine(cuisine):
    area = CUISINE_MAP.get(cuisine.lower(), cuisine.capitalize())
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?a={area}"
    resp = requests.get(url)
    data = resp.json()
    return data.get("meals") or []

def get_meals_by_category(category):
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={category}"
    resp = requests.get(url)
    data = resp.json()
    return data.get("meals") or []

def get_meal_details(meal_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal_id}"
    resp = requests.get(url)
    data = resp.json()
    meals = data.get("meals")
    return meals[0] if meals else None

def extract_ingredients(meal):
    ingredients = []
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}") or "").strip()
        if ing:
            ingredients.append(f"{measure} {ing}".strip())
    return ingredients

def fetch_meal_pool(cuisine=None, count=40):
    """Fetch a large pool of meals from TheMealDB for Gemma 4 to choose from"""
    meals = []
    if cuisine:
        pool = get_meals_by_cuisine(cuisine)
    else:
        categories = ["Chicken", "Beef", "Seafood", "Vegetarian", "Pasta", "Lamb"]
        pool = []
        for cat in categories:
            pool += get_meals_by_category(cat)

    if not pool:
        return []

    random.shuffle(pool)
    selected = pool[:min(count, len(pool))]

    print(f"Fetching recipe details from TheMealDB...")
    for meal in selected:
        detail = get_meal_details(meal["idMeal"])
        if detail:
            ingredients = extract_ingredients(detail)
            nutrition = get_nutrition(ingredients)
            meals.append({
                "name": detail["strMeal"],
                "id": detail["idMeal"],
                "category": detail.get("strCategory", ""),
                "ingredients": ingredients,
                "nutrition": nutrition,
                "steps": detail.get("strInstructions", ""),
                "image_url": detail.get("strMealThumb", "")
            })

    return meals

# ── Edamam Nutrition ────────────────────────────────────────────
def get_nutrition(ingredients):
    app_id = os.getenv("EDAMAM_APP_ID")
    app_key = os.getenv("EDAMAM_APP_KEY")

    if not app_id or not app_key:
        return None

    url = "https://api.edamam.com/api/nutrition-details"
    headers = {"Content-Type": "application/json"}
    params = {"app_id": app_id, "app_key": app_key}
    body = {"ingr": ingredients}

    try:
        resp = requests.post(url, headers=headers, params=params, json=body, timeout=10)
        data = resp.json()
        if resp.status_code != 200:
            return None

        calories = round(data.get("calories", 0))
        nutrients = data.get("totalNutrients", {})
        protein = round((nutrients.get("PROCNT") or {}).get("quantity", 0))
        carbs = round((nutrients.get("CHOCDF") or {}).get("quantity", 0))
        fat = round((nutrients.get("FAT") or {}).get("quantity", 0))

        if calories == 0 and protein == 0:
            return None

        return f"Calories: {calories} | Protein: {protein}g | Carbs: {carbs}g | Fat: {fat}g"
    except Exception:
        return None

# ── Gemma 4 AI selection ────────────────────────────────────────
def ai_select_meals(meal_pool, pantry, days, meals_per_day, cuisine=None):
    """Use Gemma 4 to intelligently select the best meals based on pantry"""
    total_needed = days * meals_per_day

    # build a simplified meal list to send to Gemma 4
    meal_summary = []
    for i, meal in enumerate(meal_pool):
        meal_summary.append({
            "index": i,
            "name": meal["name"],
            "category": meal["category"],
            "ingredients": meal["ingredients"]
        })

    prompt = f"""You are a smart meal planning assistant.

The user has these ingredients in their pantry: {', '.join(pantry) if pantry else 'nothing yet'}.
They want to plan {total_needed} meals total ({days} days, {meals_per_day} meal(s) per day).
{'They prefer ' + cuisine + ' cuisine.' if cuisine else 'They have no cuisine preference.'}

Here are the available recipes to choose from:
{json.dumps(meal_summary, indent=2)}

Your job is to select exactly {total_needed} meals from the list above that:
1. Best match the ingredients the user already has (minimize missing ingredients)
2. Provide good variety (don't repeat categories)
3. Match their cuisine preference if specified

You MUST return exactly {total_needed} unique indices.

Return ONLY a JSON object, no explanation, no markdown:
{{
  "selected_indices": [0, 5, 12, 3, ...]
}}"""

    print(f"\nAsking Gemma 4 to pick the best {total_needed} meals for your pantry...")

    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "gemma4:e4b",
        "prompt": prompt,
        "stream": False
    })

    raw = response.json()["response"]
    clean = raw.strip().replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(clean)

        # handle both {"selected_indices": [...]} and just [...]
        if isinstance(result, dict):
            indices = result.get("selected_indices") or result.get("indices") or []
        elif isinstance(result, list):
            indices = result
        else:
            indices = []

        # deduplicate while preserving order
        seen = set()
        unique_indices = []
        for i in indices:
            idx = int(i)
            if idx not in seen and idx < len(meal_pool):
                seen.add(idx)
                unique_indices.append(idx)

        selected_indices = unique_indices[:total_needed]

        # always fill up to total_needed if Gemma 4 returned fewer
        if len(selected_indices) < total_needed:
            all_indices = list(range(len(meal_pool)))
            remaining = [i for i in all_indices if i not in seen]
            random.shuffle(remaining)
            selected_indices += remaining[:total_needed - len(selected_indices)]

        return [meal_pool[i] for i in selected_indices]

    except Exception as e:
        print(f"  Gemma 4 parsing failed ({e}), falling back to random selection...")
        indices = random.sample(range(len(meal_pool)), min(total_needed, len(meal_pool)))
        return [meal_pool[i] for i in indices]

# ── meal plan builder ───────────────────────────────────────────
MEAL_TYPES = {
    1: ["Dinner"],
    2: ["Lunch", "Dinner"],
    3: ["Breakfast", "Lunch", "Dinner"],
}

def build_meal_plan(selected_meals, days, meals_per_day):
    meal_plan = []
    meal_index = 0
    meal_types = MEAL_TYPES.get(meals_per_day, ["Meal"] * meals_per_day)
    start_date = datetime.now()

    for day in range(1, days + 1):
        date = start_date + timedelta(days=day - 1)
        day_plan = {
            "day": day,
            "date": date.strftime("%A, %B %d"),
            "meals": []
        }
        for meal_type in meal_types:
            if meal_index < len(selected_meals):
                meal = selected_meals[meal_index].copy()
                meal["type"] = meal_type
                day_plan["meals"].append(meal)
                meal_index += 1
        meal_plan.append(day_plan)

    return meal_plan

# ── grocery list builder ────────────────────────────────────────
def build_grocery_list(meal_plan, pantry):
    all_ingredients = {}
    pantry_lower = [p.lower() for p in pantry]

    for day in meal_plan:
        for meal in day["meals"]:
            for ing in meal["ingredients"]:
                key = ing.strip().lower()
                if key not in all_ingredients:
                    have_it = any(p in key for p in pantry_lower)
                    all_ingredients[key] = {
                        "name": ing,
                        "have": have_it
                    }

    return all_ingredients

# ── PDF export ──────────────────────────────────────────────────
def save_to_pdf(meal_plan, grocery_list, days, meals_per_day):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"meal_plan_{days}days_{timestamp}.pdf"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", fontSize=24, fontName="Helvetica-Bold",
                                  spaceAfter=4, textColor=colors.HexColor("#2C2C2C"))
    subtitle_style = ParagraphStyle("subtitle", fontSize=11, fontName="Helvetica",
                                     spaceBefore=16, spaceAfter=16,
                                     textColor=colors.HexColor("#888888"))
    day_style = ParagraphStyle("day", fontSize=15, fontName="Helvetica-Bold",
                                spaceBefore=16, spaceAfter=6,
                                textColor=colors.HexColor("#333333"))
    meal_type_style = ParagraphStyle("mealtype", fontSize=11, fontName="Helvetica-Bold",
                                      spaceAfter=2, textColor=colors.HexColor("#666666"))
    meal_name_style = ParagraphStyle("mealname", fontSize=13, fontName="Helvetica-Bold",
                                      spaceAfter=4, textColor=colors.HexColor("#1a1a1a"))
    body_style = ParagraphStyle("body", fontSize=10, fontName="Helvetica",
                                 spaceAfter=3, leading=14)
    heading_style = ParagraphStyle("heading", fontSize=14, fontName="Helvetica-Bold",
                                    spaceBefore=16, spaceAfter=8,
                                    textColor=colors.HexColor("#2C2C2C"))

    story = []

    story.append(Paragraph("Meal Plan", title_style))
    story.append(Paragraph(
        f"{days} days • {meals_per_day} meal(s) per day • Generated {datetime.now().strftime('%B %d, %Y')}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#eeeeee")))
    story.append(Spacer(1, 0.2 * inch))

    for day in meal_plan:
        story.append(Paragraph(f"Day {day['day']} — {day['date']}", day_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd")))
        story.append(Spacer(1, 0.1 * inch))

        for meal in day["meals"]:
            story.append(Paragraph(meal["type"], meal_type_style))
            story.append(Paragraph(meal["name"], meal_name_style))

            if meal.get("image_url"):
                try:
                    img_resp = requests.get(meal["image_url"], timeout=5)
                    img_data = PILImage.open(io.BytesIO(img_resp.content))
                    img_buffer = io.BytesIO()
                    img_data.save(img_buffer, format="JPEG")
                    img_buffer.seek(0)
                    img = Image(img_buffer, width=3 * inch, height=2.2 * inch)
                    story.append(img)
                except:
                    pass

            if meal.get("nutrition"):
                story.append(Paragraph(f"<b>Nutrition:</b> {meal['nutrition']}", body_style))
                story.append(Spacer(1, 0.05 * inch))

            story.append(Paragraph("<b>Ingredients:</b>", body_style))
            for ing in meal["ingredients"]:
                story.append(Paragraph(f"• {ing}", body_style))

            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("<b>Instructions:</b>", body_style))
            steps = meal["steps"].replace("\r\n", "\n").split("\n")
            for step in steps:
                step = step.strip()
                if step:
                    story.append(Paragraph(step, body_style))

            story.append(Spacer(1, 0.2 * inch))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#eeeeee")))
    story.append(Paragraph("Grocery List", heading_style))

    need = [v["name"] for v in grocery_list.values() if not v["have"]]
    have = [v["name"] for v in grocery_list.values() if v["have"]]

    if need:
        story.append(Paragraph("<b>To Buy:</b>", body_style))
        for item in need:
            story.append(Paragraph(f"☐ {item}", body_style))
        story.append(Spacer(1, 0.1 * inch))

    if have:
        story.append(Paragraph("<b>Already Have:</b>", body_style))
        for item in have:
            story.append(Paragraph(f"✓ {item}", body_style))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"Generated by meal-planner | TheMealDB + Gemma 4 + Edamam | {datetime.now().strftime('%B %d, %Y')}",
        ParagraphStyle("footer", fontSize=8, textColor=colors.grey)
    ))

    doc.build(story)
    return filename

# ── main ─────────────────────────────────────────────────────────
def main():
    print("=== Meal Planner ===\n")

    # load and update pantry
    existing = load_pantry()
    pantry = update_pantry(existing)

    # ask how many days
    while True:
        try:
            days = int(input("\nHow many days do you want to plan? (1-7): ").strip())
            if 1 <= days <= 7:
                break
            print("Please enter a number between 1 and 7.")
        except ValueError:
            print("Please enter a valid number.")

    # ask meals per day
    print("\nHow many meals per day?")
    print("  1 = Dinner only")
    print("  2 = Lunch + Dinner")
    print("  3 = Breakfast + Lunch + Dinner")
    while True:
        try:
            meals_per_day = int(input("Enter 1, 2, or 3: ").strip())
            if meals_per_day in [1, 2, 3]:
                break
            print("Please enter 1, 2, or 3.")
        except ValueError:
            print("Please enter a valid number.")

    # ask cuisine preference
    print("\nDo you have a cuisine preference for this week?")
    print("Options: American, Mexican, Italian, Asian, Japanese, Indian, French, Thai, Spanish, British")
    print("Or press Enter for a mix of everything")
    cuisine = input("Enter cuisine or press Enter to skip: ").strip()

    # fetch meal pool from TheMealDB
    print("\nFetching recipes from TheMealDB...")
    meal_pool = fetch_meal_pool(cuisine=cuisine if cuisine else None, count=40)

    if not meal_pool:
        print("Could not fetch recipes. Check your internet connection.")
        return

    print(f"Found {len(meal_pool)} recipes.")

    # use Gemma 4 to intelligently select meals
    selected_meals = ai_select_meals(
        meal_pool, pantry, days, meals_per_day,
        cuisine=cuisine if cuisine else None
    )

    if not selected_meals:
        print("Could not select meals. Try again.")
        return

    # build meal plan
    meal_plan = build_meal_plan(selected_meals, days, meals_per_day)

    # display meal plan
    print("\n=== YOUR MEAL PLAN ===\n")
    for day in meal_plan:
        print(f"[ Day {day['day']} — {day['date']} ]")
        for meal in day["meals"]:
            print(f"  {meal['type']}: {meal['name']}")
        print()

    # build and display grocery list
    grocery_list = build_grocery_list(meal_plan, pantry)
    need = {k: v for k, v in grocery_list.items() if not v["have"]}
    have = {k: v for k, v in grocery_list.items() if v["have"]}

    print("=== GROCERY LIST ===\n")
    print(f"To buy ({len(need)} items):")
    for item in need.values():
        print(f"  [ ] {item['name']}")

    if have:
        print(f"\nAlready have ({len(have)} items):")
        for item in have.values():
            print(f"  [✓] {item['name']}")

    # save PDF
    print("\nSaving meal plan as PDF...")
    filename = save_to_pdf(meal_plan, grocery_list, days, meals_per_day)
    print(f"\n✅ Meal plan saved to: {filename}")

if __name__ == "__main__":
    main()