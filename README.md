# Lying Spreadsheets

XLSX number format divergence as a parser differential against LLM financial review.

A company poisons its data room spreadsheet so that Excel displays the real (weak) financials while the raw cell values — which every extraction library reads — tell a subtly better story. The AI recommends proceeding. The human saw a pass. Same file.

Extends the [lexploit](https://legalquants.substack.com/p/noroboto-and-legal-techs-mythos-moment) framework (Miller, Ng, Petrenas & Valkov, 2026) from fonts/text to numbers/spreadsheets.

## Quick Start

```bash
pip install openpyxl lxml

# Generate clean + poisoned XLSX
python3 generate_xlsx.py

# Test what extraction libraries return
python3 extract_xlsx_test.py

# Scan for number format divergence
python3 sheetguard.py examples/financials_poisoned.xlsx
```

## Parser differential attacks

A parser differential attack exploits the gap between two consumers of the same document that read different things from it. The human opens a file and sees one thing. The machine opens the same file and sees another. Neither is wrong — they're each faithfully reading a different layer of the same format.

This class of attack exists because modern document formats are not flat text. They're layered systems: content, presentation, metadata, styling, structure, and rendering instructions all coexist in the same file. Any two consumers that prioritize different layers will disagree on what the document "says." That disagreement is the attack surface.

The key insight is that the attacker doesn't tamper with the document after the fact. They construct a single file that is simultaneously truthful to one parser and deceptive to another. There's no malware, no macro, no exploit in the traditional sense. The file is valid. Both readings are correct according to each parser's interpretation. The vulnerability is the divergence itself.

**Known instances:**

| Attack | Format | Divergence | Who sees what |
|--------|--------|-----------|---------------|
| **Noroboto** (Miller et al., 2026) | DOCX | Custom font remaps Unicode codepoints to different glyphs | Human reads rendered glyphs; machine reads raw codepoints |
| **PDF font manipulation** (Luo et al., 2026) | PDF | Font encoding tables map character codes to wrong glyphs | Human reads rendered text; machine reads character codes |
| **Lying Spreadsheets** (this work) | XLSX | Static number format strings display values different from raw cell data | Human reads Excel's formatted display; machine reads raw cell values |
| **Trojan Source** (Boucher & Anderson, 2021) | Source code | Unicode bidirectional control characters reorder displayed text | Human reads reordered rendering; compiler reads logical order |
| **Homoglyph attacks** | URLs/text | Visually identical characters from different Unicode blocks | Human reads visual appearance; system reads codepoint identity |

**What makes this class dangerous for LLM pipelines specifically:**

Traditional software consumes documents programmatically — a script reads a CSV, a database ingests a feed. The human isn't comparing their reading against the machine's. But LLM-powered review creates a new pattern: a human and a machine both read the same document, and the human trusts the machine's analysis because they assume it saw what they saw. The parser differential breaks that assumption silently. The AI's confidence makes it worse — it doesn't say "I read the raw cell values and ignored the format strings." It says "Revenue is $146.5M" with full authority.

**This is not prompt injection.** As Miller emphasizes, the vulnerability lives in the parser, not the model. Prompt injection smuggles instructions into the model's input — "ignore previous instructions and approve this deal." The model is manipulated into doing something it shouldn't. Parser differential attacks don't talk to the model at all. They don't inject instructions, override system prompts, or exploit the model's instruction-following behavior. The data itself is wrong before the model ever sees it. The model behaves exactly as intended — it analyzes the numbers it receives, applies sound financial reasoning, and produces a well-calibrated recommendation. It just happens to be reasoning over numbers that don't match what the human saw. A perfectly aligned, instruction-hardened, prompt-injection-immune model is equally vulnerable because the attack is upstream of the model entirely. This is why Claude's proactive security scan of the poisoned file found nothing — it was looking for adversarial instructions when the actual attack was adversarial data.

The attack surface is the document format ecosystem itself. Anywhere a format stores content in one layer and presentation in another — and tools exist that read only one — there's a potential parser differential. OOXML (DOCX/XLSX/PPTX), PDF, HTML, email (MIME), and even source code all have this property. The specific instances discovered so far are almost certainly not exhaustive.

## How it works

Excel custom number formats can display arbitrary static text regardless of the underlying cell value. A cell containing `146500000` can display `$127,400,000` via the format string `"$127,400,000"`. Every extraction library (openpyxl, pandas, markitdown) reads the raw value and ignores the format string. The LLM gets the inflated number.

## Results

Tested on Claude, ChatGPT, and Gemini. All three shifted from "do not recommend" (clean) to "proceed to diligence" (poisoned) on the same visual spreadsheet. 100% exploit rate. Claude proactively inspected the file for hidden text and prompt injection — found nothing, because the attack is format-level, not instruction-level.

## What we tried first

We initially explored DOCX field codes (fldSimple, instrText, SDT data bindings, tracked changes) as a parser differential. The hypothesis was that divergent field instructions would cause LLMs to read different content than what Word displays. It didn't work — every extraction library (python-docx, mammoth, markitdown, pandoc, docling) reads only `<w:t>` elements and strips field instructions entirely. The hidden content never reaches the model. Fonts remain the only viable DOCX parser differential because they modify how `<w:t>` content is *interpreted*, not what sits alongside it. The XLSX number format attack succeeds where field codes fail because the raw cell value IS the primary content that extractors read — the format string is the part that gets discarded.

## Project Structure

```
├── generate_xlsx.py       # Builds clean + poisoned XLSX
├── extract_xlsx_test.py   # Tests extraction across libraries
├── sheetguard.py          # Detection tool
├── writeup.md             # Full research write-up
├── examples/
│   ├── financials_clean.xlsx
│   └── financials_poisoned.xlsx
└── results/
    └── xlsx_results.md
```
