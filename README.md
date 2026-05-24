# meal-planner 🗓️

A terminal-based AI meal planner powered by **Gemma 4**, **TheMealDB**, and **Edamam**. Enter your pantry ingredients and get a personalized weekly meal plan with nutrition info exported to a clean PDF — all running locally on your machine.

---

## How It Works

1. **Pantry memory** — your ingredients are saved locally and updated each session
2. **Cuisine preference** — optionally filter meals by cuisine type
3. **TheMealDB** fetches a pool of 40 real recipes
4. **Gemma 4** intelligently selects the best meals based on what you already have
5. **Edamam** calculates nutrition info (calories, protein, carbs, fat) for each meal
6. A clean **PDF** is generated with your full meal plan, recipes, and grocery list

---

## Features

- Plan 1–7 days of meals
- Choose 1, 2, or 3 meals per day (Dinner / Lunch+Dinner / Breakfast+Lunch+Dinner)
- Cuisine filter: American, Mexican, Italian, Asian, Japanese, Indian, French, Thai, Spanish, British
- Pantry saved to `pantry.txt` — just update what's changed each session
- Grocery list automatically cross-references your pantry and shows only what you're missing
- PDF export includes meal images, nutrition info, ingredients, and step-by-step instructions

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3 | Core language |
| Ollama + Gemma 4 | Local AI for smart meal selection |
| TheMealDB API | Real recipe data, images, and instructions |
| Edamam Nutrition API | Calorie and macro breakdown per meal |
| reportlab | PDF generation |
| Pillow | Image processing for PDF |
| requests | HTTP requests |
| python-dotenv | Secure API key management |

---

## Setup

**Requirements:**
- Python 3
- [Ollama](https://ollama.com) with `gemma4:e4b` installed
- Free API keys from [Edamam](https://developer.edamam.com) (Nutrition Analysis API)
- Internet connection (for TheMealDB and Edamam)

**1. Clone the repo**
```bash
git clone https://github.com/ReiltasGG/meal-planner.git
cd meal-planner
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install requests reportlab pillow python-dotenv
```

**4. Create a `.env` file in the project folder**
```
EDAMAM_APP_ID=your_app_id_here
EDAMAM_APP_KEY=your_app_key_here
```

Get your free keys at: https://developer.edamam.com (sign up → Nutrition Analysis API → create app)

**5. Check your Ollama model name**
```bash
ollama list
```
Open `meal_planner.py` and update this line to match your model name:
```python
"model": "gemma4:e4b",  # replace with your model name from ollama list
```

**6. Start Ollama**
```bash
ollama serve
```

---

## Usage

```bash
python meal_planner.py
```

---

## Project Structure

```
meal-planner/
├── meal_planner.py     # Main script
├── pantry.txt          # Your saved pantry (auto-generated, not tracked by git)
├── .env                # Your Edamam API keys (not tracked by git)
├── .gitignore
└── README.md
```

---

## Notes

- `pantry.txt` and `.env` are excluded from git for privacy
- Generated PDFs are excluded from git
- Nutrition info may not appear for some meals if Edamam cannot parse the ingredients
- Requires Ollama to be running locally before executing the script

---

*Built on a Mac with an Apple M1 Pro using Python, Ollama, Gemma 4, TheMealDB, and Edamam — running fully locally.*