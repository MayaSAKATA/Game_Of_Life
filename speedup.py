import glob
import pandas as pd
import matplotlib.pyplot as plt

# Lecture de tous les fichiers timings_Xprocs.csv
files = glob.glob("timings_*procs.csv")

if not files:
    print("Aucun fichier timings_*procs.csv trouvé.")
    exit(1)

# Calcul du temps moyen par configuration
results = {}
for f in files:
    df = pd.read_csv(f)
    nbp = df["nbp"].iloc[0]
    results[nbp] = df["calc_transfer_s"].mean()

# Tri par nombre de processus
results = dict(sorted(results.items()))
nbps = list(results.keys())
times = list(results.values())

# Référence = 1 processus de calcul
t_ref = results[1]
speedups = [t_ref / t for t in times]

# Tracé
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(nbps, speedups, marker='o', label="Speedup mesuré")
ax.plot(nbps, nbps, linestyle='--', color='gray', label="Speedup idéal")
ax.set_xlabel("Nombre de processus de calcul")
ax.set_ylabel("Speedup")
ax.set_title("Speedup du jeu de la vie en fonction du nombre de processus")
ax.legend()
ax.grid(True)
plt.tight_layout()
plt.savefig("speedup.png", dpi=150)
plt.show()
print("Graphique sauvegardé dans speedup.png")