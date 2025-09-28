#!/bin/zsh

# 初始化输出文件
echo -e "File\tU (a.u.)\tH (a.u.)\tG (a.u.)" > summary.txt

# 遍历所有 .out 文件
for f in *.out; do
    # 执行 Shermo 并提取最后三行
    output=("${(@f)$(Shermo "$f" | tail -n 3)}")

    # 从每一行中提取数字（假设格式固定，倒数第二个字段为数值）
    u=$(echo $output[1] | awk '{print $(NF-1)}')
    h=$(echo $output[2] | awk '{print $(NF-1)}')
    g=$(echo $output[3] | awk '{print $(NF-1)}')

    # 写入 summary 文件
    echo -e "$f\t$u\t$h\t$g" >> summary.txt
done
cat summary.txt
