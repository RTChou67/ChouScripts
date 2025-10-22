#!/usr/bin/env python

import sys
import re


class Colors:
    """定义ANSI颜色代码"""

    GREEN = "\033[92m"  # 绿色
    RED = "\033[91m"  # 红色
    ENDC = "\033[0m"  # 重置颜色


def ParseGOpt(filename):
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"错误: 文件 '{filename}' 未找到。")
        return []
    except Exception as e:
        print(f"读取文件时出错: {e}")
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
                    lines[i].split(),  # Max Force
                    lines[i + 1].split(),  # RMS Force
                    lines[i + 2].split(),  # Max Disp
                    lines[i + 3].split(),  # RMS Disp
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
                        DataCells[0],  # Max Force
                        DataCells[1],  # RMS Force
                        DataCells[2],  # Max Disp
                        DataCells[3],  # RMS Disp
                    ]
                )
            except (IndexError, ValueError):
                continue

    return Res


def GetLen(s):
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def CenterString(Content, InnerWidth):
    ContentStr = str(Content)
    VisibleLen = GetLen(ContentStr)

    PaddingTot = InnerWidth - VisibleLen

    # 确保填充不为负
    if PaddingTot < 0:
        PaddingTot = 0

    RPadding = PaddingTot // 2
    LPadding = PaddingTot - RPadding

    # 构建填充字符串
    LPad = " " * LPadding
    RPad = " " * RPadding

    return f"{LPad}{ContentStr}{RPad}"


def PrintTable(Res):
    if not Res:
        print("在文件中未找到任何已完成的优化步骤。")
        return

    V = "│"  # Vertical
    H = "─"  # Horizontal
    TL = "┌"  # Top-Left
    TR = "┐"  # Top-Right
    BL = "└"  # Bottom-Left
    BR = "┘"  # Bottom-Right
    ML = "├"  # Mid-Left
    MR = "┤"  # Mid-Right
    TM = "┬"  # Top-Mid
    BM = "┴"  # Bottom-Mid
    MM = "┼"  # Mid-Mid (Cross)

    header = [
        "Step",
        "Maximum Force",
        "RMS Force",
        "Maximum Displacement",
        "RMS Displacement",
    ]

    HeaderWidth = [len(h) for h in header]
    DataWidth = [0] * 5

    for row in Res:
        DataWidth[0] = max(DataWidth[0], len(str(row[0])))
        for i in range(1, 5):
            DataWidth[i] = max(DataWidth[i], GetLen(row[i]))

    step_width = max(HeaderWidth[0], DataWidth[0])
    data_width = max(max(HeaderWidth[1:]), max(DataWidth[1:]))

    step_col_width = step_width + 2  # "  Step "
    data_col_width = data_width + 2  # " Data... "

    print(
        f"{TL}{H*step_col_width}{TM}"
        f"{H*data_col_width}{TM}"
        f"{H*data_col_width}{TM}"
        f"{H*data_col_width}{TM}"
        f"{H*data_col_width}{TR}"
    )

    h_step = CenterString(header[0], step_width)
    h_maxf = CenterString(header[1], data_width)
    h_rmsf = CenterString(header[2], data_width)
    h_maxd = CenterString(header[3], data_width)
    h_rmsd = CenterString(header[4], data_width)

    print(f"{V} {h_step} {V} {h_maxf} {V} {h_rmsf} {V} {h_maxd} {V} {h_rmsd} {V}")

    print(
        f"{ML}{H*step_col_width}{MM}"
        f"{H*data_col_width}{MM}"
        f"{H*data_col_width}{MM}"
        f"{H*data_col_width}{MM}"
        f"{H*data_col_width}{MR}"
    )

    for row in Res:
        step_cell_str = CenterString(row[0], step_width)

        data_cell_strs = []
        for i in range(1, 5):
            cell_content = row[i]
            centered_content = CenterString(cell_content, data_width)
            data_cell_strs.append(f" {centered_content} ")

        print(f"{V} {step_cell_str} {V}{V.join(data_cell_strs)}{V}")

    print(
        f"{BL}{H*step_col_width}{BM}"
        f"{H*data_col_width}{BM}"
        f"{H*data_col_width}{BM}"
        f"{H*data_col_width}{BM}"
        f"{H*data_col_width}{BR}"
    )


def main():
    if len(sys.argv) != 2:
        script_name = sys.argv[0]
        print(f"使用方法: python {script_name} <gaussian_file.out>")
        sys.exit(1)

    filename = sys.argv[1]

    print(f"--- 正在监控: {filename} ---")
    opt_data = ParseGOpt(filename)
    PrintTable(opt_data)

    if opt_data:
        last_step_data = opt_data[-1]
        all_converged = all("(YES)" in item for item in last_step_data[1:])

        if all_converged:
            print(f"\n状态: {Colors.GREEN}最后一个记录的步骤已收敛。{Colors.ENDC}")
        else:
            print(f"\n状态: {Colors.RED}最后一个记录的步骤尚未收敛。{Colors.ENDC}")


if __name__ == "__main__":
    main()
