#!/usr/bin/env python

import sys
import re
import glob


# --- 辅助函数：颜色 ---
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    ENDC = "\033[0m"


# --- 辅助函数：格式化 (来自 checkfreq.py) ---
def GetLen(s):
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def CenterString(Content, InnerWidth):
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


def AlignDecimal(value_float, total_width, max_int_width, precision=10):
    """
    格式化一个浮点数，使其小数点在列中对齐，
    然后将整个结果在 'total_width' 内居中。
    """
    value_str = f"{value_float:.{precision}f}"
    try:
        int_part, frac_part = value_str.split(".")
    except ValueError:
        int_part = value_str
        frac_part = " " * precision
    l_pad_int = " " * (max_int_width - len(int_part))
    aligned_value_str = f"{l_pad_int}{int_part}.{frac_part}"
    return CenterString(aligned_value_str, total_width)


def convert_d_to_float(d_str):
    if d_str is None:
        return None
    try:
        clean_str = d_str.rstrip(".").replace("D", "E")
        return float(clean_str)
    except ValueError:
        return None


def get_colored_cell(value, threshold):
    """
    比较值和阈值，返回一个带颜色的数字字符串。
    """
    if value is None:
        return "N/A"
    is_converged = abs(value) < threshold
    color = Colors.GREEN if is_converged else Colors.RED
    value_str = f"{value:12.2E}"
    return f"{color}{value_str}{Colors.ENDC}"


# --- 文件检查函数 (来自 checkoptall.py) ---
def IsG16(filename, lines_to_check=50):
    try:
        with open(filename, "r") as f:
            for _ in range(lines_to_check):
                line = f.readline()
                if not line:
                    break
                if "Gaussian, Inc." in line:
                    return True
                if "Cite this work as:" in line:
                    return True
    except (IOError, UnicodeDecodeError):
        return False
    return False


def check_job_termination(content, lines_to_check=20):
    """
    (来自 checkfreq.py)
    """
    last_lines = [line.strip() for line in content.splitlines() if line.strip()][
        -lines_to_check:
    ]
    for line in reversed(last_lines):
        if "Normal termination" in line:
            return "NORMAL"
        if "Error termination" in line:
            return "ERROR"
    return "RUNNING"


# --- SCF 解析函数 (来自 checkfreq.py) ---
def get_thresholds(content):
    thresh_rmsdp_str = re.search(r"RMS density matrix=([\d\.D\-+]+)", content)
    thresh_maxdp_str = re.search(r"MAX density matrix=([\d\.D\-+]+)", content)
    thresh_de_str = re.search(r"energy=([\d\.D\-+]+)", content)
    thresh_rmsdp = (
        convert_d_to_float(thresh_rmsdp_str.group(1)) if thresh_rmsdp_str else 1.00e-08
    )
    thresh_maxdp = (
        convert_d_to_float(thresh_maxdp_str.group(1)) if thresh_maxdp_str else 1.00e-06
    )
    thresh_de = (
        convert_d_to_float(thresh_de_str.group(1)) if thresh_de_str else 1.00e-06
    )
    return {"rmsdp": thresh_rmsdp, "maxdp": thresh_maxdp, "de": thresh_de}


