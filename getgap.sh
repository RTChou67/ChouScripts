#!/bin/bash

# 打印表头 (Tab 分隔)
# 顺序: Folder, E_tot, VBM, CBM, Gap, E_f
echo -e "Folder\tE_tot\tVBM\tCBM\tGap\tE_f"

# 遍历所有子目录下的 EIGENVAL (包括当前目录)
for file in */EIGENVAL EIGENVAL; do

    # 检查文件是否存在
    if [ ! -f "$file" ]; then
        continue
    fi

    # 获取目录路径
    dirname=$(dirname "$file")
    outcar="${dirname}/OUTCAR"

    # --- 初始化变量 ---
    e_fermi="NaN"
    e_total="NaN"

    # --- 1. 从 OUTCAR 提取 Fermi Level 和 Total Energy ---
    if [ -f "$outcar" ]; then
        # 提取费米能级 (倒数第一个 E-fermi)
        e_fermi=$(grep "E-fermi" "$outcar" | tail -1 | awk '{print $3}')

        # 提取总能量 (energy without entropy)
        # 逻辑：搜索 "energy  without entropy"，取最后一行
        # 使用 awk -F'=' 以等号分割，取第2部分，再取第1个字段
        e_total=$(grep "energy  without entropy" "$outcar" | tail -1 | awk -F'=' '{print $2}' | awk '{print $1}')
    fi

    # --- 2. 从 EIGENVAL 提取 VBM/CBM/Gap (Awk 高速版) ---
    band_data=$(awk '
    BEGIN {
        vbm = -99999;
        cbm = 99999;
        nbands = 0;
        found_header = 0;
    }

    # 寻找 NBANDS
    !found_header && FNR <= 20 && NF == 3 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/ {
        if ($3 > 0) {
            nbands = $3;
            found_header = 1;
        }
        next;
    }

    # 提取能带
    found_header && NF == 3 {
        idx = $1;
        en = $2;
        occ = $3;

        # 校验数据行
        if (idx ~ /^[0-9]+$/ && idx >= 1 && idx <= nbands) {
            if (occ > 0.5) {
                if (en > vbm) vbm = en;
            } else {
                if (en < cbm) cbm = en;
            }
        }
    }

    END {
        if (vbm != -99999 && cbm != 99999) {
            # 输出: VBM \t CBM \t Gap
            printf "%.6f\t%.6f\t%.6f", vbm, cbm, cbm - vbm;
        } else {
            printf "NaN\tNaN\tNaN";
        }
    }
    ' "$file")

    # --- 3. 整合输出 ---
    # 空值检查
    if [ -z "$e_fermi" ]; then e_fermi="NaN"; fi
    if [ -z "$e_total" ]; then e_total="NaN"; fi

    # 输出顺序: Folder -> E_tot -> (VBM, CBM, Gap) -> E_f
    echo -e "${dirname}\t${e_total}\t${band_data}\t${e_fermi}"

done
