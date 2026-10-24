# Monolith Sand Sudoku

> A minimalist, Zen-inspired **Sudoku desktop game** built in Python with Tkinter, featuring a strict **4-color Sand palette**, local logical deduction engine, and **Gemini 3.8 Flash AI Coach**.

---

## ✦ Monolith Sand Palette

Designed for cognitive focus and calm aesthetics without bright or jarring tones:
- **Lightest Cream** (`#EBE2CC`) — Primary background canvas, editable cells, and inverted active buttons.
- **Soft Sand** (`#DED6C1`) — Fixed starting numbers and grid division highlights.
- **Muted Stone** (`#CFC6B1`) — Major 3x3 box borders and selection rings.
- **Deep Taupe** (`#B7B09E`) — High-contrast typography, glyphs, and subtle panel dividers.

## 🧩 Features

- **Puzzle Generation & Validation:** Generates valid, unique-solution Sudoku puzzles with multiple difficulty tiers.
- **Local Logical Deduction Engine:** Computes cell candidates, naked singles, hidden pairs, and detects contradictions instantly without external network calls.
- **Gemini 3.8 Flash AI Coach:**
  - Ask the AI Coach for step-by-step reasoning on the next logical cell without spoiling the entire puzzle.
  - Powered by the Google GenAI Interactions API with seamless offline fallback to the local deduction engine.
- **Keyboard & Mouse Controls:** Complete number pad support, arrow key navigation, cell clearing, and move history undo.

## 🛠️ Getting Started

### Prerequisites

- Python 3.10+ (or Python 3.14+) with Tkinter
- *(Optional)* `google-genai`

### Installation & Run

```bash
# Clone the repository
git clone https://github.com/ZengLLQ/sudoku.git
cd sudoku

# Run the game
python main.py
```

To enable Gemini AI Coach:
```bash
pip install google-genai
export GEMINI_API_KEY="your_api_key"  # Windows PowerShell: $env:GEMINI_API_KEY="your_key"
python main.py
```

## 📄 License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.
