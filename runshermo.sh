#!/bin/zsh

# 1. 初始化输出文件，写入表头
# 输出列：文件名, 电子能, U校正, H校正, G校正, 总U, 总H, 总G
echo -e "File\tE_elec\tU_corr\tH_corr\tG_corr\tTotal_U\tTotal_H\tTotal_G" >summary.txt

# 2. 遍历所有 .out 文件
for f in *.out; do
    # 3. 执行 Shermo 并获取最后 20 行 (包含了 Total 板块的所有信息)
    # 将结果存入变量 raw_data 中，避免重复运行 Shermo
    raw_data=$(Shermo "$f" | tail -n 20)

    # 4. 使用 grep 和 awk 提取各项数据
    # $(NF-1) 表示倒数第二个字段，即数值部分

    # 电子能 (Electronic energy)
    # 注意：输出中可能出现多次 "Electronic energy"，tail -n 20 保证了我们取的是最后汇总段落的那个
    e_elec=$(echo "$raw_data" | grep "Electronic energy:" | tail -n 1 | awk '{print $(NF-1)}')

    # 热力学校正值 (Thermal corrections)
    u_corr=$(echo "$raw_data" | grep "Thermal correction to U:" | awk '{print $(NF-1)}')
    h_corr=$(echo "$raw_data" | grep "Thermal correction to H:" | awk '{print $(NF-1)}')
    g_corr=$(echo "$raw_data" | grep "Thermal correction to G:" | awk '{print $(NF-1)}')

    # 热力学总能量 (Sum of electronic energy and ...)
    # 使用正则 "Sum.*correction to X" 匹配较长的描述
    u_tot=$(echo "$raw_data" | grep "Sum.*correction to U:" | awk '{print $(NF-1)}')
    h_tot=$(echo "$raw_data" | grep "Sum.*correction to H:" | awk '{print $(NF-1)}')
    g_tot=$(echo "$raw_data" | grep "Sum.*correction to G:" | awk '{print $(NF-1)}')

    # 5. 写入 summary 文件，使用制表符分隔
    echo -e "$f\t$e_elec\t$u_corr\t$h_corr\t$g_corr\t$u_tot\t$h_tot\t$g_tot" >>summary.txt
done

# 6. 显示结果预览
cat summary.txt
