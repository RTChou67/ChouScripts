import os
import shutil as cinema

pwd = os.getcwd()
Filename = []
Pseudo = []
for file in os.listdir("."):
    if file.endswith(".fdf"):
        Filename.append(file)

for filename in Filename:
    start = -1
    end = -1
    TargetFile = open("{}/{}".format(pwd, filename), "r")
    Content = TargetFile.readlines()
    PseudoPath = "/home/rtchou/Study/PseudoPotential/ONCVPSP0.5-PBE"
    for i, line in enumerate(Content):
        lower = line.strip().lower()
        if lower == "%block chemicalspecieslabel":
            start = i + 1
        elif lower == "%endblock chemicalspecieslabel":
            end = i
    for i in Content[start:end]:
        Pseudo.append(i.split()[2])
        try:
            cinema.copy("{}/{}.psml".format(PseudoPath, i.split()[2]), "{}".format(pwd))
        except:
            print("ERROR: No element information could be found in {}".format(filename))
    TargetFile.close()
Pseudo = list(set(Pseudo))
print("The PseudoPotential files are copied to the current directory.")
print("The PseudoPotential files are:")
for i in Pseudo:
    print(i + ".psml")
print("Please check the PseudoPotential files.")
