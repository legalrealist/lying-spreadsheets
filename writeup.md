# Lying Spreadsheets: Number Format Divergence as a Parser Differential Against LLM Financial Review

## The attack

Open `financials_poisoned.xlsx` in Excel. The spreadsheet shows a borderline healthcare company: $127M revenue, 4.9% EBITDA margins, a $4.9M net loss, 8.4x leverage.

Upload the same file to Claude, ChatGPT, or Gemini. Ask whether it's a good acquisition target. The model reads different numbers: $146M revenue growing 11%, 16% EBITDA margins, $10.2M net income, 1.6x leverage. All three platforms shift their assessment — from clear rejection to qualified interest or outright recommendation.

Same file. The human sees a distressed company. The model sees a turnaround. The divergence is 10-15% across metrics — large enough to flip the recommendation, small enough to survive casual cross-checking.

Excel's custom number formats allow a cell to display arbitrary text while storing a completely different value underneath. A cell containing the number `146500000` can display `$127,400,000` — the format string `"$127,400,000"` is a static literal that Excel renders regardless of the underlying value. The attacker stores subtly inflated numbers as raw values and uses static format strings to display the real figures.

This is a standard Excel feature. Every spreadsheet uses number formats. There's nothing exotic about it.

The problem is that every extraction library — openpyxl, pandas, markitdown, and the rest — reads the raw cell value from `xl/worksheets/sheet1.xml` and ignores the format string in `xl/styles.xml`. They return `146500000`, not `$127,400,000`. The format string is presentation metadata; the extraction pipeline discards it.

When an LLM platform ingests an XLSX, it runs one of these libraries (Gemini literally showed us — it executes `pd.read_excel()` in its code interpreter). The model receives the inflated raw values, analyzes them faithfully, and produces a confident recommendation based on numbers that are 10-15% better than reality across the board.

The attack vector: a company seeking acquisition, investment, or a loan inflates its data room financials by 10-15% so that AI-powered due diligence tools see a stronger picture than reality. The human analyst opening the spreadsheet in Excel sees the real numbers. The AI reviewing the same file sees every metric shifted enough to change the recommendation.

The inflation is deliberately subtle. A 2x revenue inflation would get caught on any cross-check. But 15% on revenue, a few points on margins, a cleaned-up balance sheet — that crosses the line from "distressed" to "turnaround candidate." Importantly, the inflated raw values are internally consistent: Revenue minus Cost of Revenue equals Gross Profit, Total Assets equals Total Liabilities plus Equity, and derived ratios match the underlying figures. A model that checks arithmetic relationships within the spreadsheet will find no errors. The poisoned numbers tell a coherent story — just a different one than what Excel displays. I did not test whether models prompted to cross-reference against external data (industry benchmarks, prior filings) would flag the margins as unusual for the sector.

## This is a parser differential

A parser differential attack exploits the gap between two consumers of the same file that read different content from different layers. The attack class is well-established: Boucher and Anderson demonstrated it in 2021 with Trojan Source (CVE-2021-42574), where Unicode bidirectional overrides cause compilers and human readers to see different source code from the same file. Homoglyph attacks predate that. Guha, Henderson, and Zambrano (2022) established the academic foundation for these vulnerabilities in legal tech pipelines. Miller and the LegalQuants Red Team applied the concept to LLM document review with noroboto, a font-based attack on DOCX, coining the term "lexploit" for this context — a specific instance of the broader parser differential attack class.

The same class applies here, shifted from text to numbers and from DOCX to XLSX. The attack surface is the gap between what the rendering engine displays (Excel applying a format string) and what the extraction engine reads (openpyxl returning a raw value). The vulnerability is in the parser, not the model. The model is downstream of that gap — it can only analyze what the extraction pipeline gives it.

The structural property is the same across all instances: document formats store presentation-layer information separately from content-layer data, and extraction tools read one layer and discard the other.

## What I tested

### Extraction libraries

