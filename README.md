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