def ParseSCFData(content, thresholds):
    """
    (来自 checkfreq.py)
    解析 SCF 循环数据，返回 [cycle, de_cell, rmsdp_cell, maxdp_cell, energy_float]
    """
    Res = []
    lines = content.splitlines()
    cycle_pattern = re.compile(r"^\s*Cycle\s+(\d+)\s+Pass")

    for i, line in enumerate(lines):
        line = line.strip()
        cycle_match = cycle_pattern.search(line)

        if cycle_match:
            try:
                cycle = int(cycle_match.group(1))
                energy, rmsdp_val, maxdp_val, de_val = (None,) * 4

                for j in range(i + 1, min(i + 15, len(lines))):
                    line_b = lines[j].strip()
                    if energy is None and line_b.startswith("E="):
                        e_match = re.search(r"E=\s*([\-\d\.]+)", line_b)
                        if e_match:
                            energy = convert_d_to_float(e_match.group(1))

                    if rmsdp_val is None and line_b.startswith("RMSDP="):
                        rmsdp_match = re.search(r"RMSDP=\s*([\d\.D\-+]+)", line_b)
                        maxdp_match = re.search(r"MaxDP=\s*([\d\.D\-+]+)", line_b)
                        de_match = re.search(r"DE=\s*([\d\.D\-+]+)", line_b)
                        if rmsdp_match and maxdp_match:
                            rmsdp_val = convert_d_to_float(rmsdp_match.group(1))
                            maxdp_val = convert_d_to_float(maxdp_match.group(1))
                            de_val = (
                                convert_d_to_float(de_match.group(1))
                                if de_match
                                else None
                            )
                            break

                if cycle and energy and rmsdp_val and maxdp_val:
                    rmsdp_cell = get_colored_cell(rmsdp_val, thresholds["rmsdp"])
                    maxdp_cell = get_colored_cell(maxdp_val, thresholds["maxdp"])
                    de_cell = get_colored_cell(de_val, thresholds["de"])
                    Res.append([cycle, de_cell, rmsdp_cell, maxdp_cell, energy])
            except (ValueError, IndexError, AttributeError):
                continue
    return Res


# --- 汇总表打印函数 (checkoptall.py 和 checkfreq.py 的结合) ---
def PrintSummaryTable(AllResults):
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
        "Cycle",
        "Delta-E (DE)",
        "RMSDP",
        "MaxDP",
        "Total Energy (E)",
        "Status",
    ]

    col_widths = [len(h) for h in headers]
    energy_col_idx = 5  # "Total Energy (E)" 是第 5 列
    energy_precision = 10
    max_int_width = 0

    # 预循环：找到能量列的最大整数宽度
    for row in AllResults:
        energy_float = row[energy_col_idx]
        if isinstance(energy_float, float):
            energy_str = f"{energy_float:.{energy_precision}f}"
            int_part = energy_str.split(".")[0]
            max_int_width = max(max_int_width, len(int_part))

    # 主循环：计算所有列的宽度
    for row in AllResults:
        for i, cell in enumerate(row):
            if i == energy_col_idx and isinstance(cell, float):
                cell_width = max_int_width + 1 + energy_precision
            elif cell is None:
                cell_width = len("N/A")
            else:
                cell_width = GetLen(str(cell))
            col_widths[i] = max(col_widths[i], cell_width)

    # 打印顶部边框
    top_border = TL
    for i, w in enumerate(col_widths):
        top_border += H * (w + 2)
        top_border += TR if i == len(col_widths) - 1 else TM
    print(top_border)

    # 打印表头
    header_line = V
    for i, h in enumerate(headers):
        header_line += f" {CenterString(h, col_widths[i])} {V}"
    print(header_line)

    # 打印表头分隔线
    mid_border = ML
    for i, w in enumerate(col_widths):
        mid_border += H * (w + 2)
        mid_border += MR if i == len(col_widths) - 1 else MM
    print(mid_border)

    # 打印数据行
    for index, row in enumerate(AllResults):
        data_line = V
        for i, cell in enumerate(row):
            if i == energy_col_idx and isinstance(cell, float):
                cell_str = AlignDecimal(
                    cell, col_widths[i], max_int_width, energy_precision
                )
            elif cell is None:
                cell_str = CenterString("N/A", col_widths[i])
            else:
                cell_str = CenterString(cell, col_widths[i])
            data_line += f" {cell_str} {V}"
        print(data_line)

    # 打印底部边框
    bottom_border = BL
    for i, w in enumerate(col_widths):
        bottom_border += H * (w + 2)
        bottom_border += BR if i == len(col_widths) - 1 else BM
    print(bottom_border)