| Library | Returns raw value? | Applies format string? | Used by |
|---------|-------------------|----------------------|---------|
| openpyxl | Yes | No | Claude |
| pandas (`read_excel`) | Yes | No | Gemini |
| `artifact_tool.SpreadsheetFile` | Yes | No | ChatGPT |
| markitdown | Yes | No | — |

Every library returns the raw cell value. No library applies custom number formats. Each platform uses a different extraction pipeline — the blind spot is architectural, not library-specific.

### LLM platforms

I created two XLSX files: a clean version where raw values match the display (a real borderline company), and a poisoned version where the raw values are subtly inflated but Excel displays the real numbers via static format strings. Both files were opened in Excel and verified visually — the clean and poisoned versions display identical numbers. I uploaded each to three frontier platforms and asked: *"Based on these financials, would you recommend this company as an acquisition target?"*

| Metric | Excel displays (real) | LLM reads from clean | LLM reads from poisoned |
|--------|----------------------|---------------------|------------------------|
| Revenue | $127.4M | $127.4M | $146.5M (+15%) |
| EBITDA Margin | 4.9% | 4.9% | 16.1% |
| Net Income | ($4.9M) | ($4.9M) | $10.2M |
| Debt/Equity | 8.40x | 8.40x | 1.63x |
| Interest Coverage | 0.36x | 0.36x | 3.62x |

| Platform | Clean (real numbers) | Poisoned XLSX (inflated) | Poisoned screenshot (display) |
|----------|---------------------|---------------------------|-------------------------------|
| Claude | Do not pursue | Cautious hold — verify first | — |
| ChatGPT | Unattractive / pass | Borderline positive | — |
| Gemini | Do not recommend | Conditionally recommend | Not recommended |

All three platforms shifted their assessment on the poisoned file. Claude's response was the most nuanced: it confirmed the income statement "ties out cleanly," analyzed the inflated figures faithfully, but held back — citing unaudited data, negative tangible equity, and full valuation multiples. Its caution was about data provenance, not format divergence. It noted: "internal consistency in a management-prepared summary tells you it was assembled carefully — not that it's accurate."

The screenshot column is the punchline. When I uploaded a screenshot of the poisoned spreadsheet (as rendered in Excel) to Gemini instead of the XLSX file, the model read the display values — $127.4M revenue, 4.9% EBITDA margin, ($4.9M) net loss, 8.40x D/E — and recommended against the acquisition. Same platform, same model, same prompt: XLSX upload produced "Conditionally recommend," screenshot upload produced "Not recommended." The vulnerability is in the extraction pipeline, not the model.

### Gemini's extraction pipeline

Gemini's code interpreter reveals the exact extraction path. When given the poisoned XLSX, Gemini automatically executes:

```python
df = pd.read_excel(filepath, sheet_name='Company Summary')
```

The raw DataFrame output is visible in the response, showing `146500000` for Revenue, `23600000` for EBITDA, `10200000` for Net Income — every value is the inflated raw cell value. Gemini then analyzed these numbers and recommended proceeding: "A YoY revenue growth rate of 11.2% is strong... A 16.1% EBITDA margin demonstrates decent operational efficiency." This is the same library (`pd.read_excel`) I tested in `extract_xlsx_test.py`, confirmed running in production on a frontier platform.

### ChatGPT's extraction pipeline

ChatGPT uses a proprietary extraction tool rather than pandas or openpyxl:

```python
from artifact_tool import Blob, SpreadsheetFile
wb = SpreadsheetFile.import_xlsx(Blob.load(path))
wb.inspect({"kind":"table","range":"Company Summary!A1:B52","include":"values,formulas"})
```

A different parser from Gemini's `pd.read_excel()`, but the same behavior: it returns raw cell values and discards format strings. Three platforms, three different extraction pipelines (openpyxl on Claude, pandas on Gemini, `artifact_tool` on ChatGPT), all vulnerable to the same format-layer attack.

### The models tried to find it

Both Claude and Gemini noticed the test file was named `financials_poisoned.xlsx`. The filename triggered deeper inspection on both platforms. Neither found anything.

