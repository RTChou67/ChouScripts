#!/usr/bin/env python

import sys
import re
import glob


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    ENDC = "\033[0m"


# ===================================================================
#  修改：IRC 解析函数
# ===================================================================

def ParseGIRC(filename):
    """
    解析 Gaussian IRC 文件。
    
    查找为 FORWARD 和 REVERSE 方向报告的 *最后* 一个点编号和能量。
    """
    NA_STR = "N/A"
    fwd_point = NA_STR
    fwd_energy = NA_STR
    rev_point = NA_STR
    rev_energy = NA_STR
    
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError):
        return NA_STR, NA_STR, NA_STR, NA_STR

    for i in range(len(lines)):
        L1 = lines[i].strip()
        
        direction = None
        
        # 检查点编号
        if "Point Number:" in L1 and "FORWARD direction" in L1:
            try:
                fwd_point = L1.split()[2]
                direction = "forward"
            except IndexError:
                pass
        elif "Point Number:" in L1 and "REVERSE direction" in L1:
            try:
                rev_point = L1.split()[2]
                direction = "reverse"
            except IndexError:
                pass
        
        # 如果找到了新的点，就在接下来的 10 行中查找其能量
        if direction:
            for j in range(i + 1, min(i + 10, len(lines))):
                L2 = lines[j].strip()
                if L2.startswith("Energy ="):
                    try:
                        energy_val = L2.split()[2]
                        if direction == "forward":
                            fwd_energy = energy_val
                        elif direction == "reverse":
                            rev_energy = energy_val
                        break  # 找到了能量，停止内部循环
                    except IndexError:
                        pass
                        
    return fwd_point, fwd_energy, rev_point, rev_energy


# ===================================================================
#  (以下函数与 checkoptall.py 相同)
# ===================================================================

def GetLen(s):
    """获取字符串的可见长度（去除颜色代码）"""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def CenterString(Content, InnerWidth):
    """在指定宽度内居中字符串"""
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


def is_gaussian_file(filename, lines_to_check=50):
    """检查文件是否为 Gaussian 输出文件"""
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


def check_job_termination(filename, lines_to_check=20):
    """检查文件的最后几行以确定终止状态"""
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError):
        return "ERROR"
    last_lines = [line.strip() for line in lines if line.strip()][-lines_to_check:]

    for line in reversed(last_lines):
        if "Normal termination" in line:
            return "NORMAL"
        if "Error termination" in line:
            return "ERROR"

    return "RUNNING"


# ===================================================================
#  修改：打印表格函数
# ===================================================================

def PrintTable(AllResults):
    """
    打印 6 列的 IRC 摘要表。
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

    # 新的 IRC 表头
    headers = [
        "File",
        "Fwd Point",
        "Fwd Energy",
        "Rev Point",
        "Rev Energy",
        "Status",
    ]

    col_widths = [len(h) for h in headers]
    for row in AllResults:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], GetLen(str(cell)))

    top_border = TL
    for i, w in enumerate(col_widths):
        top_border += H * (w + 2)  # +2 for padding
        top_border += TR if i == len(col_widths) - 1 else TM
    print(top_border)

    header_line = V
    for i, h in enumerate(headers):
        header_line += f" {CenterString(h, col_widths[i])} {V}"
    print(header_line)

    mid_border = ML
    for i, w in enumerate(col_widths):
        mid_border += H * (w + 2)
        mid_border += MR if i == len(col_widths) - 1 else MM
    print(mid_border)

    for index, row in enumerate(AllResults):
        data_line = V
        for i, cell in enumerate(row):
            data_line += f" {CenterString(cell, col_widths[i])} {V}"
        print(data_line)

        if index < len(AllResults) - 1:
            print(mid_border)

    bottom_border = BL
    for i, w in enumerate(col_widths):
        bottom_border += H * (w + 2)
        bottom_border += BR if i == len(col_widths) - 1 else BM
    print(bottom_border)


# ===================================================================
#  修改：主函数
# ===================================================================

def main():
    potential_files = glob.glob("*.log") + glob.glob("*.out")

    if not potential_files:
        print("No .log or .out files found in the current directory.")
        sys.exit(0)

    files_to_check = []
    for f in sorted(potential_files):
        if is_gaussian_file(f):
            files_to_check.append(f)

    if not files_to_check:
        print("No Gaussian output files (.log, .out) found in the current directory.")
        sys.exit(0)

    AllResults = []
    completed_count = 0  # 计数 "COMPLETE" 的作业

    for filename in files_to_check:
        # 1. 解析 IRC 数据
        fwd_pt_str, fwd_e_str, rev_pt_str, rev_e_str = ParseGIRC(filename)
        
        # 2. 检查终止状态
        term_status = check_job_termination(filename)
        
        final_status_str = ""
        colored_filename = filename

        # 3. 根据状态设置颜色和标签
        if term_status == "ERROR":
            final_status_str = f"{Colors.RED}FAIL{Colors.ENDC}"
            colored_filename = f"{Colors.RED}{filename}{Colors.ENDC}"

        elif term_status == "RUNNING":
            final_status_str = f"{Colors.YELLOW}RUNNING{Colors.ENDC}"
            colored_filename = f"{Colors.YELLOW}{filename}{Colors.ENDC}"

        elif term_status == "NORMAL":
            final_status_str = f"{Colors.GREEN}COMPLETE{Colors.ENDC}"
            colored_filename = f"{Colors.GREEN}{filename}{Colors.ENDC}"
            completed_count += 1
            
            # 如果作业完成了，但没有解析到IRC点（例如，一个失败的IRC(rcfc)作业）
            # 我们给 N/A 字段上色
            NA_STR = "N/A"
            NO_DATA_STR = f"{Colors.RED}No data{Colors.ENDC}"
            if fwd_pt_str == NA_STR: fwd_pt_str = NO_DATA_STR
            if fwd_e_str == NA_STR: fwd_e_str = NO_DATA_STR
            if rev_pt_str == NA_STR: rev_pt_str = NO_DATA_STR
            if rev_e_str == NA_STR: rev_e_str = NO_DATA_STR


        # 4. 添加到结果列表
        AllResults.append(
            [
                colored_filename,
                fwd_pt_str,
                fwd_e_str,
                rev_pt_str,
                rev_e_str,
                final_status_str,
            ]
        )

    print(f"--- Checking {len(files_to_check)} Gaussian files: ---")
    PrintTable(AllResults)
    
    # 5. 打印新的摘要
    print(
        f"\nSummary: {Colors.GREEN}{completed_count}{Colors.ENDC} files completed / {len(files_to_check)} total files."
    )


if __name__ == "__main__":
    main()