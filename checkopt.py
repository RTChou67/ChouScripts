#!/usr/bin/env python

import sys
import re
import glob
import os


# --- 颜色定义 ---
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    ENDC = "\033[0m"


# --- 核心解析功能 ---


def get_visible_len(s):
    """获取去除ANSI颜色代码后的字符串长度"""
    return len(re.sub(r"\033\[[0-9;]*m", "", str(s)))


def center_string(content, inner_width):
    """带颜色字符串的居中对齐"""
    content_str = str(content)
    visible_len = get_visible_len(content_str)
    padding = max(0, inner_width - visible_len)
    r_padding = padding // 2
    l_padding = padding - r_padding
    return " " * l_padding + content_str + " " * r_padding


def detect_file_type(filename, lines_to_check=100):
    """
    检查文件类型
    返回: 'GAUSSIAN', 'CP2K', 'ORCA' or None
    """
    try:
        with open(filename, "r", errors="ignore") as f:
            for _ in range(lines_to_check):
                line = f.readline()
                if not line:
                    break
                if "Gaussian, Inc." in line or "Cite this work as:" in line:
                    return "GAUSSIAN"
                if "* O   R   C   A *" in line or "Program Version" in line:
                    # 简单的二次确认，防止误判
                    return "ORCA"
                if "CP2K|" in line or "PROGRAM STARTED AT" in line:
                    if "CP2K" in line or "CP2K" in f.read(
                        1000
                    ):  # Double check shortly after
                        return "CP2K"
    except Exception:
        return None
    return None