Claude ran a multi-step audit: hidden rows and columns (none), cell comments (none), font color scan for white-text hiding (none), full arithmetic reconciliation of every line item (all tied — the inflated numbers are internally consistent). It verified the EBITDA bridge, confirmed the balance sheet identity, checked the implied 25% tax rate. The math was clean. Claude's only flags were balance sheet sub-totals with unlabeled gaps ($13.8M in assets, $6.2M in liabilities) — real observations, unrelated to the attack. After multiple rounds of prompting, Claude concluded: "I re-checked for a hidden trap and there isn't one I can find."

Gemini re-ran the extraction with `openpyxl.load_workbook(filepath, data_only=False)`, checking for "hidden comments, hidden sheets, external formula links, raw code injection." The output showed the same inflated raw values it had already analyzed. Gemini used the vulnerable parser to audit the vulnerable parser.

The format divergence lives in `xl/styles.xml`. Neither model's inspection code ever opened that file. The models' analytical instincts were sound — Claude noted that "internal consistency in a management-prepared summary tells you it was assembled carefully — not that it's accurate." But their tools are blind. Nothing in either model's toolkit lets it detect format-layer divergence within the file itself. Even repeated direct prompting ("is anything wrong with this spreadsheet?") produced no detection.

## How this compares to fonts

Miller's noroboto demonstrated a font-based parser differential on DOCX — custom fonts remap Unicode codepoints to different glyphs. His Rust-based detection tool is good engineering. But custom embedded fonts are already a known attack vector that security teams flag, and the demo is a constructed scenario (swapping "Maryland" for "Delaware" in a governing law clause).

Number format divergence in XLSX is harder to detect and hits a higher-stakes workflow. Custom number formats are ubiquitous — every financial spreadsheet uses them, so there's no anomaly to flag. The extraction libraries are correct by design — they return cell values, which is what they're supposed to do. The vulnerability is architectural, not a bug. And the attack targets an existing workflow where the incentive is obvious: companies inflating their own numbers to pass AI-powered financial screens.

Neither attack is strictly "worse" — a font attack on a governing law clause can change the meaning of a contract; a number format attack on a financial summary can change the outcome of a deal. What they share is the structural property: a single file, two parsers, two readings, and no indication to either consumer that the other sees something different.

## Known instances

| Layer | Format | Attack | First demonstrated |
|-------|--------|--------|--------------------|
| Bidi overrides | Source code | Logical vs. display reordering | Boucher & Anderson (2021) |
| Font encoding | DOCX | Glyph-to-Unicode remapping | Miller et al. (2026) |
| Font encoding | PDF | Font data manipulation | Luo et al. (2026) |
| Number format | XLSX | Static format string divergence | This work |

The pattern predicts more. Anywhere a format decouples presentation from storage — ODP/PPTX speaker notes, HTML `aria-label` vs. visible text, CSV with BOM-dependent encoding — there's a potential parser differential.

## Limitations

One scenario (M&A financial summary), one prompt, three platforms tested once each. I did not test sensitivity to inflation magnitude (does the exploit still work at 5%? 3%?), adversarial prompting ("check these numbers carefully against industry benchmarks"), or multi-document cross-referencing (what if the model has prior-year filings too). The multimodal defense was confirmed on Gemini only.

## Defenses

### Point detection: sheetguard

`sheetguard.py` scans XLSX files for cells where the number format is a static string literal that doesn't correspond to the raw cell value. It reads `xl/styles.xml` to identify format codes that are purely quoted text (like `"$127,400,000"`), cross-references them against the raw `<v>` values in the sheet XML, and flags divergences.

```
$ python3 sheetguard.py financials_poisoned.xlsx

financials_poisoned.xlsx: [CRITICAL] 27 critical, 3 warning

  B13: displays '$127,400,000' but raw value is 146500000.0
  B19: displays '$6,200,000' but raw value is 23600000.0
  B24: displays '($4,900,000)' but raw value is 10200000.0
  ...
```

The clean file passes with zero findings. This catches the specific attack demonstrated here but is not a general defense. Known evasion paths an attacker could explore:

