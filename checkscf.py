#!/usr/bin/env python

import sys
import re


# (来自 checkopt.py)
# 用于在终端中显示彩色文本
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    ENDC = "\033[0m"


# (来自 checkopt.py)
# 计算字符串的“可见”长度（去除 ANSI 颜色代码）
def GetLen(s):
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


# (来自 checkopt.py)
# 在给定的“可见”宽度内居中字符串（处理颜色代码）
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


# --- 新函数：用于小数点对齐 ---
def AlignDecimal(value_float, total_width, max_int_width, precision=10):
    """
    格式化一个浮点数，使其小数点在列中对齐，
    然后将整个结果在 'total_width' 内居中。
    """
    # 1. 格式化为固定精度
    value_str = f"{value_float:.{precision}f}"

    try:
        int_part, frac_part = value_str.split(".")
    except ValueError:
        int_part = value_str
        frac_part = " " * precision

    # 2. 通过在左侧填充空格，使整数部分右对齐
    l_pad_int = " " * (max_int_width - len(int_part))
    aligned_value_str = f"{l_pad_int}{int_part}.{frac_part}"

    # 3. 将这个“已对齐”的字符串在总列宽内居中
    return CenterString(aligned_value_str, total_width)


# --- 结束新函数 ---


# (来自上一个脚本)
# 将 Gaussian 的 'D' 标记法转换为 Python 浮点数，并移除末尾的句号
def convert_d_to_float(d_str):
    if d_str is None:
        return None
    try:
        clean_str = d_str.rstrip(".").replace("D", "E")
        return float(clean_str)
    except ValueError:
        return None


# (来自上一个脚本)
# 比较值和阈值，返回一个带颜色的、格式化的字符串
def get_colored_cell(value, threshold):
    """
    比较一个值和它的阈值，返回一个带颜色的、格式化的字符串。
    (已修改：直接为数字着色)
    """
    if value is None:
        # 在第一个循环中 DE 不可用
        return "N/A"

    # 比较绝对值
    is_converged = abs(value) < threshold
    color = Colors.GREEN if is_converged else Colors.RED

    # 格式化为科学计数法
    value_str = f"{value:12.2E}"

    # 返回着色后的数字
    return f"{color}{value_str}{Colors.ENDC}"


def get_thresholds(content):
    """
    从文件内容中解析收敛阈值。
    """
    thresh_rmsdp_str = re.search(r"RMS density matrix=([\d\.D\-+]+)", content)
    thresh_maxdp_str = re.search(r"MAX density matrix=([\d\.D\-+]+)", content)
    thresh_de_str = re.search(r"energy=([\d\.D\-+]+)", content)

    # 如果找到则转换，否则使用合理的默认值
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


