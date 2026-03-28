# Rapport projet jeu de la vie  — Maya Sakata, Coline Palefroy, Maelle Rouvray

Ce projet vise à implémenter le jeu de la vie de manière parallèle. Pour cela, nous sommes parties du fichier *game_of_life.py* qui correspond au code qui réalise ce jeu de manière séquentielle.

La parallélisation se fait avec MPI et la commande d'exécution des programmes est `mpiexec -n k python nom_fichier.py` en remplacant k par le nombre de processus souhaités.

## Parallélisation sur 2 processus  — *game_of_life_parallel.py*

Dans un premier temps, nous avons parallélise le fichier fourni sur 2 processus uniquement. Le processus 0 se charge de calculer la nouvelle génération et d'envoyer la liste des cellules modifiées au processus 1. Le processus 1 reçoit les modifications et s'occupe de mettre à jour localement la grille puis de l'afficher.
Le processus 0 s'occupe donc du calcul tandis que le processus 1 gère l'affichage.

Pour 2 processus,

- le temps de calcul pour chaque itération est environ $8.5\times10^{-2}$ secondes.
- le temps d'affichage est environ $1.3\times10^{-2}$ secondes.

## Parallélisation avec Split  — *game_of_life_split_vf.py*

Nous avons parallélisé à l'aide de la fonction *Split* sur 2 processus comme précédemment. Le processus 0 calcule toujours la nouvelle génération et envoie les cellules modifiées au processus 1, qui les reçoit et réalise la mise à jour de la grille et son affichage.

Pour 2 processus,

- le temps de calcul pour chaque itération est environ $8\times10^{-3}$ secondes.
- le temps d'affichage est $1.2\times10^{-2}$ secondes.

## Parallélisation horizontale  — *game_of_life_domain_decomposition.py*

Nous avons découpé l'espace en bandes horizontales.

Chaque processus gère un bloc de lignes composé de 2 lignes de cellules fantômes (au dessus et en dessous) nécessaires aux calculs. Puis à chaque itération, les processus échangent les lignes de frontières. Chacun des processus se charge de calculer localement la génération suivante. Seul le processus 0 réalise l'affichage de la grille.
Voici les temps moyens pour chaque itération pour différents nombre de processus :

| Nombre de processus | 2 | 4 | 8 |
| --------------------- | --------- | ------ | ------- |
| Durée d'une itération | $1.8\times10^{-2}$ | $1.15\times10^{-2}$ | $1.2\times10^{-2}$ |
| Durée de l'affichage | $3.8\times10^{-3}$ | $3.6\times10^{-3}$ | $3.5\times10^{-3}$ |

On remarque que le temps diminue lorsque le nombre de processus augmente.

## Combinaison de split avec la décomposition de domaine  — *game_of_life_domain_split.py*

Une fois le split et la décomposition de domaine maîtrisée, nous avons combiné les deux méthodes. On choisit de découper les processus de la manière suivante :

- le processus 0 affiche, écrit dans le terminal et récupère les données de temps -> color = 0
- les processus de 1 à nbp se chargent des calculs -> color = 1

Dans une première approche, un `time.sleep()` de durée fixe a été introduit au début de la boucle principale afin de cadencer les itérations et obtenir une animation fluide.

Cependant, cette méthode s'est révélée insuffisante pour deux raisons.

- `time.sleep()` n'est pas précis : le système d'exploitation ne garantit qu'une durée minimale de sommeil, le réveil réel pouvant varier de plusieurs millisecondes selon la charge du scheduler.
- Les processus de calcul et d'affichage appellent `time.sleep()` de manière indépendante. Leurs durées de sommeil dérivent l'une par rapport à l'autre, introduisant une attente variable à chaque itération.

Pour résoudre ce problème, on intègre la cadence directement dans le mécanisme de synchronisation MPI existant. À la fin de chaque itération, le processus d'affichage calcule le timestamp absolu `t1 + FRAME_DURATION`, où `t1` est l'horodatage du début de l'itération courante, et transmet ce timestamp au processus de calcul dans le message d'acquittement. Le processus de calcul, après réception, attend que ce moment soit atteint avant de repartir pour l'itération suivante.

Ainsi, la durée de chaque itération est ancrée sur une référence temporelle absolue commune aux deux processus : toute dérive accumulée lors d'une itération est automatiquement corrigée à la suivante, garantissant une vitesse d'animation constante et indépendante des aléas du système.

## Speedup en fonction du nombre de processus

Avec le pattern glider :

| nbp | Temps moy (s) | Speedup | Efficacité |
| ---- | ----------------- | ------- | ------ |
| 1 | 2.9581e-02 | 1.00 | 100.0% |
| 2 | 1.7175e-02 | 1.72 | 86.1% |
| 4 | 1.1405e-02 | 2.59 | 64.8% |
| 8 | 2.4167e-02 | 1.22 | 15.3% |

## Comparaison des performances des différentes méthodes

Les résultats du benchmark montrent que la parallélisation par décomposition de domaine apporte un gain significatif jusqu'à 4 processus, avec un speedup de 2.59x pour une efficacité de 64.8%.

Au-delà, on observe une dégradation des performances : à 8 processus, le speedup chute à 1.22x et l'efficacité tombe à 15.3%. Ce phénomène s'explique par la taille limitée de la grille utilisée (100×90) : chaque processus ne traite que 12 lignes, ce qui rend le coût des communications MPI (synchronisation des ghost cells et Gather) disproportionné par rapport au temps de calcul pur.

On retrouve ici la loi d'Amdahl, qui prédit que le speedup est limité par la fraction non parallélisable du programme (ici dominée par les communications). Le point optimal se situe donc à 4 processus pour cette configuration, et l'on peut s'attendre à de meilleures performances avec 8 processus sur une grille plus grande.