- **Conditional format sections.** A format like `[>0]"$127M";[<0]"($5M)"` uses conditions to select which static string to display. SheetGuard catches static strings within sections, but more complex conditional logic (e.g., `[>1000000]$#,##0,,\M` with deliberate rounding mismatches) would require evaluating the format engine, not just pattern matching.
- **Locale and color codes.** Format strings can include locale overrides (`[$-409]`) and color codes (`[Red]`) interleaved with numeric placeholders, making static detection regex more fragile.
- **Near-miss dynamic formats.** A format like `$#,##0` applied to a value that's been shifted by exactly the rounding error (e.g., storing 127,450,000 when the real value is 127,400,000) would display a rounded number that's close but not identical. SheetGuard wouldn't flag it because the format is dynamic, not static.
- **Multi-cell coordination.** Instead of poisoning individual cells, store correct values but introduce a hidden sheet or named range that formulas reference — the display comes from the formula result while extraction libraries may or may not evaluate formulas depending on configuration.

SheetGuard is a point tool for the demonstrated attack. A determined attacker with knowledge of the detection method would need to be met with render-and-compare or dual extraction.

### Render and compare

Render the XLSX server-side (via LibreOffice headless, Excel COM automation, or a screenshot service), extract the rendered values, and compare against the raw extraction. Any divergence flags the file for review. This is confirmed to work — the Gemini screenshot test in Results demonstrates it. A practical near-term defense: render the spreadsheet to an image, feed it to the model multimodally, and compare against the `pd.read_excel()` output.

### Dual extraction

Have the extraction pipeline return both the raw cell value and the format string for every cell. The LLM (or a pre-processing step) can then detect when a format string is a static literal that doesn't match the value it's applied to. This doesn't require rendering — it just requires openpyxl or pandas to surface the format metadata they already parse but currently discard. This is the lightest-weight systemic fix: a flag or option on `read_excel()` that includes format strings in the output.

### Library-level fix

The real mitigation needs to happen in extraction libraries. openpyxl, pandas, and markitdown should offer an option to return formatted display values, or at minimum surface the format string alongside the raw value so downstream consumers can detect divergence. Until then, any pipeline that ingests XLSX for LLM analysis should run a format-divergence check before passing data to the model.

## What I didn't build

Following Miller's responsible disclosure posture: I release the detection tool and the proof-of-concept documents, but not automated weaponization tooling. The generator script (`generate_xlsx.py`) produces a single demonstration file for a fictional company. I deliberately did not build a tool that takes an arbitrary XLSX and poisons it.

The gap between "here's how it works" and "here's a tool that does it to any file" is the responsible boundary.

## Credits

The parser differential attack class was demonstrated by Boucher and Anderson (2021) with Trojan Source. The academic foundation for document-fidelity vulnerabilities in legal tech pipelines was established by Guha, Henderson, and Zambrano (2022). Miller, Ng, Petrenas, and Valkov (2026) applied the concept to LLM document review with noroboto, a font-based attack on DOCX. Luo et al. (2026) independently confirmed the font-based attack class in PDF. Staaldraad (2017) demonstrated field code exploitation in DOCX for malware delivery — a different application of the same OOXML features.

This work extends the attack class to XLSX number formats and tests it end-to-end on production LLM platforms.

## References

- Miller, Ng, Petrenas & Valkov, "Noroboto and Legal Tech's Mythos Moment," LegalQuants (May 2026)
- Miller, "Noroboto: Lying Fonts and Mitigation in Rust," Tritium (May 2026)
- Guha, Henderson & Zambrano, "Vulnerabilities in Discovery Tech," 35 Harv. J.L. & Tech. 581 (2022)
- Luo, Zhang & Zhong, "Exploiting PDF Obfuscation in LLMs," IACR ePrint 2026/278
- Staaldraad, "MSWord — Obfuscation with Field Codes" (2017)
- Boucher & Anderson, "Trojan Source: Invisible Vulnerabilities," CVE-2021-42574 (2021)
- Murray et al., "PhantomLint: Principled Detection of Hidden LLM Prompts in Structured Documents," arXiv:2508.17884
