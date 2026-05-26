#!/usr/bin/env python

import glob
import os
import re
import sys


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    ENDC = "\033[0m"


THRESHOLD_PATTERNS = {
    "rmsdp": re.compile(r"RMS density matrix=([\d.Dd\-+]+)"),
    "maxdp": re.compile(r"MAX density matrix=([\d.Dd\-+]+)"),
    "de": re.compile(r"energy=([\d.Dd\-+]+)"),
}
CYCLE_PATTERN = re.compile(r"^\s*Cycle\s+(\d+)\s+Pass")
ENERGY_PATTERN = re.compile(r"E=\s*([-+]?\d*\.?\d+(?:[DdEe][-+]?\d+)?)")
RMSDP_PATTERN = re.compile(r"RMSDP=\s*([\d.Dd\-+]+)")
MAXDP_PATTERN = re.compile(r"MaxDP=\s*([\d.Dd\-+]+)")
DELTA_E_PATTERN = re.compile(r"DE=\s*([\d.Dd\-+]+)")
SCF_DONE_PATTERN = re.compile(
    r"SCF Done:\s+E\([^)]+\)\s+=\s+([-+]?\d*\.?\d+(?:[DdEe][-+]?\d+)?)\s+"
    r"A\.U\.\s+after\s+(\d+)\s+cycles?"
)


def get_visible_len(s):
    return len(re.sub(r"\033\[[0-9;]*m", "", str(s)))


def center_string(content, inner_width):
    content_str = str(content)
    visible_len = get_visible_len(content_str)
    padding = max(0, inner_width - visible_len)
    r_padding = padding // 2
    l_padding = padding - r_padding
    return " " * l_padding + content_str + " " * r_padding


def align_decimal(value_float, total_width, max_int_width, precision=10):
    value_str = f"{value_float:.{precision}f}"
    try:
        int_part, frac_part = value_str.split(".")
    except ValueError:
        int_part = value_str
        frac_part = " " * precision

    aligned = " " * (max_int_width - len(int_part)) + f"{int_part}.{frac_part}"
    return center_string(aligned, total_width)


def draw_table(headers, rows, float_columns=None, precision=10):
    if not rows:
        return

    float_columns = set(float_columns or [])
    col_widths = [len(h) for h in headers]
    max_int_width = {idx: 0 for idx in float_columns}

    for row in rows:
        for idx in float_columns:
            if idx >= len(row):
                continue
            cell = row[idx]
            if isinstance(cell, float):
                int_part = f"{cell:.{precision}f}".split(".")[0]
                max_int_width[idx] = max(max_int_width[idx], len(int_part))

    for row in rows:
        for idx, cell in enumerate(row):
            if idx >= len(col_widths):
                continue
            if idx in float_columns and isinstance(cell, float):
                cell_width = max_int_width[idx] + 1 + precision
            else:
                cell_width = get_visible_len(cell)
            col_widths[idx] = max(col_widths[idx], cell_width)

    v, h = "│", "─"
    tl, tr, bl, br = "┌", "┐", "└", "┘"
    ml, mr, tm, bm, mm = "├", "┤", "┬", "┴", "┼"

    def make_border(left, mid, right):
        return left + mid.join(h * (w + 2) for w in col_widths) + right

    print(make_border(tl, tm, tr))
    print(v + "".join(f" {center_string(hd, col_widths[i])} {v}" for i, hd in enumerate(headers)))
    print(make_border(ml, mm, mr))

    for row in rows:
        cells = []
        for idx, cell in enumerate(row):
            if idx in float_columns and isinstance(cell, float):
                cells.append(align_decimal(cell, col_widths[idx], max_int_width[idx], precision))
            else:
                cells.append(center_string(cell, col_widths[idx]))
        print(v + "".join(f" {cell} {v}" for cell in cells))

    print(make_border(bl, bm, br))


def convert_d_to_float(value):
    if value is None:
        return None
    try:
        return float(value.rstrip(".").replace("D", "E").replace("d", "E"))
    except ValueError:
        return None


def color_by_threshold(value, threshold):
    if value is None:
        return "N/A"
    color = Colors.GREEN if abs(value) < threshold else Colors.RED
    return f"{color}{value:12.2E}{Colors.ENDC}"


def detect_file_type(filename, lines_to_check=100):
    try:
        with open(filename, "r", errors="ignore") as handle:
            for _ in range(lines_to_check):
                line = handle.readline()
                if not line:
                    break
                if "Gaussian, Inc." in line or "Cite this work as:" in line:
                    return "GAUSSIAN"
    except OSError:
        return None
    return None