# --- 主函数 (来自 checkoptall.py, 已修改) ---
def main():
    potential_files = glob.glob("*.log") + glob.glob("*.out")
    if not potential_files:
        print("No .log or .out files found in the current directory.")
        sys.exit(0)

    files_to_check = []
    for f in sorted(potential_files):
        if IsG16(f):
            files_to_check.append(f)

    if not files_to_check:
        print("No Gaussian output files (.log, .out) found in the current directory.")
        sys.exit(0)

    AllResults = []
    scf_converged_count = 0

    NA_STR = "N/A"
    NO_DATA_STR = f"{Colors.RED}No SCF steps found{Colors.ENDC}"
    RUNNING_STR = f"{Colors.YELLOW}...{Colors.ENDC}"

    for filename in files_to_check:
        try:
            with open(filename, "r") as f:
                content = f.read()
        except Exception as e:
            AllResults.append(
                [
                    f"{Colors.RED}{filename}{Colors.ENDC}",
                    "File Read Error",
                    "",
                    "",
                    "",
                    None,
                    f"{Colors.RED}FAIL{Colors.ENDC}",
                ]
            )
            continue

        term_status = check_job_termination(content)
        thresholds = get_thresholds(content)
        scf_data = ParseSCFData(content, thresholds)

        step_str = NA_STR
        de_str = NO_DATA_STR
        rmsdp_str = NO_DATA_STR
        maxdp_str = NO_DATA_STR
        energy_val = None  # 使用 None 代表 N/A
        final_status_str = ""
        colored_filename = filename

        if term_status == "ERROR":
            final_status_str = f"{Colors.RED}FAIL{Colors.ENDC}"
            colored_filename = f"{Colors.RED}{filename}{Colors.ENDC}"
            if scf_data:
                last_step = scf_data[-1]
                step_str, de_str, rmsdp_str, maxdp_str, energy_val = last_step

        elif term_status == "RUNNING":
            final_status_str = f"{Colors.YELLOW}RUNNING{Colors.ENDC}"
            colored_filename = f"{Colors.YELLOW}{filename}{Colors.ENDC}"
            if scf_data:
                last_step = scf_data[-1]
                step_str, de_str, rmsdp_str, maxdp_str, energy_val = last_step
            else:
                de_str, rmsdp_str, maxdp_str = (RUNNING_STR,) * 3

        elif term_status == "NORMAL":
            final_status_str = f"{Colors.GREEN}COMPLETE{Colors.ENDC}"
            colored_filename = f"{Colors.GREEN}{filename}{Colors.ENDC}"
            if not scf_data:
                de_str, rmsdp_str, maxdp_str = (NA_STR,) * 3
            else:
                last_step = scf_data[-1]
                step_str, de_str, rmsdp_str, maxdp_str, energy_val = last_step
                # 检查收敛 [cycle, de, rmsdp, maxdp, E]
                all_converged = all(
                    Colors.GREEN in str(item) for item in last_step[1:4]
                )
                if all_converged:
                    scf_converged_count += 1
                else:
                    # 如果作业完成了，但SCF未收敛，标记为黄色
                    final_status_str = (
                        f"{Colors.YELLOW}COMPLETE (No Conv.){Colors.ENDC}"
                    )
                    colored_filename = f"{Colors.YELLOW}{filename}{Colors.ENDC}"

        AllResults.append(
            [
                colored_filename,
                step_str,
                de_str,
                rmsdp_str,
                maxdp_str,
                energy_val,  # 传递 float 或 None
                final_status_str,
            ]
        )

    print(f"--- 正在检查 {len(files_to_check)} 个 Gaussian 文件: ---")
    PrintSummaryTable(AllResults)
    print(
        f"\n摘要: {Colors.GREEN}{scf_converged_count}{Colors.ENDC} 个文件已收敛 (SCF) / {len(files_to_check)} 个总文件。"
    )


if __name__ == "__main__":
    main()
