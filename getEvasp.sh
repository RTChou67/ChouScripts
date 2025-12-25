#!/bin/bash

# 定义输出文件名
OUTPUT_FILE="vasp_energies.txt"

# 打印表格的标题，并将其重定向到输出文件（覆盖模式）
echo "--- VASP 能量提取结果 (修正版：E(sigma->0)) ---" >"$OUTPUT_FILE"
echo "" >>"$OUTPUT_FILE"
printf "%-30s %s\n" "子文件夹 (Strain/Relaxation)" "能量 E(sigma->0) (eV)" >>"$OUTPUT_FILE"
printf "%-30s %s\n" "------------------------------" "-----------------------" >>"$OUTPUT_FILE"

# 遍历当前目录下的所有子文件夹
for dir in */; do
    FOLDER_NAME=${dir%/}
    OUTCAR_PATH="$FOLDER_NAME/OUTCAR"

    if [ -f "$OUTCAR_PATH" ]; then
        # *** 关键修正：将 $5 更改为 $7 ***
        # E(sigma->0) 值位于第 7 列
        ENERGY=$(grep 'entropy=' "$OUTCAR_PATH" | tail -n 1 | awk '{print $7}')

        if [ ! -z "$ENERGY" ]; then
            printf "%-30s %s\n" "$FOLDER_NAME" "$ENERGY" >>"$OUTPUT_FILE"
        else
            printf "%-30s %s\n" "$FOLDER_NAME" "ERROR: Energy not found (Line found, but column 7 missing)" >>"$OUTPUT_FILE"
        fi
    else
        printf "%-30s %s\n" "$FOLDER_NAME" "ERROR: OUTCAR missing" >>"$OUTPUT_FILE"
    fi
done

echo "" >>"$OUTPUT_FILE"
echo "提取完成！结果已保存到文件: $OUTPUT_FILE"

# 同时在终端打印结果
cat "$OUTPUT_FILE"
