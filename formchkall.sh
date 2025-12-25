#!/usr/bin/env bash
shopt -s nullglob
count=0
for chk_file in *.chk; do
    base_name="${chk_file%.chk}"
    fchk_file="${base_name}.fchk"
    echo "Processing:  $chk_file  ==>  $fchk_file"
    formchk "$chk_file" "$fchk_file"
    count=$((count + 1))
done
shopt -u nullglob
if [ $count -eq 0 ]; then
    echo "No .chk files found in the current directory."
else
    echo "Done. Processed $count files."
fi