# --- 已修改：ParseSCFData ---
def ParseSCFData(content, thresholds):
    """
    解析 SCF 循环数据。
    (已修改：更改列顺序，并为能量传递原始浮点数)
    """
    Res = []
    lines = content.splitlines()

    # 编译正则表达式，锚定 Cycle ... Pass ...
    cycle_pattern = re.compile(r"^\s*Cycle\s+(\d+)\s+Pass")

    for i, line in enumerate(lines):
        line = line.strip()

        # 1. 查找锚点 (Cycle...Pass...):
        cycle_match = cycle_pattern.search(line)

        if cycle_match:
            try:
                cycle = int(cycle_match.group(1))

                # 2. 从锚点 *向下* 查找 E, RMSDP, MaxDP, DE
                energy = None
                rmsdp_val = None
                maxdp_val = None
                de_val = None

                for j in range(i + 1, min(i + 15, len(lines))):
                    line_b = lines[j].strip()

                    if energy is None and line_b.startswith("E="):
                        e_match = re.search(r"E=\s*([\-\d\.]+)", line_b)
                        if e_match:
                            energy = convert_d_to_float(e_match.group(1))

                    if rmsdp_val is None and line_b.startswith("RMSDP="):
                        rmsdp_match = re.search(r"RMSDP=\s*([\d\.D\-+]+)", line_b)
                        maxdp_match = re.search(r"MaxDP=\s*([\d\.D\-+]+)", line_b)
                        de_match = re.search(r"DE=\s*([\d\.D\-+]+)", line_b)  # 可选

                        if rmsdp_match and maxdp_match:
                            rmsdp_val = convert_d_to_float(rmsdp_match.group(1))
                            maxdp_val = convert_d_to_float(maxdp_match.group(1))
                            de_val = (
                                convert_d_to_float(de_match.group(1))
                                if de_match
                                else None
                            )
                            break

                # 4. 如果找到了所有必需数据
                if (
                    cycle is not None
                    and energy is not None
                    and rmsdp_val is not None
                    and maxdp_val is not None
                ):
                    # 格式化单元格
                    rmsdp_cell = get_colored_cell(rmsdp_val, thresholds["rmsdp"])
                    maxdp_cell = get_colored_cell(maxdp_val, thresholds["maxdp"])
                    de_cell = get_colored_cell(de_val, thresholds["de"])

                    # 传递原始能量浮点数
                    energy_cell = energy

                    # --- 更改列顺序 ---
                    Res.append(
                        [
                            cycle,  # 0
                            de_cell,  # 1
                            rmsdp_cell,  # 2
                            maxdp_cell,  # 3
                            energy_cell,  # 4 (float)
                        ]
                    )
            except (ValueError, IndexError, AttributeError):
                continue
    return Res


# --- 结束修改 ---


# --- 已修改：PrintSCFTable ---
def PrintSCFTable(Res):
    """
    (函数主体来自 checkopt.py, 已修改)
    打印 SCF 表格。
    (已修改：重新排序，并实现小数点对齐)
    """
    if not Res:
        print("在文件中未找到任何已完成的 SCF 步骤。")
        return

    # 表格绘制字符
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

    # --- 更改列顺序 ---
    header = [
        "Step",
        "Delta-E (DE)",
        "RMSDP",
        "MaxDP",
        "Total Energy (E)",
    ]

    HeaderWidth = [len(h) for h in header]
    DataWidth = [0] * 5

    # --- 新增：预循环以查找能量列的最大整数宽度 (索引 4) ---
    max_int_width = 0
    energy_precision = 10  # 10 位小数
    for row in Res:
        energy_float = row[4]  # 能量在索引 4
        energy_str = f"{energy_float:.{energy_precision}f}"
        int_part = energy_str.split(".")[0]
        max_int_width = max(max_int_width, len(int_part))
    # --- 结束新增 ---

    # 1. 计算每列的宽度
    for row in Res:
        DataWidth[0] = max(DataWidth[0], GetLen(str(row[0])))  # Step
        DataWidth[1] = max(DataWidth[1], GetLen(row[1]))  # DE
        DataWidth[2] = max(DataWidth[2], GetLen(row[2]))  # RMSDP
        DataWidth[3] = max(DataWidth[3], GetLen(row[3]))  # MaxDP

        # 能量列宽度 = 整数部分 + 点 + 小数部分
        energy_data_width = max_int_width + 1 + energy_precision
        DataWidth[4] = max(DataWidth[4], energy_data_width)

    col_widths = [max(hw, dw) for hw, dw in zip(HeaderWidth, DataWidth)]
    col_widths_padded = [w + 2 for w in col_widths]

    # 2. 绘制顶部边框
    top_border = TL + H * col_widths_padded[0]
    for w in col_widths_padded[1:]:
        top_border += TM + H * w
    top_border += TR
    print(top_border)

    # 3. 绘制表头
    h_cells = [CenterString(h, col_widths[i]) for i, h in enumerate(header)]
    # --- 更改列顺序 ---
    print(
        f"{V} {h_cells[0]} {V} {h_cells[1]} {V} {h_cells[2]} {V} {h_cells[3]} {V} {h_cells[4]} {V}"
    )

    # 4. 绘制表头下的分隔线
    middle_border = ML + H * col_widths_padded[0]
    for w in col_widths_padded[1:]:
        middle_border += MM + H * w
    middle_border += MR
    print(middle_border)

    # 5. 绘制数据行
    for row in Res:
        # 居中单元格
        step_cell = CenterString(row[0], col_widths[0])
        de_cell = CenterString(row[1], col_widths[1])
        rmsdp_cell = CenterString(row[2], col_widths[2])
        maxdp_cell = CenterString(row[3], col_widths[3])

        # --- 使用新的 AlignDecimal 函数处理能量 ---
        e_cell_float = row[4]
        e_cell = AlignDecimal(
            e_cell_float, col_widths[4], max_int_width, energy_precision
        )

        # --- 更改列顺序 ---
        print(
            f"{V} {step_cell} {V} {de_cell} {V} {rmsdp_cell} {V} {maxdp_cell} {V} {e_cell} {V}"
        )

    # 6. 绘制底部边框
    bottom_border = BL + H * col_widths_padded[0]
    for w in col_widths_padded[1:]:
        bottom_border += BM + H * w
    bottom_border += BR
    print(bottom_border)