def check_termination_status(filename, file_type):
    """检查任务是正常结束、报错还是正在运行"""
    try:
        # 使用二进制模式 "rb" 打开，以支持 seek 倒序读取
        with open(filename, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            # 读取文件末尾的 20KB 内容 (足够覆盖结尾信息)
            seek_offset = min(file_size, 20000)
            f.seek(-seek_offset, os.SEEK_END)
            # 解码为字符串，忽略解码错误
            content = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return "ERROR"

    # 如果文件内容太少（刚开始运行）
    if not content.strip():
        return "RUNNING"

    if file_type == "GAUSSIAN":
        if "Normal termination" in content:
            return "NORMAL"
        if "Error termination" in content:
            return "ERROR"

    elif file_type == "CP2K":
        if "PROGRAM ENDED AT" in content:
            return "NORMAL"
        if "ABNORMAL TERMINATION" in content or "An error has occurred" in content:
            return "ERROR"

    elif file_type == "ORCA":
        if "ORCA TERMINATED NORMALLY" in content:
            return "NORMAL"
        # ORCA 报错通常不会有特定的统一结尾标志，如果没正常结束且文件不更新，
        # 往往是报错，但在脚本里很难严格区分 Error 和 Running，
        # 这里假设只要没看到 normal termination 且不是明显报错就是 running/error
        if "ORCA finished by error termination" in content:
            return "ERROR"

    return "RUNNING"


def update_last_or_append(rows, row, keep_all):
    if keep_all:
        rows.append(row)
    elif rows:
        rows[0] = row
    else:
        rows.append(row)


def parse_gaussian_block(lines, step):
    parts = [
        lines[0].split(),  # Max Force
        lines[1].split(),  # RMS Force
        lines[2].split(),  # Max Disp
        lines[3].split(),  # RMS Disp
    ]

    data_cells = []
    for p in parts:
        value = p[2]
        status = p[4]
        if status == "YES":
            fmt_value = f"{Colors.GREEN}{value}{Colors.ENDC}"
        else:
            fmt_value = f"{Colors.RED}{value}{Colors.ENDC}"
        data_cells.append(fmt_value)
    return [step] + data_cells


def parse_gaussian_last_step_from_tail(filename, initial_size=262144):
    try:
        with open(filename, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            size = min(initial_size, file_size)
            while size <= file_size:
                f.seek(file_size - size, os.SEEK_SET)
                content = f.read(size).decode("utf-8", errors="ignore")

                candidates = []
                for match in re.finditer(r"^\s*Maximum Force", content, flags=re.M):
                    force_pos = match.start()
                    block = content[force_pos:].splitlines()[:4]
                    if (
                        len(block) == 4
                        and block[0].strip().startswith("Maximum Force")
                        and block[1].strip().startswith("RMS")
                        and "Force" in block[1]
                    ):
                        prior = content[:force_pos]
                        step_matches = list(
                            re.finditer(
                                r"Step number\s+(\d+)\s+out of a maximum of\s+(\d+)",
                                prior,
                            )
                        )
                        if step_matches:
                            step = int(step_matches[-1].group(1))
                            max_steps = int(step_matches[-1].group(2))
                        else:
                            step = content[:force_pos].count("Maximum Force") + 1
                            max_steps = None
                        candidates.append((max_steps, force_pos, parse_gaussian_block(block, step)))

                preferred = [
                    row
                    for max_steps, _, row in candidates
                    if max_steps is None or max_steps > 2
                ]
                if preferred:
                    return [preferred[-1]]
                if candidates and size == file_size:
                    return [candidates[-1][2]]

                if size == file_size:
                    break
                size = min(size * 2, file_size)
    except Exception:
        return []
    return []


def parse_gaussian_steps(filename, keep_all=True):
    """解析 Gaussian 优化步骤"""
    if not keep_all:
        tail_result = parse_gaussian_last_step_from_tail(filename)
        if tail_result:
            return tail_result

    results = []
    try:
        with open(filename, "r", errors="ignore") as f:
            window = []
            step_counter = 0
            for line in f:
                window.append(line)
                if len(window) < 4:
                    continue
                if len(window) > 4:
                    window.pop(0)

                l1 = window[0].strip()
                if not (l1.startswith("Maximum Force") and ("YES" in l1 or "NO" in l1)):
                    continue

                try:
                    l2 = window[1].strip()
                    if not (l2.startswith("RMS") and "Force" in l2):
                        continue

                    step_counter += 1
                    update_last_or_append(
                        results,
                        parse_gaussian_block(window, step_counter),
                        keep_all,
                    )
                except (IndexError, ValueError):
                    continue
    except Exception:
        return []
    return results


def parse_cp2k_steps(filename):
    """解析 CP2K 优化步骤 (GEO_OPT)"""
    results = []
    try:
        with open(filename, "r", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []

    step_pattern = re.compile(r"OPT\|\s+Step number\s+(\d+)")

    def get_val_and_status(block, label_val, label_conv):
        val_match = re.search(
            rf"OPT\|\s+{re.escape(label_val)}\s+([-+]?\d*\.\d+)", block
        )
        conv_match = re.search(rf"OPT\|\s+{re.escape(label_conv)}\s+(YES|NO)", block)

        if val_match and conv_match:
            val = val_match.group(1)
            status = conv_match.group(1)
            try:
                val_float = float(val)
                val_str = f"{val_float:.6f}"
            except:
                val_str = val

            if status == "YES":
                return f"{Colors.GREEN}{val_str}{Colors.ENDC}"
            else:
                return f"{Colors.RED}{val_str}{Colors.ENDC}"
        return f"{Colors.YELLOW}N/A{Colors.ENDC}"

    parts = step_pattern.split(content)
    if len(parts) < 2:
        return []

    for k in range(1, len(parts), 2):
        step_num = parts[k]
        block = parts[k + 1]

        max_grad = get_val_and_status(
            block, "Maximum gradient", "Maximum gradient is converged"
        )
        rms_grad = get_val_and_status(
            block, "RMS gradient", "RMS gradient is converged"
        )
        max_step = get_val_and_status(
            block, "Maximum step size", "Maximum step size is converged"
        )
        rms_step = get_val_and_status(
            block, "RMS step size", "RMS step size is converged"
        )

        if "N/A" in max_grad and "N/A" in max_step:
            continue

        results.append([step_num, max_grad, rms_grad, max_step, rms_step])

    return results


def parse_orca_steps(filename):
    """解析 ORCA 优化步骤"""
    results = []
    try:
        with open(filename, "r", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    step_counter = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # --- 修正开始 ---
        # 匹配类似 "* GEOMETRY OPTIMIZATION CYCLE   1      *" 的行
        if "GEOMETRY OPTIMIZATION CYCLE" in line:
            match = re.search(r"GEOMETRY OPTIMIZATION CYCLE\s+(\d+)", line)
            if match:
                step_counter = int(match.group(1))
        # --- 修正结束 ---

        # 抓取收敛表
        if "Geometry convergence" in line:
            # 向下寻找表格内容
            # 表格结构通常如下：
            # ----------------------|Geometry convergence|-------------------------
            # Item                value                   Tolerance       Converged
            # ---------------------------------------------------------------------
            # RMS gradient        0.0001155240            0.0001000000      NO
            # MAX gradient        0.0003965150            0.0003000000      NO
            # RMS step            0.0002714441            0.0020000000      YES
            # MAX step            0.0007522183            0.0040000000      YES

            # 提取暂存
            extracted_data = {}

            # 向下看最多 20 行寻找数据
            for k in range(1, 20):
                if i + k >= len(lines):
                    break
                sub_line = lines[i + k].strip()

                # 遇到分隔符或结束标志停止
                if "Max(Bonds)" in sub_line or "The step convergence" in sub_line:
                    break

                parts = sub_line.split()
                if len(parts) < 4:
                    continue

                # 提取 Value 和 Converged (YES/NO)
                # 假设格式: Label Value Tolerance Converged
                label_key = None
                if sub_line.startswith("RMS gradient"):
                    label_key = "RMS_G"
                elif sub_line.startswith("MAX gradient"):
                    label_key = "MAX_G"
                elif sub_line.startswith("RMS step"):
                    label_key = "RMS_S"
                elif sub_line.startswith("MAX step"):
                    label_key = "MAX_S"

                if label_key:
                    # parts 类似 ['RMS', 'gradient', '0.0001', '0.0001', 'NO']
                    # ORCA 的分割比较稳定，最后一位是 YES/NO
                    status = parts[-1]
                    # 值通常是倒数第三个 (Tolerance 是倒数第二个)
                    val = parts[-3]

                    if status == "YES":
                        fmt_val = f"{Colors.GREEN}{val}{Colors.ENDC}"
                    else:
                        fmt_val = f"{Colors.RED}{val}{Colors.ENDC}"
                    extracted_data[label_key] = fmt_val

            # 组装数据，确保顺序：Max Grad, RMS Grad, Max Step, RMS Step
            if len(extracted_data) >= 4:
                row = [
                    step_counter,
                    extracted_data.get("MAX_G", "N/A"),
                    extracted_data.get("RMS_G", "N/A"),
                    extracted_data.get("MAX_S", "N/A"),
                    extracted_data.get("RMS_S", "N/A"),
                ]
                results.append(row)

        i += 1

    return results


def parse_opt_steps(filename, file_type, keep_all=True):
    if file_type == "GAUSSIAN":
        return parse_gaussian_steps(filename, keep_all=keep_all)
    elif file_type == "CP2K":
        return parse_cp2k_steps(filename)
    elif file_type == "ORCA":
        return parse_orca_steps(filename)
    return []


# --- 表格绘制功能 ---


def draw_table(headers, rows):
    """通用的表格绘制函数"""
    if not rows:
        return

    # 计算列宽
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], get_visible_len(cell))

    # 边框字符
    V, H = "│", "─"
    TL, TR, BL, BR = "┌", "┐", "└", "┘"
    ML, MR, TM, BM, MM = "├", "┤", "┬", "┴", "┼"

    def make_border(left, mid, right, widths):
        segments = [H * (w + 2) for w in widths]
        return left + mid.join(segments) + right

    # 打印表头
    print(make_border(TL, TM, TR, col_widths))
    header_str = V
    for i, h in enumerate(headers):
        header_str += f" {center_string(h, col_widths[i])} {V}"
    print(header_str)

    # 打印数据
    print(make_border(ML, MM, MR, col_widths))
    for idx, row in enumerate(rows):
        row_str = V
        for i, cell in enumerate(row):
            row_str += f" {center_string(cell, col_widths[i])} {V}"
        print(row_str)

    print(make_border(BL, BM, BR, col_widths))


# --- 两种显示模式 ---


def show_single_file_detail(filename):
    """模式1：显示单个文件的详细优化历史"""
    file_type = detect_file_type(filename)

    if not file_type:
        print(
            f"{Colors.RED}跳过: 无法识别文件类型 (非 Gaussian/CP2K/ORCA){Colors.ENDC}: {filename}"
        )
        return

    print(f"--- 分析文件: {filename} [{Colors.CYAN}{file_type}{Colors.ENDC}] ---")

    opt_data = parse_opt_steps(filename, file_type)
    status = check_termination_status(filename, file_type)

    if opt_data:
        # 统一表头显示
        headers = [
            "Step",
            "Max Grad/Force",
            "RMS Grad/Force",
            "Max Step/Disp",
            "RMS Step/Disp",
        ]
        draw_table(headers, opt_data)
    else:
        print("未找到优化步骤数据。")

    print(f"\n--- 任务状态 ---")
    if status == "ERROR":
        print(f"状态: {Colors.RED}FAIL / ABNORMAL{Colors.ENDC}")
    elif status == "RUNNING":
        print(f"状态: {Colors.YELLOW}RUNNING...{Colors.ENDC}")
    elif status == "NORMAL":
        print(f"状态: {Colors.GREEN}COMPLETE{Colors.ENDC}")
        print("      (任务已正常结束)")


def show_batch_summary(file_list):
    """模式2：显示多个文件的汇总列表"""

    valid_files = []
    for f in sorted(file_list):
        ftype = detect_file_type(f)
        if ftype:
            valid_files.append((f, ftype))

    if not valid_files:
        print("未找到有效的输出文件 (Gaussian/CP2K/ORCA)。")
        return

    print(f"--- 正在检查 {len(valid_files)} 个文件 ---")

    table_rows = []
    complete_count = 0

    headers = [
        "File",
        "Type",
        "Step",
        "Max F/G",  # Force / Gradient
        "RMS F/G",
        "Max D/S",  # Disp / Step
        "RMS D/S",
        "Status",
    ]

    for filename, ftype in valid_files:
        opt_data = parse_opt_steps(filename, ftype, keep_all=False)
        status = check_termination_status(filename, ftype)

        step_str = "N/A"
        vals = [f"{Colors.RED}No Data{Colors.ENDC}"] * 4
        fname_colored = filename
        status_str = ""
        type_str = ftype

        # 设置文件名颜色
        if status == "ERROR":
            status_str = f"{Colors.RED}FAIL{Colors.ENDC}"
            fname_colored = f"{Colors.RED}{filename}{Colors.ENDC}"
        elif status == "RUNNING":
            status_str = f"{Colors.YELLOW}RUN{Colors.ENDC}"
            fname_colored = f"{Colors.YELLOW}{filename}{Colors.ENDC}"
            vals = [f"{Colors.YELLOW}...{Colors.ENDC}"] * 4
        elif status == "NORMAL":
            status_str = f"{Colors.GREEN}DONE{Colors.ENDC}"
            fname_colored = f"{Colors.GREEN}{filename}{Colors.ENDC}"
            vals = ["N/A"] * 4
            complete_count += 1

        # 获取最后一步数据
        if opt_data:
            last = opt_data[-1]
            step_str = str(last[0])
            vals = last[1:]

        row = [fname_colored, type_str, step_str] + vals + [status_str]
        table_rows.append(row)

    draw_table(headers, table_rows)
    print(
        f"\n统计: {Colors.GREEN}{complete_count}{Colors.ENDC} 个文件已完成 / 共 {len(valid_files)} 个有效文件。"
    )


# --- 主程序入口 ---


def collect_output_files(args):
    if not args:
        return sorted(set(glob.glob("*.log") + glob.glob("*.out")))

    files = []
    for arg in args:
        if os.path.isdir(arg):
            files.extend(glob.glob(os.path.join(arg, "*.log")))
            files.extend(glob.glob(os.path.join(arg, "*.out")))
        elif "*" in arg or "?" in arg or "[" in arg:
            files.extend(glob.glob(arg))
        else:
            files.append(arg)

    return sorted(dict.fromkeys(files))


def main():
    args = sys.argv[1:]

    if len(args) == 1 and not os.path.isdir(args[0]) and not ("*" in args[0] or "?" in args[0] or "[" in args[0]):
        if os.path.exists(args[0]):
            show_single_file_detail(args[0])
        else:
            print(f"错误：文件 {args[0]} 不存在。")
        return

    files = collect_output_files(args)
    if not files:
        if len(args) == 0:
            print("当前目录无 .log 或 .out 文件。")
        else:
            print("指定路径无 .log 或 .out 文件。")
        sys.exit(0)

    if len(files) == 1 and len(args) == 1 and not os.path.isdir(args[0]):
        show_single_file_detail(files[0])
    else:
        show_batch_summary(files)


if __name__ == "__main__":
    main()
