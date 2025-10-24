#!/usr/bin/env python

import sys
import re
import glob

# ===================================================================
#  Helper Functions (Copied from checkopt.py)
# ===================================================================


class Colors:
    """Defines ANSI color codes"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    ENDC = "\033[0m"


def ParseGOpt(filename):
    """
    Parses a Gaussian optimization file.
    (Copied from checkopt.py)
    """
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    except Exception as e:
        return []

    Res = []
    StepCounter = 0
    for i in range(len(lines) - 3):
        L1s = lines[i].strip()
        if L1s.startswith("Maximum Force") and ("YES" in L1s or "NO" in L1s):
            try:
                L2s = lines[i + 1].strip()
                L3s = lines[i + 2].strip()
                L4s = lines[i + 3].strip()

                if not (
                    L2s.startswith("RMS")
                    and "Force" in L2s
                    and L3s.startswith("Maximum Displacement")
                    and L4s.startswith("RMS")
                    and "Displacement" in L4s
                ):
                    continue

                StepCounter += 1
                PartsList = [
                    lines[i].split(),
                    lines[i + 1].split(),
                    lines[i + 2].split(),
                    lines[i + 3].split(),
                ]
                DataCells = []
                for p in PartsList:
                    value = p[2]
                    status = p[4]
                    if status == "YES":
                        color_status = f"{Colors.GREEN}({status}){Colors.ENDC}"
                    else:
                        color_status = f"{Colors.RED}({status}) {Colors.ENDC}"
                    DataCells.append(f"{value} {color_status}")
                Res.append(
                    [
                        StepCounter,
                        DataCells[0],
                        DataCells[1],
                        DataCells[2],
                        DataCells[3],
                    ]
                )
            except (IndexError, ValueError):
                continue
    return Res


def GetLen(s):
    """Gets the visible length of a string (strips ANSI codes)"""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def CenterString(Content, InnerWidth):
    """Centers a string within a width (ANSI-aware)"""
    ContentStr = str(Content)
    VisibleLen = GetLen(ContentStr)
    PaddingTot = InnerWidth - VisibleLen
    if PaddingTot < 0:
        PaddingTot = 0
    RPadding = PaddingTot // 2
    LPadding = PaddingTot - RPadding
    LPad = " " * LPadding
    RPad = " " * RPadding
    return f"{LPad}{ContentStr}{RPad}"


# ===================================================================
#  Modified Table Printing Function
# ===================================================================


def PrintTable(AllResults):
    """
    Prints the 6-column summary table.
    """
    if not AllResults:
        print("No data found for any files.")
        return

    V = "│"
    H = "─"
    TL = "┌"
    TR = "┐"
    BL = "└"
    BR = "┘"
    ML = "├"
    MR = "┤"
    TM = "┬"
    BM = "┴"
    MM = "┼"

    headers = [
        "File",
        "Step",
        "Maximum Force",
        "RMS Force",
        "Maximum Displacement",
        "RMS Displacement",
    ]

    # 1. Calculate column widths (ANSI-aware for all columns)
    col_widths = [len(h) for h in headers]
    for row in AllResults:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], GetLen(str(cell)))

    # 2. Draw Top Border
    top_border = TL
    for i, w in enumerate(col_widths):
        top_border += H * (w + 2)  # +2 for padding
        top_border += TR if i == len(col_widths) - 1 else TM
    print(top_border)

    # 3. Draw Header
    header_line = V
    for i, h in enumerate(headers):
        header_line += f" {CenterString(h, col_widths[i])} {V}"
    print(header_line)

    # 4. Draw Middle Border (for header and in-between rows)
    mid_border = ML
    for i, w in enumerate(col_widths):
        mid_border += H * (w + 2)
        mid_border += MR if i == len(col_widths) - 1 else MM
    print(mid_border)

    # 5. Draw Data Rows (*** MODIFIED SECTION ***)
    for index, row in enumerate(AllResults):
        data_line = V
        for i, cell in enumerate(row):
            data_line += f" {CenterString(cell, col_widths[i])} {V}"
        print(data_line)

        # Print separator line, *unless* it's the last row
        if index < len(AllResults) - 1:
            print(mid_border)

    # 6. Draw Bottom Border
    bottom_border = BL
    for i, w in enumerate(col_widths):
        bottom_border += H * (w + 2)
        bottom_border += BR if i == len(col_widths) - 1 else BM
    print(bottom_border)


# ===================================================================
#  Main Function (Unchanged)
# ===================================================================


def main():
    files_to_check = glob.glob("*.log") + glob.glob("*.out")

    if not files_to_check:
        print("No .log or .out files found in the current directory.")
        sys.exit(0)

    AllResults = []
    converged_count = 0

    # English status strings
    NA_STR = "N/A"
    NO_DATA_STR = f"{Colors.RED}No opt steps found{Colors.ENDC}"

    for filename in sorted(files_to_check):
        opt_data = ParseGOpt(filename)

        if not opt_data:
            # File has no opt data, color filename RED
            colored_filename = f"{Colors.RED}{filename}{Colors.ENDC}"
            AllResults.append(
                [
                    colored_filename,
                    NA_STR,
                    NO_DATA_STR,
                    NO_DATA_STR,
                    NO_DATA_STR,
                    NO_DATA_STR,
                ]
            )
        else:
            # File has data, check last step
            last_step = opt_data[-1]
            all_converged = all("(YES)" in item for item in last_step[1:])

            if all_converged:
                converged_count += 1
                # Converged, color filename GREEN
                colored_filename = f"{Colors.GREEN}{filename}{Colors.ENDC}"
            else:
                # Not converged, color filename RED
                colored_filename = f"{Colors.RED}{filename}{Colors.ENDC}"

            AllResults.append(
                [
                    colored_filename,
                    last_step[0],  # Step
                    last_step[1],  # Max Force
                    last_step[2],  # RMS Force
                    last_step[3],  # Max Disp
                    last_step[4],  # RMS Disp
                ]
            )

    # Print summary table
    print(f"--- Checking {len(files_to_check)} files: ---")
    PrintTable(AllResults)

    # Print summary
    print(
        f"\nSummary: {Colors.GREEN}{converged_count}{Colors.ENDC} files converged / {len(files_to_check)} total files."
    )


if __name__ == "__main__":
    main()