def read_tail(filename, size=20000):
    try:
        with open(filename, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            handle.seek(-min(file_size, size), os.SEEK_END)
            return handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""


def check_termination_status(filename):
    tail = read_tail(filename)
    if not tail.strip():
        return "RUNNING"
    if "Normal termination" in tail:
        return "NORMAL"
    if "Error termination" in tail:
        return "ERROR"
    return "RUNNING"


def get_thresholds(content):
    rmsdp_match = re.search(r"RMS density matrix=([\d.Dd\-+]+)", content)
    maxdp_match = re.search(r"MAX density matrix=([\d.Dd\-+]+)", content)
    de_match = re.search(r"energy=([\d.Dd\-+]+)", content)

    return {
        "rmsdp": convert_d_to_float(rmsdp_match.group(1)) if rmsdp_match else 1.0e-8,
        "maxdp": convert_d_to_float(maxdp_match.group(1)) if maxdp_match else 1.0e-6,
        "de": convert_d_to_float(de_match.group(1)) if de_match else 1.0e-6,
    }


def update_last_or_append(rows, row, keep_all):
    if keep_all:
        rows.append(row)
    elif rows:
        rows[0] = row
    else:
        rows.append(row)


def format_detailed_rows(raw_rows, thresholds):
    return [
        [
            cycle,
            color_by_threshold(delta_e, thresholds["de"]),
            color_by_threshold(rmsdp, thresholds["rmsdp"]),
            color_by_threshold(maxdp, thresholds["maxdp"]),
            energy,
        ]
        for cycle, delta_e, rmsdp, maxdp, energy in raw_rows
    ]


def parse_scf_steps(filename, keep_all=True):
    thresholds = {"rmsdp": 1.0e-8, "maxdp": 1.0e-6, "de": 1.0e-6}
    detailed_rows = []
    fallback_rows = []
    pending = None
    pending_remaining = 0

    try:
        with open(filename, "r", errors="ignore") as handle:
            for line in handle:
                for key, pattern in THRESHOLD_PATTERNS.items():
                    match = pattern.search(line)
                    if match:
                        value = convert_d_to_float(match.group(1))
                        if value is not None:
                            thresholds[key] = value

                done_match = SCF_DONE_PATTERN.search(line)
                if done_match:
                    energy = convert_d_to_float(done_match.group(1))
                    if energy is not None:
                        update_last_or_append(
                            fallback_rows,
                            [int(done_match.group(2)), "N/A", "N/A", "N/A", energy],
                            keep_all,
                        )

                if pending is not None:
                    stripped = line.strip()
                    if pending["energy"] is None and stripped.startswith("E="):
                        energy_match = ENERGY_PATTERN.search(stripped)
                        if energy_match:
                            pending["energy"] = convert_d_to_float(energy_match.group(1))

                    if pending["rmsdp"] is None and stripped.startswith("RMSDP="):
                        rmsdp_match = RMSDP_PATTERN.search(stripped)
                        maxdp_match = MAXDP_PATTERN.search(stripped)
                        delta_e_match = DELTA_E_PATTERN.search(stripped)
                        if rmsdp_match and maxdp_match:
                            pending["rmsdp"] = convert_d_to_float(rmsdp_match.group(1))
                            pending["maxdp"] = convert_d_to_float(maxdp_match.group(1))
                            pending["delta_e"] = (
                                convert_d_to_float(delta_e_match.group(1))
                                if delta_e_match
                                else None
                            )

                    if (
                        pending["energy"] is not None
                        and pending["rmsdp"] is not None
                        and pending["maxdp"] is not None
                    ):
                        update_last_or_append(
                            detailed_rows,
                            [
                                pending["cycle"],
                                pending["delta_e"],
                                pending["rmsdp"],
                                pending["maxdp"],
                                pending["energy"],
                            ],
                            keep_all,
                        )
                        pending = None
                    else:
                        pending_remaining -= 1
                        if pending_remaining <= 0:
                            pending = None

                cycle_match = CYCLE_PATTERN.search(line)
                if cycle_match:
                    pending = {
                        "cycle": int(cycle_match.group(1)),
                        "energy": None,
                        "rmsdp": None,
                        "maxdp": None,
                        "delta_e": None,
                    }
                    pending_remaining = 15
    except OSError:
        return [], None

    if detailed_rows:
        return format_detailed_rows(detailed_rows, thresholds), thresholds

    return fallback_rows, thresholds


def is_detailed_scf_converged(last_step):
    return all(Colors.GREEN in str(item) for item in last_step[1:4])


def has_density_convergence_data(last_step):
    return bool(last_step) and all(str(item) != "N/A" for item in last_step[1:4])


def format_status(status):
    if status == "ERROR":
        return f"{Colors.RED}FAIL{Colors.ENDC}"
    if status == "RUNNING":
        return f"{Colors.YELLOW}RUN{Colors.ENDC}"
    if status != "NORMAL":
        return f"{Colors.YELLOW}{status}{Colors.ENDC}"

    return f"{Colors.GREEN}DONE{Colors.ENDC}"


def color_filename(filename, status, scf_data):
    if status == "ERROR":
        return f"{Colors.RED}{filename}{Colors.ENDC}"
    if status == "RUNNING":
        return f"{Colors.YELLOW}{filename}{Colors.ENDC}"
    if status == "NORMAL":
        return f"{Colors.GREEN}{filename}{Colors.ENDC}"
    return filename


def show_single_file_detail(filename):
    file_type = detect_file_type(filename)
    if file_type != "GAUSSIAN":
        print(f"{Colors.RED}跳过: 无法识别为 Gaussian 输出文件{Colors.ENDC}: {filename}")
        return

    scf_data, thresholds = parse_scf_steps(filename)
    status = check_termination_status(filename)

    print(f"--- SCF 收敛监控表: {filename} [{Colors.CYAN}GAUSSIAN{Colors.ENDC}] ---")

    if thresholds:
        print("检测到的收敛阈值:")
        print(f"  DE:    {thresholds['de']:<10.1E}")
        print(f"  RMSDP: {thresholds['rmsdp']:<10.1E}")
        print(f"  MaxDP: {thresholds['maxdp']:<10.1E}\n")

    headers = ["Step", "Delta-E (DE)", "RMSDP", "MaxDP", "Total Energy (E)"]
    if scf_data:
        draw_table(headers, scf_data, float_columns={4})
    else:
        print("未找到 SCF 步骤数据。")

    print("\n--- 任务状态 ---")
    print(f"状态: {format_status(status)}")
    if status == "NORMAL":
        print("      (任务已正常结束)")


def collect_output_files(args):
    if not args:
        return sorted(set(glob.glob("*.out") + glob.glob("*.log")))

    files = []
    for arg in args:
        if os.path.isdir(arg):
            files.extend(glob.glob(os.path.join(arg, "*.out")))
            files.extend(glob.glob(os.path.join(arg, "*.log")))
        elif any(ch in arg for ch in "*?[]"):
            files.extend(glob.glob(arg))
        else:
            files.append(arg)

    return sorted(dict.fromkeys(files))


def show_batch_summary(file_list):
    valid_files = []
    for filename in sorted(file_list):
        if os.path.isfile(filename) and detect_file_type(filename) == "GAUSSIAN":
            valid_files.append(filename)

    if not valid_files:
        print("未找到有效的 Gaussian 输出文件 (.out/.log)。")
        return

    headers = ["File", "Type", "Step", "Delta-E (DE)", "RMSDP", "MaxDP", "Total Energy (E)", "Status"]
    rows = []
    complete_count = 0

    for filename in valid_files:
        status = check_termination_status(filename)
        scf_data, _ = parse_scf_steps(filename, keep_all=False)
        if status == "NORMAL":
            complete_count += 1

        step = "N/A"
        delta_e = f"{Colors.RED}No Data{Colors.ENDC}"
        rmsdp = f"{Colors.RED}No Data{Colors.ENDC}"
        maxdp = f"{Colors.RED}No Data{Colors.ENDC}"
        energy = "N/A"

        if status == "RUNNING" and not scf_data:
            delta_e = rmsdp = maxdp = f"{Colors.YELLOW}...{Colors.ENDC}"

        if scf_data:
            last_step = scf_data[-1]
            step, delta_e, rmsdp, maxdp, energy = last_step

        rows.append(
            [
                color_filename(filename, status, scf_data),
                "GAUSSIAN",
                step,
                delta_e,
                rmsdp,
                maxdp,
                energy,
                format_status(status),
            ]
        )

    print(f"--- 正在检查 {len(valid_files)} 个 Gaussian 文件 ---")
    draw_table(headers, rows, float_columns={6})
    print(
        f"\n统计: {Colors.GREEN}{complete_count}{Colors.ENDC} 个文件已完成 / 共 {len(valid_files)} 个有效文件。"
    )


def main():
    args = sys.argv[1:]

    if len(args) == 1 and not os.path.isdir(args[0]) and not any(ch in args[0] for ch in "*?[]"):
        if not os.path.exists(args[0]):
            print(f"错误: 文件 {args[0]} 不存在。")
            sys.exit(1)
        show_single_file_detail(args[0])
        return

    files = collect_output_files(args)
    if not files:
        target = "当前目录" if not args else "指定路径"
        print(f"{target}无 .out 或 .log 文件。")
        return

    if len(files) == 1 and len(args) == 1 and not os.path.isdir(args[0]):
        show_single_file_detail(files[0])
    else:
        show_batch_summary(files)


if __name__ == "__main__":
    main()
