#!/usr/bin/env python3
"""
Monolith Sand Sudoku — Single-File Python Application
Strictly uses only the 4-color palette:
  - #EBE2CC (Lightest Cream)
  - #DED6C1 (Soft Sand)
  - #CFC6B1 (Muted Stone)
  - #B7B09E (Deep Taupe)

Includes optional Gemini AI Coach powered by `google-genai` Interactions API
(`client.interactions.create` with `gemini-3.8-flash` & `previous_interaction_id`),
with automatic offline fallback to the local logical deduction engine.
"""

import copy
import os
import random
import threading
import time
import tkinter as tk

# Optional Google GenAI SDK (Gemini Interactions API)
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ============================================================================
# STRICT 4-COLOR PALETTE (No other colors exist in this application)
# ============================================================================
C_LIGHTEST = "#EBE2CC"  # Primary background, editable cells, inverted text on dark
C_LIGHT    = "#DED6C1"  # Alternating 3x3 boxes, panels, hover states
C_MEDIUM   = "#CFC6B1"  # Peer highlights, thin grid lines, secondary fills
C_DARKEST  = "#B7B09E"  # Primary text, thick borders, active/selected fills


class SudokuEngine:
    """Pure Python backtracking Sudoku generator, solver, and logical hint analyzer."""

    @staticmethod
    def is_valid(board, row, col, num):
        for i in range(9):
            if board[row][i] == num or board[i][col] == num:
                return False
        box_r, box_c = (row // 3) * 3, (col // 3) * 3
        for r in range(box_r, box_r + 3):
            for c in range(box_c, box_c + 3):
                if board[r][c] == num:
                    return False
        return True

    @classmethod
    def solve(cls, board, randomize=False):
        for r in range(9):
            for c in range(9):
                if board[r][c] == 0:
                    digits = list(range(1, 10))
                    if randomize:
                        random.shuffle(digits)
                    for num in digits:
                        if cls.is_valid(board, r, c, num):
                            board[r][c] = num
                            if cls.solve(board, randomize):
                                return True
                            board[r][c] = 0
                    return False
        return True

    @classmethod
    def count_solutions(cls, board, limit=2):
        count = 0

        def backtrack():
            nonlocal count
            if count >= limit:
                return
            for r in range(9):
                for c in range(9):
                    if board[r][c] == 0:
                        for num in range(1, 10):
                            if cls.is_valid(board, r, c, num):
                                board[r][c] = num
                                backtrack()
                                board[r][c] = 0
                        return
            count += 1

        backtrack()
        return count

    @classmethod
    def generate_puzzle(cls, difficulty="Medium"):
        solution = [[0] * 9 for _ in range(9)]
        cls.solve(solution, randomize=True)
        puzzle = copy.deepcopy(solution)

        removals_map = {"Easy": 36, "Medium": 46, "Hard": 53}
        target_removals = removals_map.get(difficulty, 46)

        positions = [(r, c) for r in range(9) for c in range(9)]
        random.shuffle(positions)

        removed = 0
        for r, c in positions:
            if removed >= target_removals:
                break
            backup = puzzle[r][c]
            puzzle[r][c] = 0

            test_board = copy.deepcopy(puzzle)
            if cls.count_solutions(test_board, limit=2) == 1:
                removed += 1
            else:
                puzzle[r][c] = backup

        return puzzle, solution

    @classmethod
    def find_logical_hint(cls, board, solution):
        """Finds a Naked Single, Hidden Single, or fallback cell with explanation."""
        # 1. Check Naked Singles (cell with only 1 legal candidate)
        for r in range(9):
            for c in range(9):
                if board[r][c] == 0:
                    candidates = [
                        n for n in range(1, 10) if cls.is_valid(board, r, c, n)
                    ]
                    if len(candidates) == 1:
                        val = candidates[0]
                        return (
                            r,
                            c,
                            val,
                            f"Naked Single at R{r+1}C{c+1}: only {val} fits legally.",
                        )

        # 2. Check Hidden Singles in rows
        for r in range(9):
            for num in range(1, 10):
                if num not in board[r]:
                    possible_cols = [
                        c
                        for c in range(9)
                        if board[r][c] == 0 and cls.is_valid(board, r, c, num)
                    ]
                    if len(possible_cols) == 1:
                        c = possible_cols[0]
                        return (
                            r,
                            c,
                            num,
                            f"Hidden Single in Row {r+1}: {num} can only go in R{r+1}C{c+1}.",
                        )

        # 3. Fallback to first empty cell from solution
        for r in range(9):
            for c in range(9):
                if board[r][c] == 0:
                    val = solution[r][c]
                    return (
                        r,
                        c,
                        val,
                        f"Deduction target at R{r+1}C{c+1}: place {val}.",
                    )
        return None


class GeminiSudokuCoach:
    """
    AI Coach powered by the `google-genai` Interactions API.
    Uses `client.interactions.create` with `gemini-3.8-flash` and preserves
    conversation context via `previous_interaction_id`.
    """

    def __init__(self):
        self.client = None
        self.previous_interaction_id = None
        if HAS_GENAI and os.environ.get("GEMINI_API_KEY"):
            try:
                self.client = genai.Client()
            except Exception:
                self.client = None

    def reset_session(self):
        self.previous_interaction_id = None

    def request_hint(self, board, local_hint_tuple, callback):
        if not self.client:
            r, c, val, reason = local_hint_tuple
            callback(r, c, val, f"[Local Coach] {reason}")
            return

        def worker():
            r, c, val, reason = local_hint_tuple
            grid_str = "\n".join(
                " ".join(str(x) if x != 0 else "." for x in row) for row in board
            )
            prompt = (
                "You are a concise Sudoku strategy coach. "
                f"Current 9x9 board ('.' is empty):\n{grid_str}\n\n"
                f"Target move: Row {r+1}, Column {c+1} = {val}. "
                "Explain in ONE short sentence (max 18 words) why this move works "
                "by referencing its row, column, or 3x3 box constraints."
            )
            try:
                kwargs = {
                    "model": "gemini-3.8-flash",
                    "input": prompt,
                }
                if self.previous_interaction_id:
                    kwargs["previous_interaction_id"] = self.previous_interaction_id

                interaction = self.client.interactions.create(**kwargs)
                self.previous_interaction_id = interaction.id
                text = (interaction.output_text or "").strip().replace("\n", " ")
                if not text:
                    text = reason
                callback(r, c, val, f"[Gemini 3.8] {text}")
            except Exception:
                callback(r, c, val, f"[Local Coach] {reason}")

        threading.Thread(target=worker, daemon=True).start()


class SudokuApp:
    """Custom Canvas-rendered Sudoku GUI strictly adhering to the 4-color palette."""

    WIDTH = 820
    HEIGHT = 640
    BOARD_X = 36
    BOARD_Y = 92
    CELL_SIZE = 54
    BOARD_PX = CELL_SIZE * 9  # 486px

    def __init__(self, root):
        self.root = root
        self.root.title("SUDOKU // MONOLITH EDITION")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=C_LIGHTEST)

        self.coach = GeminiSudokuCoach()
        self.difficulty = "Medium"
        self.notes_mode = False
        self.selected = (0, 0)
        self.mistakes = 0
        self.start_time = time.time()
        self.elapsed_paused = 0
        self.game_won = False
        self.ai_busy = False
        self.status_message = "Click a cell or use Arrow keys. Press N for Notes."
        self.hovered_btn = None
        self.buttons = []

        self.puzzle = [[0] * 9 for _ in range(9)]
        self.board = [[0] * 9 for _ in range(9)]
        self.solution = [[0] * 9 for _ in range(9)]
        self.given = [[False] * 9 for _ in range(9)]
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.history = []

        self.canvas = tk.Canvas(
            self.root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=C_LIGHTEST,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Event bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.root.bind("<Key>", self.on_key)

        self.new_game(self.difficulty)
        self.tick_timer()

    # ------------------------------------------------------------------------
    # GAME STATE MANAGEMENT
    # ------------------------------------------------------------------------
    def new_game(self, difficulty=None):
        if difficulty:
            self.difficulty = difficulty
        self.status_message = f"Generating {self.difficulty.upper()} puzzle..."
        self.render()
        self.root.update_idletasks()

        self.puzzle, self.solution = SudokuEngine.generate_puzzle(self.difficulty)
        self.board = copy.deepcopy(self.puzzle)
        self.given = [[self.puzzle[r][c] != 0 for c in range(9)] for r in range(9)]
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.history.clear()
        self.mistakes = 0
        self.game_won = False
        self.start_time = time.time()
        self.coach.reset_session()

        # Select first empty cell
        for r in range(9):
            for c in range(9):
                if not self.given[r][c]:
                    self.selected = (r, c)
                    break
            else:
                continue
            break

        mode_tag = "Gemini 3.8 Ready" if self.coach.client else "Offline Coach Ready"
        self.status_message = f"New {self.difficulty} game started ({mode_tag})."
        self.render()

    def save_snapshot(self):
        self.history.append(
            (
                copy.deepcopy(self.board),
                [[ set(s) for s in row ] for row in self.notes],
            )
        )

    def undo(self):
        if not self.history or self.game_won:
            self.status_message = "Nothing to undo."
            self.render()
            return
        self.board, self.notes = self.history.pop()
        self.status_message = "Reverted last action."
        self.render()

    def set_number(self, num):
        if self.game_won or not self.selected:
            return
        r, c = self.selected
        if self.given[r][c]:
            self.status_message = "Locked clue cell cannot be modified."
            self.render()
            return

        self.save_snapshot()

        if num == 0:
            self.board[r][c] = 0
            self.notes[r][c].clear()
            self.status_message = f"Cleared R{r+1}C{c+1}."
            self.render()
            return

        if self.notes_mode:
            if self.board[r][c] != 0:
                self.board[r][c] = 0
            if num in self.notes[r][c]:
                self.notes[r][c].remove(num)
                self.status_message = f"Removed note {num} at R{r+1}C{c+1}."
            else:
                self.notes[r][c].add(num)
                self.status_message = f"Added note {num} at R{r+1}C{c+1}."
        else:
            if self.board[r][c] == num:
                self.board[r][c] = 0
                self.status_message = f"Cleared {num} from R{r+1}C{c+1}."
            else:
                self.board[r][c] = num
                self.notes[r][c].clear()
                if num != self.solution[r][c]:
                    self.mistakes += 1
                    self.status_message = (
                        f"Conflict alert: {num} at R{r+1}C{c+1} does not match solution."
                    )
                else:
                    self.clear_peer_notes(r, c, num)
                    self.status_message = f"Placed {num} at R{r+1}C{c+1}."
                    self.check_victory()

        self.render()

    def clear_peer_notes(self, row, col, num):
        for i in range(9):
            self.notes[row][i].discard(num)
            self.notes[i][col].discard(num)
        br, bc = (row // 3) * 3, (col // 3) * 3
        for r in range(br, br + 3):
            for c in range(bc, bc + 3):
                self.notes[r][c].discard(num)

    def has_conflict(self, row, col):
        val = self.board[row][col]
        if val == 0:
            return False
        for i in range(9):
            if i != col and self.board[row][i] == val:
                return True
            if i != row and self.board[i][col] == val:
                return True
        br, bc = (row // 3) * 3, (col // 3) * 3
        for r in range(br, br + 3):
            for c in range(bc, bc + 3):
                if (r != row or c != col) and self.board[r][c] == val:
                    return True
        if not self.given[row][col] and val != self.solution[row][col]:
            return True
        return False

    def check_victory(self):
        for r in range(9):
            for c in range(9):
                if self.board[r][c] != self.solution[r][c]:
                    return
        self.game_won = True
        self.elapsed_paused = int(time.time() - self.start_time)
        self.status_message = (
            f"PUZZLE SOLVED in {self.format_time(self.elapsed_paused)} "
            f"with {self.mistakes} mistakes!"
        )

    def request_ai_hint(self):
        if self.game_won or self.ai_busy:
            return
        hint = SudokuEngine.find_logical_hint(self.board, self.solution)
        if not hint:
            self.status_message = "No empty cells remaining."
            self.render()
            return

        self.ai_busy = True
        self.status_message = "Consulting coach for logical next step..."
        self.render()

        def on_hint_ready(r, c, val, explanation):
            def apply_ui():
                self.ai_busy = False
                self.save_snapshot()
                self.selected = (r, c)
                self.board[r][c] = val
                self.notes[r][c].clear()
                self.clear_peer_notes(r, c, val)
                self.status_message = explanation
                self.check_victory()
                self.render()

            self.root.after(0, apply_ui)

        self.coach.request_hint(self.board, hint, on_hint_ready)

    def solve_all(self):
        if self.game_won:
            return
        self.save_snapshot()
        self.board = copy.deepcopy(self.solution)
        for r in range(9):
            for c in range(9):
                self.notes[r][c].clear()
        self.game_won = True
        self.elapsed_paused = int(time.time() - self.start_time)
        self.status_message = "Board auto-completed via backtracking solver."
        self.render()

    # ------------------------------------------------------------------------
    # INPUT HANDLERS
    # ------------------------------------------------------------------------
    def on_click(self, event):
        x, y = event.x, event.y
        # Check board click
        if (
            self.BOARD_X <= x < self.BOARD_X + self.BOARD_PX
            and self.BOARD_Y <= y < self.BOARD_Y + self.BOARD_PX
        ):
            c = (x - self.BOARD_X) // self.CELL_SIZE
            r = (y - self.BOARD_Y) // self.CELL_SIZE
            self.selected = (int(r), int(c))
            self.render()
            return

        # Check custom buttons
        for btn in self.buttons:
            x1, y1, x2, y2, btn_id, action = btn
            if x1 <= x <= x2 and y1 <= y <= y2:
                action()
                return

    def on_motion(self, event):
        x, y = event.x, event.y
        hovered = None
        for btn in self.buttons:
            x1, y1, x2, y2, btn_id, _ = btn
            if x1 <= x <= x2 and y1 <= y <= y2:
                hovered = btn_id
                break
        if hovered != self.hovered_btn:
            self.hovered_btn = hovered
            self.render()

    def on_key(self, event):
        key = event.keysym
        r, c = self.selected

        if key in ("Up", "w", "W"):
            self.selected = ((r - 1) % 9, c)
            self.render()
        elif key in ("Down", "s", "S"):
            self.selected = ((r + 1) % 9, c)
            self.render()
        elif key in ("Left", "a", "A"):
            self.selected = (r, (c - 1) % 9)
            self.render()
        elif key in ("Right", "d", "D"):
            self.selected = (r, (c + 1) % 9)
            self.render()
        elif key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self.set_number(int(key))
        elif key in ("BackSpace", "Delete", "0"):
            self.set_number(0)
        elif key in ("n", "N", "space"):
            self.notes_mode = not self.notes_mode
            state = "ON" if self.notes_mode else "OFF"
            self.status_message = f"Pencil Notes Mode: {state}"
            self.render()
        elif key in ("u", "U", "z", "Z"):
            self.undo()
        elif key in ("h", "H"):
            self.request_ai_hint()

    # ------------------------------------------------------------------------
    # TIMER & RENDERING (Strictly using #EBE2CC, #DED6C1, #CFC6B1, #B7B09E)
    # ------------------------------------------------------------------------
    @staticmethod
    def format_time(seconds):
        m, s = divmod(max(0, int(seconds)), 60)
        return f"{m:02d}:{s:02d}"

    def tick_timer(self):
        if not self.game_won:
            self.render_header_stats()
        self.root.after(1000, self.tick_timer)

    def render_header_stats(self):
        self.canvas.delete("timer_tag")
        elapsed = (
            self.elapsed_paused
            if self.game_won
            else int(time.time() - self.start_time)
        )
        stats_text = (
            f"DIFFICULTY: {self.difficulty.upper()}    |    "
            f"MISTAKES: {self.mistakes}    |    "
            f"TIME: {self.format_time(elapsed)}"
        )
        self.canvas.create_text(
            self.BOARD_X + self.BOARD_PX,
            64,
            text=stats_text,
            anchor="e",
            fill=C_DARKEST,
            font=("Helvetica", 10, "bold"),
            tags="timer_tag",
        )

    def draw_button(
        self, x1, y1, x2, y2, label, btn_id, action, active=False, primary=False, sublabel=None
    ):
        is_hovered = self.hovered_btn == btn_id
        if active or primary:
            bg = C_DARKEST
            fg = C_LIGHTEST
            border = C_DARKEST
        elif is_hovered:
            bg = C_MEDIUM
            fg = C_DARKEST
            border = C_DARKEST
        else:
            bg = C_LIGHT
            fg = C_DARKEST
            border = C_MEDIUM

        self.canvas.create_rectangle(
            x1, y1, x2, y2, fill=bg, outline=border, width=2
        )
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        if sublabel is not None:
            self.canvas.create_text(
                cx,
                cy - 7,
                text=label,
                fill=fg,
                font=("Helvetica", 15, "bold"),
            )
            self.canvas.create_text(
                cx,
                cy + 12,
                text=sublabel,
                fill=fg,
                font=("Helvetica", 8, "bold"),
            )
        else:
            self.canvas.create_text(
                cx,
                cy,
                text=label,
                fill=fg,
                font=("Helvetica", 10, "bold"),
            )

        self.buttons.append((x1, y1, x2, y2, btn_id, action))

    def render(self):
        self.canvas.delete("all")
        self.buttons.clear()

        # 1. Header Title & Subtitle
        self.canvas.create_text(
            self.BOARD_X,
            34,
            text="SUDOKU",
            anchor="w",
            fill=C_DARKEST,
            font=("Helvetica", 24, "bold"),
        )
        self.canvas.create_text(
            self.BOARD_X,
            64,
            text="MONOLITH PALETTE EDITION",
            anchor="w",
            fill=C_DARKEST,
            font=("Helvetica", 9, "bold"),
        )
        self.render_header_stats()

        # 2. Render 9x9 Sudoku Grid Cells
        sel_r, sel_c = self.selected
        sel_val = self.board[sel_r][sel_c]

        for r in range(9):
            for c in range(9):
                x1 = self.BOARD_X + c * self.CELL_SIZE
                y1 = self.BOARD_Y + r * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE

                val = self.board[r][c]
                is_selected = (r == sel_r and c == sel_c)
                in_peer = (
                    r == sel_r
                    or c == sel_c
                    or (r // 3 == sel_r // 3 and c // 3 == sel_c // 3)
                )
                same_digit = (val != 0 and val == sel_val and not is_selected)
                alt_box = ((r // 3 + c // 3) % 2 == 1)

                # Determine cell surface color from the 4 hex codes
                if is_selected:
                    cell_bg = C_DARKEST
                    text_fg = C_LIGHTEST
                elif same_digit:
                    cell_bg = C_MEDIUM
                    text_fg = C_LIGHTEST
                elif in_peer:
                    cell_bg = C_MEDIUM
                    text_fg = C_DARKEST
                elif alt_box:
                    cell_bg = C_LIGHT
                    text_fg = C_DARKEST
                else:
                    cell_bg = C_LIGHTEST
                    text_fg = C_DARKEST

                self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=cell_bg, outline=C_MEDIUM, width=1
                )

                # Given clue marker (subtle corner frame so locked cells are unmistakable)
                if self.given[r][c] and not is_selected:
                    self.canvas.create_rectangle(
                        x1 + 3,
                        y1 + 3,
                        x2 - 3,
                        y2 - 3,
                        fill="",
                        outline=C_MEDIUM if not in_peer else C_LIGHT,
                        width=1,
                    )

                # Conflict indicator (double inner box using palette contrast)
                if self.has_conflict(r, c):
                    ring_color = C_LIGHTEST if is_selected else C_DARKEST
                    self.canvas.create_rectangle(
                        x1 + 4,
                        y1 + 4,
                        x2 - 4,
                        y2 - 4,
                        fill="",
                        outline=ring_color,
                        width=2,
                    )
                    self.canvas.create_oval(
                        x2 - 12,
                        y1 + 5,
                        x2 - 5,
                        y1 + 12,
                        fill=ring_color,
                        outline=ring_color,
                    )

                # Draw cell value or pencil marks
                if val != 0:
                    font_spec = (
                        ("Helvetica", 20, "bold")
                        if self.given[r][c]
                        else ("Helvetica", 19, "normal")
                    )
                    self.canvas.create_text(
                        (x1 + x2) / 2,
                        (y1 + y2) / 2,
                        text=str(val),
                        fill=text_fg,
                        font=font_spec,
                    )
                    # Underline user-entered numbers for instant distinction from given clues
                    if not self.given[r][c]:
                        self.canvas.create_line(
                            x1 + 17,
                            y2 - 10,
                            x2 - 17,
                            y2 - 10,
                            fill=text_fg,
                            width=2,
                        )
                elif self.notes[r][c]:
                    sub = self.CELL_SIZE / 3
                    for n in sorted(self.notes[r][c]):
                        nr = (n - 1) // 3
                        nc = (n - 1) % 3
                        nx = x1 + nc * sub + sub / 2
                        ny = y1 + nr * sub + sub / 2
                        self.canvas.create_text(
                            nx,
                            ny,
                            text=str(n),
                            fill=text_fg,
                            font=("Helvetica", 8, "bold"),
                        )

        # 3. Draw Thick 3x3 Subgrid Borders & Outer Frame
        for i in range(10):
            weight = 3 if i % 3 == 0 else 1
            color = C_DARKEST if i % 3 == 0 else C_MEDIUM
            if weight == 3:
                pos_x = self.BOARD_X + i * self.CELL_SIZE
                pos_y = self.BOARD_Y + i * self.CELL_SIZE
                self.canvas.create_line(
                    pos_x,
                    self.BOARD_Y,
                    pos_x,
                    self.BOARD_Y + self.BOARD_PX,
                    fill=color,
                    width=weight,
                )
                self.canvas.create_line(
                    self.BOARD_X,
                    pos_y,
                    self.BOARD_X + self.BOARD_PX,
                    pos_y,
                    fill=color,
                    width=weight,
                )

        # 4. Right Control Panel
        panel_x = self.BOARD_X + self.BOARD_PX + 28
        panel_w = self.WIDTH - panel_x - 32

        # Difficulty Selector Row
        self.canvas.create_text(
            panel_x,
            self.BOARD_Y + 8,
            text="DIFFICULTY",
            anchor="w",
            fill=C_DARKEST,
            font=("Helvetica", 9, "bold"),
        )
        diff_w = (panel_w - 16) / 3
        for idx, level in enumerate(("Easy", "Medium", "Hard")):
            bx1 = panel_x + idx * (diff_w + 8)
            by1 = self.BOARD_Y + 22
            self.draw_button(
                bx1,
                by1,
                bx1 + diff_w,
                by1 + 34,
                level.upper(),
                f"diff_{level}",
                lambda lv=level: self.new_game(lv),
                active=(self.difficulty == level),
            )

        # 1-9 Keypad with Remaining Digit Counter
        self.canvas.create_text(
            panel_x,
            self.BOARD_Y + 76,
            text="NUMBER PAD (REMAINING)",
            anchor="w",
            fill=C_DARKEST,
            font=("Helvetica", 9, "bold"),
        )
        counts = {d: 0 for d in range(1, 10)}
        for r in range(9):
            for c in range(9):
                v = self.board[r][c]
                if v in counts:
                    counts[v] += 1

        pad_w = (panel_w - 16) / 3
        pad_h = 54
        pad_y_start = self.BOARD_Y + 90
        for num in range(1, 10):
            idx = num - 1
            pr = idx // 3
            pc = idx % 3
            bx1 = panel_x + pc * (pad_w + 8)
            by1 = pad_y_start + pr * (pad_h + 8)
            remaining = max(0, 9 - counts[num])
            self.draw_button(
                bx1,
                by1,
                bx1 + pad_w,
                by1 + pad_h,
                str(num),
                f"num_{num}",
                lambda n=num: self.set_number(n),
                active=(sel_val == num and sel_val != 0),
                sublabel=f"{remaining} left",
            )

        # Action Controls Grid (Notes, Erase, Undo, AI Coach, Solve, New Game)
        act_y = pad_y_start + 3 * (pad_h + 8) + 12
        half_w = (panel_w - 8) / 2

        notes_label = "NOTES: ON" if self.notes_mode else "NOTES: OFF"
        self.draw_button(
            panel_x,
            act_y,
            panel_x + half_w,
            act_y + 40,
            notes_label,
            "btn_notes",
            self.toggle_notes,
            active=self.notes_mode,
        )
        self.draw_button(
            panel_x + half_w + 8,
            act_y,
            panel_x + panel_w,
            act_y + 40,
            "ERASE CELL",
            "btn_erase",
            lambda: self.set_number(0),
        )

        act_y2 = act_y + 48
        self.draw_button(
            panel_x,
            act_y2,
            panel_x + half_w,
            act_y2 + 40,
            "UNDO (U)",
            "btn_undo",
            self.undo,
        )
        self.draw_button(
            panel_x + half_w + 8,
            act_y2,
            panel_x + panel_w,
            act_y2 + 40,
            "AI HINT (H)",
            "btn_hint",
            self.request_ai_hint,
        )

        act_y3 = act_y2 + 48
        self.draw_button(
            panel_x,
            act_y3,
            panel_x + half_w,
            act_y3 + 42,
            "AUTO SOLVE",
            "btn_solve",
            self.solve_all,
        )
        self.draw_button(
            panel_x + half_w + 8,
            act_y3,
            panel_x + panel_w,
            act_y3 + 42,
            "NEW PUZZLE",
            "btn_new",
            lambda: self.new_game(self.difficulty),
            primary=True,
        )

        # 5. Bottom Status & Gemini Coach Banner
        banner_y1 = self.BOARD_Y + self.BOARD_PX + 16
        banner_y2 = self.HEIGHT - 16
        self.canvas.create_rectangle(
            self.BOARD_X,
            banner_y1,
            self.WIDTH - 32,
            banner_y2,
            fill=C_LIGHT,
            outline=C_DARKEST,
            width=2,
        )
        self.canvas.create_text(
            self.BOARD_X + 14,
            (banner_y1 + banner_y2) / 2,
            text=self.status_message,
            anchor="w",
            fill=C_DARKEST,
            font=("Helvetica", 10, "bold"),
        )

    def toggle_notes(self):
        self.notes_mode = not self.notes_mode
        state = "ON" if self.notes_mode else "OFF"
        self.status_message = f"Pencil Notes Mode: {state}"
        self.render()


if __name__ == "__main__":
    root = tk.Tk()
    app = SudokuApp(root)
    root.mainloop()