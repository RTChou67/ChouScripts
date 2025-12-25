#!/bin/bash

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Error: 缺少参数。"
    echo "用法: $0 <输入后缀> <输出格式> [可选: 文件或目录路径]"
    exit 1
fi

IN_EXT=$1
TARGET=$2
INPUT_PATH=$3

TARGET_LOWER=$(echo "$TARGET" | tr '[:upper:]' '[:lower:]')
case "$TARGET_LOWER" in
pdb)
    CODE=1
    EXT="pdb"
    ;;
xyz)
    CODE=2
    EXT="xyz"
    ;;
cml)
    CODE=31
    EXT="cml"
    ;;
cif)
    CODE=33
    EXT="cif"
    ;;
gro)
    CODE=34
    EXT="gro"
    ;;
chg)
    CODE=3
    EXT="chg"
    ;;
wfx)
    CODE=4
    EXT="wfx"
    ;;
wfn)
    CODE=5
    EXT="wfn"
    ;;
molden)
    CODE=6
    EXT="molden"
    ;;
fch)
    CODE=7
    EXT="fch"
    ;;
47)
    CODE=8
    EXT="47"
    ;;
mkl)
    CODE=9
    EXT="mkl"
    ;;
mwfn)
    CODE=32
    EXT="mwfn"
    ;;
*)
    echo "Error: 不支持的目标格式 '$TARGET'"
    exit 1
    ;;
esac
FILES=()

if [ -z "$INPUT_PATH" ]; then
    SEARCH_DIR="."
    echo "--- 模式: 扫描当前目录 ---"

elif [ -d "$INPUT_PATH" ]; then
    SEARCH_DIR="$INPUT_PATH"
    echo "--- 模式: 扫描目录 [$SEARCH_DIR] ---"

elif [ -f "$INPUT_PATH" ]; then
    FILES=("$INPUT_PATH")
    echo "--- 模式: 处理单文件 [$INPUT_PATH] ---"

else
    echo "Error: 找不到路径或文件: $INPUT_PATH"
    exit 1
fi
if [ ${#FILES[@]} -eq 0 ]; then
    SEARCH_DIR="${SEARCH_DIR%/}"
    shopt -s nullglob
    FILES=("$SEARCH_DIR"/*."$IN_EXT")
    shopt -u nullglob
    if [ ${#FILES[@]} -eq 0 ]; then
        echo "Warning: 在 $SEARCH_DIR 中未找到 .$IN_EXT 文件。"
        exit 0
    fi
fi
icc=0
NUM=${#FILES[@]}
for inf in "${FILES[@]}"; do
    ((icc++))
    outf="${inf%.*}.${EXT}"
    echo "[$icc/$NUM] Converting $inf -> $outf ..."
    Multiwfn "$inf" <<EOF >/dev/null
100
2
$CODE
$outf
0
q
EOF
done

echo "完成！"
