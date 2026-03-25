"""
Calcule le speedup de domain_decomposition.py en fonction du nombre de processus.
Lance simplement : python3 speedup.py
"""
import subprocess
import re

SCRIPT   = "game_of_life_domain_decomposition.py"
PATTERN  = "glider"
NBP_LIST = [1, 2, 4, 8]  # nombres de processus à tester

def get_temps_moyen(nbp):
    """Lance domain_decomp avec nbp processus et retourne le temps moyen par itération."""
    result = subprocess.run(
        ["mpiexec", "-n", str(nbp), "python3", SCRIPT, PATTERN],
        capture_output=True, text=True
    )
    # On cherche tous les temps de calcul dans les prints de rank 0
    # ex: "[Rank 0] Total iter : 1.23e-02s | Affichage : 4.56e-03s"
    temps = re.findall(r"Total iter : ([\d.e+-]+)s", result.stdout)
    if not temps:
        print(f"  Aucun temps trouvé pour nbp={nbp}, stdout:")
        print(result.stdout)
        return None
    temps = [float(t) for t in temps]
    return sum(temps) / len(temps)  # moyenne sur toutes les itérations


if __name__ == '__main__':
    print(f"\nBenchmark speedup — pattern: {PATTERN}")
    print(f"{'nbp':<6} {'Temps moy (s)':<18} {'Speedup':<12} {'Efficacité'}")
    print("-" * 50)

    t_seq = None
    for nbp in NBP_LIST:
        print(f"  Lancement avec {nbp} processus...", end=" ", flush=True)
        t = get_temps_moyen(nbp)
        if t is None:
            continue
        if nbp == 1:
            t_seq = t
        speedup    = t_seq / t if t_seq else None
        efficacite = speedup / nbp if speedup else None
        print(f"\r{nbp:<6} {t:<18.4e} {speedup:<12.2f} {efficacite*100:.1f}%")

    print()