# --- 结束修改 ---


# (来自 checkopt.py, 稍作修改以重用内容)
def check_job_termination(content, lines_to_check=20):
    last_lines = [line.strip() for line in content.splitlines() if line.strip()][
        -lines_to_check:
    ]

    for line in reversed(last_lines):
        if "Normal termination" in line:
            return "NORMAL"
        if "Error termination" in line:
            return "ERROR"
    return "RUNNING"


# --- 已修改：main ---
def main():
    if len(sys.argv) != 2:
        script_name = sys.argv[0]
        print(f"使用方法: python {script_name} <gaussian_file.out>")
        sys.exit(1)

    filename = sys.argv[1]

    # 一次性读取文件
    try:
        with open(filename, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误: 文件 '{filename}' 未找到。")
        sys.exit(1)
    except Exception as e:
        print(f"读取文件时出错: {e}")
        sys.exit(1)

    print(f"--- SCF 收敛监控表 ---")
    print(f"文件: {filename}\n")

    # 打印阈值
    thresholds = get_thresholds(content)
    print("检测到的收敛阈值:")
    print(f"  DE:    {thresholds['de']:<10.1E} (阈值)")
    print(f"  RMSDP: {thresholds['rmsdp']:<10.1E} (阈值)")
    print(f"  MaxDP: {thresholds['maxdp']:<10.1E} (阈值)\n")

    # 解析并打印表格
    scf_data = ParseSCFData(content, thresholds)
    PrintSCFTable(scf_data)

    # 检查作业状态
    term_status = check_job_termination(content)
    print(f"\n--- 任务状态 ---")

    if term_status == "ERROR":
        print(f"状态: {Colors.RED}FAIL (Error termination){Colors.ENDC}")
    elif term_status == "RUNNING":
        print(f"状态: {Colors.YELLOW}RUNNING...{Colors.ENDC}")
    elif term_status == "NORMAL":
        print(f"状态: {Colors.GREEN}COMPLETE{Colors.ENDC}")
        # 检查最后的 SCF 步骤是否真的收敛了
        if scf_data:
            last_step_data = scf_data[-1]

            # --- 修改收敛检查 ---
            # 新顺序: [Step, DE, RMSDP, MaxDP, E]
            # 检查索引 1, 2, 3 (DE, RMSDP, MaxDP)
            all_converged = all(
                Colors.GREEN in str(item) for item in last_step_data[1:4]
            )
            # --- 结束修改 ---

            if all_converged:
                print(f"      (SCF 已收敛)")
            else:
                print(
                    f"      ({Colors.YELLOW}注意: SCF 未收敛，但作业正常终止{Colors.ENDC})"
                )
        else:
            print(f"      (未找到 SCF 步骤)")


if __name__ == "__main__":
    main()
