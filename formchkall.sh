#!/bin/bash

# 脚本：formchkall.sh
# 目的：对当前目录中所有的 .chk 文件运行 formchk

echo "开始处理所有 .chk 文件..."

# 用于计数
count=0

# 遍历所有 .chk 文件
for file in *.chk; do
    # 检查文件是否存在且是一个普通文件
    # 这可以防止在没有 .chk 文件时，循环体依然执行（此时 file 的值会是 "*.chk"）
    if [ -f "$file" ]; then
        echo "正在处理: $file"

        # 执行 formchk 命令
        # "$file" 使用引号是为了正确处理带空格的文件名
        formchk "$file"

        # 可选：检查上一条命令是否成功
        if [ $? -eq 0 ]; then
            echo "成功处理: $file"
        else
            echo "处理 $file 时发生错误" >&2
        fi

        count=$((count + 1))
        echo "-----------------------------------"
    fi
done

# 如果 count 仍然是 0，说明没有找到文件
if [ "$count" -eq 0 ]; then
    echo "未在当前目录找到 .chk 文件。"
else
    echo "全部完成。共处理了 $count 个文件。"
fi
