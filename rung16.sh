#!/bin/zsh -i

start_time=$EPOCHREALTIME

icc=0
gjf_files=(./*.gjf)
nfile=${#gjf_files[@]}

if [[ $nfile -eq 0 ]]; then
    echo "❌ No .gjf files found in $workdir."
    exit 1
fi

for inf in "${gjf_files[@]}"; do
    ((icc++))
    fname="${inf##*/}" # 去掉路径前缀 ./xxx.gjf -> xxx.gjf
    outfile="${fname%.gjf}.out"

    echo "🧪 Running $fname ... ($icc of $nfile)"

    if g16 <"$inf" >"$outfile"; then
        echo "✅ $fname has finished successfully"
    else
        echo "❌ $fname failed to run"
    fi
done

end_time=$EPOCHREALTIME
elapsed=$(printf "%.2f" "$(echo "$end_time - $start_time" | bc)")
echo "⏱️ Total elapsed time: ${elapsed} seconds"
