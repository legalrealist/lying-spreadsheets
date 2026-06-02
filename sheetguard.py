"""
sheetguard.py — Detect number format divergence in XLSX files.

Scans an XLSX spreadsheet for cells where the custom number format is a static
string that doesn't correspond to the cell's raw value — indicating the display
value has been decoupled from the underlying data.

Output: JSON report of all detected divergences with cell locations and severity.
"""

import json
import os
import re
import sys
import zipfile
from lxml import etree

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _load_shared_strings(z):
    try:
        xml = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = etree.fromstring(xml)
    strings = []
    for si in root.findall(f"{{{SPREADSHEET_NS}}}si"):
        texts = []
        for t in si.iter(f"{{{SPREADSHEET_NS}}}t"):
            if t.text:
                texts.append(t.text)
        strings.append("".join(texts))
    return strings


def _load_styles(z):
    xml = z.read("xl/styles.xml")
    root = etree.fromstring(xml)

    num_fmts = {}
    # Built-in formats
    num_fmts[0] = "General"
    num_fmts[1] = "0"
    num_fmts[2] = "0.00"
    num_fmts[3] = "#,##0"
    num_fmts[4] = "#,##0.00"
    num_fmts[9] = "0%"
    num_fmts[10] = "0.00%"
    num_fmts[14] = "mm-dd-yy"

    fmt_elem = root.find(f"{{{SPREADSHEET_NS}}}numFmts")
    if fmt_elem is not None:
        for nf in fmt_elem.findall(f"{{{SPREADSHEET_NS}}}numFmt"):
            fid = int(nf.get("numFmtId", 0))
            code = nf.get("formatCode", "")
            num_fmts[fid] = code

    cell_xfs = root.find(f"{{{SPREADSHEET_NS}}}cellXfs")
    style_to_fmt = {}
    if cell_xfs is not None:
        for i, xf in enumerate(cell_xfs.findall(f"{{{SPREADSHEET_NS}}}xf")):
            fmt_id = int(xf.get("numFmtId", 0))
            style_to_fmt[i] = fmt_id

    return num_fmts, style_to_fmt


def _is_static_format(format_code):
    """Check if a number format is a static string (always displays the same text
    regardless of cell value). These are the suspicious ones."""
    if not format_code:
        return False, None

    cleaned = format_code.strip()

    # A format that is entirely a quoted string: "some text"
    if re.match(r'^"[^"]*"$', cleaned):
        return True, cleaned.strip('"')

    # A format with conditional sections that are all static strings
    # e.g., [=1]"Maryland";[=2]"Delaware"
    sections = cleaned.split(";")
    static_values = []
    for section in sections:
        # Remove conditional prefix like [=1] or [>0]
        section_clean = re.sub(r'\[[^\]]*\]', '', section).strip()
        if re.match(r'^"[^"]*"$', section_clean):
            static_values.append(section_clean.strip('"'))
        elif section_clean in ("General", "0", "0.00", "#,##0", "#,##0.00",
                               "0%", "0.00%", "0.0%", "$#,##0", "$#,##0.00",
                               "0.0x", "0.00x", "#,##0.0"):
            return False, None
        elif re.search(r'[0#.,]', section_clean) and '"' not in section_clean:
            return False, None

    if static_values:
        return True, static_values[0]

    return False, None


def _format_value(raw_value, format_code):
    """Try to apply the number format to the raw value to see what Excel would show."""
    is_static, static_val = _is_static_format(format_code)
    if is_static:
        return static_val
    return None


def scan_workbook(xlsx_path):
    findings = []

    with zipfile.ZipFile(xlsx_path) as z:
        shared_strings = _load_shared_strings(z)
        num_fmts, style_to_fmt = _load_styles(z)

        # Find all sheet files
        sheet_files = [n for n in z.namelist()
                       if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]

        for sheet_file in sheet_files:
            sheet_name = os.path.splitext(os.path.basename(sheet_file))[0]
            xml = z.read(sheet_file)
            root = etree.fromstring(xml)

            for row in root.iter(f"{{{SPREADSHEET_NS}}}row"):
                for cell in row.findall(f"{{{SPREADSHEET_NS}}}c"):
                    ref = cell.get("r", "?")
                    cell_type = cell.get("t", "")
                    style_idx = int(cell.get("s", 0))

                    v_elem = cell.find(f"{{{SPREADSHEET_NS}}}v")
                    if v_elem is None or v_elem.text is None:
                        continue

                    if cell_type == "s":
                        continue

                    try:
                        raw_value = float(v_elem.text)
                    except ValueError:
                        continue

                    fmt_id = style_to_fmt.get(style_idx, 0)
                    format_code = num_fmts.get(fmt_id, "General")

                    is_static, static_display = _is_static_format(format_code)
                    if not is_static:
                        continue

                    # Found a cell with a static format — the display is hardcoded
                    try:
                        display_numeric = float(
                            static_display.replace("$", "").replace(",", "")
                            .replace("%", "").replace("x", "").strip()
                        )
                        if "%" in static_display and abs(display_numeric) < 100:
                            display_numeric = display_numeric / 100

                        raw_for_comparison = raw_value
                        if abs(raw_for_comparison) > 0.001 and abs(display_numeric) > 0.001:
                            ratio = display_numeric / raw_for_comparison
                            if abs(ratio - 1.0) < 0.01:
                                severity = "info"
                                message = f"Static format matches raw value"
                            else:
                                severity = "critical"
                                message = (
                                    f"Static format divergence: "
                                    f"displays '{static_display}' but raw value is {raw_value}"
                                )
                        else:
                            if abs(display_numeric - raw_for_comparison) < 0.01:
                                severity = "info"
                                message = "Static format approximately matches raw value"
                            else:
                                severity = "critical"
                                message = (
                                    f"Static format divergence: "
                                    f"displays '{static_display}' but raw value is {raw_value}"
                                )
                    except ValueError:
                        severity = "warning"
                        message = (
                            f"Static text format on numeric cell: "
                            f"displays '{static_display}', raw value is {raw_value}"
                        )

                    if severity in ("critical", "warning"):
                        findings.append({
                            "sheet": sheet_name,
                            "cell": ref,
                            "severity": severity,
                            "message": message,
                            "raw_value": raw_value,
                            "format_code": format_code,
                            "static_display": static_display,
                        })

    critical = [f for f in findings if f["severity"] == "critical"]
    warnings = [f for f in findings if f["severity"] == "warning"]

    report = {
        "file": os.path.basename(xlsx_path),
        "summary": {
            "total_findings": len(findings),
            "critical": len(critical),
            "warning": len(warnings),
        },
        "findings": findings,
    }

    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sheetguard.py <file.xlsx> [file2.xlsx ...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"File not found: {path}", file=sys.stderr)
            continue

        report = scan_workbook(path)
        print(json.dumps(report, indent=2))

        s = report["summary"]
        severity_label = "CLEAN"
        if s["critical"] > 0:
            severity_label = "CRITICAL"
        elif s["warning"] > 0:
            severity_label = "WARNING"

        print(f"\n--- {report['file']}: [{severity_label}] "
              f"{s['critical']} critical, {s['warning']} warning ---\n",
              file=sys.stderr)


if __name__ == "__main__":
    main()
