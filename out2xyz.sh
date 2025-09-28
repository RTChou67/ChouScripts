icc=0
nfile=$(ls *.out | wc -l)
for inf in *.out; do
    ((icc++))
    echo "Converting ${inf} to ${inf//out/xyz} ... ($icc of $nfile)"
    Multiwfn ${inf} <<EOF >/dev/null
100
2
2
${inf//out/xyz}
0
q
EOF
done
