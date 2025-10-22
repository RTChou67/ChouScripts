#!/bin/bash

if [ $# -lt 1 ]; then
    echo "用法: $0 输入文件.md [输出图片前缀]"
    exit 1
fi

INPUT="$1"
OUTPUT_PDF="${2:-${INPUT%.*}.pdf}"
OUTPUT_IMG_PREFIX="${3:-${INPUT%.*}}"

pandoc "$INPUT" -o "$OUTPUT_PDF" --pdf-engine=xelatex \
    -V header-includes='\usepackage{braket}' \
    -V CJKmainfont="WenQuanYi Zen Hei"

if [ $? -ne 0 ]; then
    echo "Pandoc 转 PDF 失败，退出"
    exit 1
fi

pdftoppm -png -r 800 "$OUTPUT_PDF" "$OUTPUT_IMG_PREFIX"

if [ $? -ne 0 ]; then
    echo "pdftoppm 转 PNG 失败，退出"
    exit 1
fi

for img in ${OUTPUT_IMG_PREFIX}-*.png; do
    echo "裁剪去除空白边框: $img"
    magick "$img" -trim +repage -resample 800 "$img"
done

echo "转换完成："
echo "PDF文件: $OUTPUT_PDF"
echo "图片名称: $OUTPUT_IMG_PREFIX-*.png"

mv *.png /mnt/c/Users/arthurzcz/Downloads
