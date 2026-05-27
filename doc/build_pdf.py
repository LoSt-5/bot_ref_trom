"""Сборка PROGRAMMNAYA_DOKUMENTACIYA.pdf из markdown и PNG."""
from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

DOC = Path(__file__).resolve().parent
MD = DOC / "PROGRAMMNAYA_DOKUMENTACIYA.md"
OUT = DOC / "PROGRAMMNAYA_DOKUMENTACIYA.pdf"

FONT_DIR = Path(r"C:\Windows\Fonts")
ARIAL = FONT_DIR / "arial.ttf"
ARIAL_B = FONT_DIR / "arialbd.ttf"
ARIAL_I = FONT_DIR / "ariali.ttf"
CONSOLAS = FONT_DIR / "consola.ttf"

EMOJI = {
    "✌️": "V",
    "👍": "+",
    "🤙": "shaka",
    "🤟": "rock",
    "✅": "[OK]",
    "❌": "[X]",
    "⏩": "[>>]",
    "🛑": "[STOP]",
}


class DocPDF(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_auto_page_break(auto=True, margin=18)
        self.add_font("Arial", "", str(ARIAL))
        self.add_font("Arial", "B", str(ARIAL_B))
        self.add_font("Arial", "I", str(ARIAL_I))
        self.add_font("Consolas", "", str(CONSOLAS))
        self._heading_sizes = {1: 14, 2: 12, 3: 11, 4: 10}

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Arial", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Программная документация bot_ref_trom", align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 10, f"— {self.page_no()} —", align="C")

    def ensure_space(self, h: float = 12):
        if self.get_y() + h > self.h - self.b_margin:
            self.add_page()

    def write_rich(self, text: str, size: int = 10, style: str = ""):
        """Простая разметка: **bold**, `code`, [text](url)."""
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
        self.set_font("Arial", style, size)
        for part in parts:
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                self.set_font("Arial", "B", size)
                self.write(5, part[2:-2])
                self.set_font("Arial", style, size)
            elif part.startswith("`") and part.endswith("`"):
                self.set_font("Consolas", "", size - 1)
                self.write(5, part[1:-1])
                self.set_font("Arial", style, size)
            else:
                self.write(5, part)

    def paragraph(self, text: str, size: int = 10):
        self.ensure_space(10)
        self.set_x(self.l_margin)
        self.set_font("Arial", "", size)
        self.multi_cell(0, 5, self._plain(text))
        self.ln(1)

    def bullet(self, text: str, indent: int = 0):
        self.ensure_space(8)
        x = self.l_margin + indent
        self.set_x(x)
        self.set_font("Arial", "", 10)
        w = self.w - self.r_margin - x
        self.multi_cell(w, 5, "• " + self._plain(text))

    def numbered(self, num: str, text: str):
        self.ensure_space(8)
        self.set_x(self.l_margin)
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 5, f"{num}. {self._plain(text)}")

    def heading(self, level: int, text: str):
        size = self._heading_sizes.get(level, 10)
        self.ln(3 if level > 1 else 6)
        self.ensure_space(size + 4)
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", size)
        self.multi_cell(0, size * 0.45, self._plain(text))
        self.ln(2)

    def hr(self):
        self.ln(2)
        y = self.get_y()
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(4)

    def code_block(self, lines: list[str]):
        self.ensure_space(8 + len(lines) * 4.5)
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(200, 200, 200)
        x, y = self.l_margin, self.get_y()
        h = max(6, len(lines) * 4.5 + 4)
        self.rect(x, y, self.w - self.l_margin - self.r_margin, h, style="DF")
        self.set_xy(x + 2, y + 2)
        self.set_font("Consolas", "", 8)
        for line in lines:
            self.cell(0, 4.5, line.replace("\t", "    "), ln=True)
        self.set_y(y + h + 2)

    def image_block(self, path: Path, caption: str = ""):
        if not path.exists():
            self.paragraph(f"[Изображение не найдено: {path.name}]")
            return
        self.ensure_space(80)
        max_w = self.w - self.l_margin - self.r_margin
        self.image(str(path), w=min(max_w, 180))
        self.ln(2)
        if caption:
            self.set_font("Arial", "I", 9)
            self.multi_cell(0, 4, caption, align="C")
            self.ln(3)

    def table(self, rows: list[list[str]]):
        if not rows:
            return
        cols = len(rows[0])
        usable = self.w - self.l_margin - self.r_margin
        col_w = usable / cols
        line_h = 5
        self.ensure_space(line_h * min(len(rows), 3) + 4)
        self.set_font("Arial", "", 8)
        for ri, row in enumerate(rows):
            if ri == 1 and all(re.match(r"^[-:\s|]+$", c) for c in row):
                continue
            if self.get_y() + line_h > self.h - self.b_margin:
                self.add_page()
            style = "B" if ri == 0 else ""
            self.set_font("Arial", style, 8)
            x0 = self.l_margin
            y0 = self.get_y()
            max_h = line_h
            cells = []
            for cell in row[:cols]:
                cell = self._plain(cell.strip())
                nb = self.get_string_width(cell) / max(col_w - 2, 1)
                lines = max(1, int(nb) + (1 if nb > int(nb) else 0))
                max_h = max(max_h, lines * line_h)
                cells.append(cell)
            for ci, cell in enumerate(cells):
                x = x0 + ci * col_w
                self.set_xy(x, y0)
                self.multi_cell(col_w, line_h, cell, border=1, align="L")
            self.set_xy(x0, y0 + max_h)

    @staticmethod
    def _plain(text: str) -> str:
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        for emoji, repl in EMOJI.items():
            text = text.replace(emoji, repl)
        return text.strip()


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        rows.append(row)
        i += 1
    return rows, i


def build():
    text = MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    pdf = DocPDF()
    pdf.add_page()

    i = 0
    in_code = False
    code_buf: list[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                pdf.code_block(code_buf)
                code_buf = []
                in_code = False
            else:
                code_buf.append(line)
            i += 1
            continue

        if stripped.startswith("```"):
            in_code = True
            i += 1
            continue

        if stripped == "---":
            pdf.hr()
            i += 1
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            pdf.heading(min(level, 4), title)
            i += 1
            continue

        m_img = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if m_img:
            cap, rel = m_img.group(1), m_img.group(2)
            pdf.image_block(DOC / rel, cap or None)
            i += 1
            continue

        if stripped.startswith("|"):
            rows, i = parse_table(lines, i)
            pdf.table(rows)
            pdf.ln(2)
            continue

        if stripped.startswith("- "):
            pdf.bullet(stripped[2:])
            i += 1
            continue

        m_num = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m_num:
            pdf.numbered(m_num.group(1), m_num.group(2))
            i += 1
            continue

        if stripped.startswith("> "):
            pdf.paragraph("» " + stripped[2:], size=9)
            i += 1
            continue

        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            pdf.paragraph(stripped.strip("*"), size=9)
            i += 1
            continue

        if stripped:
            pdf.paragraph(stripped)
        i += 1

    pdf.output(str(OUT))
    print(f"PDF: {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
