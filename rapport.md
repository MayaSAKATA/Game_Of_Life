# Rapport projet jeu de la vie  — Maya Sakata, Coline Palefroy, Maelle Rouvray


Ce projet vise à implémenter le jeu de la vie de manière parallèle. Pour cela, on part du fichier *game_of_life.py* qui correspond au code qui réalise ce jeu de manière séquentielle.
La parallélisation se fait avec MPI et la commande d'exécution des programmes est *mpiexec -n k python nom_fichier.py* en remplacant k par le nombre de processus souhaités.

## Parallélisation sur 2 processus  — *game_of_life_parallel.py*
Dans un premier temps, on parallélise le fichier de base sur 2 processus uniquement. Le processus 0 se charge de calculer la nouvelle génération et d'envoyer la liste des cellules modifiées au processus 1. Le processus 1 reçoit les modifications et s'occupe de mettre à jour localement la grille puis de l'afficher.
Le processus 0 s'occupe donc du calcul tandis que le processus 1 gère l'affichage.
Pour 2 processus, le temps de calcul pour chaque itération est $8,55.10^{-2}$ secondes et le temps d'affichage est $1,34.10^{-2}$ secondes.

## Parallélisation avec Split  — *game_of_life_split_vf.py*
On parallélise maintenant à l'aide de la fonction *Split* sur 2 processus comme précédemment. Le processus 0 calcule toujours la nouvelle génération et envoie les cellules modifiées au processus 1, qui les reçoit et réalise la mise à jour de la grille et son affichage.
Pour 2 processus, le temps de calcul pour chaque itération est $2,06.10^{-2}$ secondes et le temps d'affichage est $1,86.10^{-2}$ secondes.

## Parallélisation horizontale  — *game_of_life_domain_decomposition.py*
On découpe l'espace en bandes horizontales. Chaque processus gère un bloc de lignes composé de 2 lignes de ghosts cells (au dessus et en dessous) nécessaires aux calculs. Puis à chaque itération, les processus échangent les lignes de frontières. Chacun des processus se charge de calculer localement la génération suivante. Seul le processus 0 réalise l'affichage de la grille.
Voici les temps moyens pour chaque itération pour différents nombre de processus :
| Nombre de processus | 2 | 4 | 8 | 16 |
|---------------------|---------|------|-------|---|
| Durée d'une itération (s) | $5,84.10^{-2}$ | $4,18.10^{-2}$ | $2,94.10^{-2}$ | ... |

On remarque que le temps diminue lorsque le nombre de processus augmente.


## tracer speedup en fonction du nombre de processus
## comparer performances des différents codes

