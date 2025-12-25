#!/bin/bash
icc=0
nfile=$(ls *.fchk | wc -l)
for inf in *.fchk; do
    ((icc++))
    echo Calculating CHELPG file for $inf
    Multiwfn ${inf} <<EOF >/dev/null
7
11
1
y
0
q
EOF
done
