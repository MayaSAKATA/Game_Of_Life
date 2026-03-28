"""
Le jeu de la vie
################
Le jeu de la vie est un automate cellulaire inventé par Conway se basant normalement sur une grille infinie
de cellules en deux dimensions. Ces cellules peuvent prendre deux états :
    - un état vivant
    - un état mort
A l'initialisation, certaines cellules sont vivantes, d'autres mortes.
Le principe du jeu est alors d'itérer de telle sorte qu'à chaque itération, une cellule va devoir interagir avec
les huit cellules voisines (gauche, droite, bas, haut et les quatre en diagonales.) L'interaction se fait selon les
règles suivantes pour calculer l'irération suivante :
    - Une cellule vivante avec moins de deux cellules voisines vivantes meurt ( sous-population )
    - Une cellule vivante avec deux ou trois cellules voisines vivantes reste vivante
    - Une cellule vivante avec plus de trois cellules voisines vivantes meurt ( sur-population )
    - Une cellule morte avec exactement trois cellules voisines vivantes devient vivante ( reproduction )

Pour ce projet, on change légèrement les règles en transformant la grille infinie en un tore contenant un
nombre fini de cellules. Les cellules les plus à gauche ont pour voisines les cellules les plus à droite
et inversement, et de même les cellules les plus en haut ont pour voisines les cellules les plus en bas
et inversement.

On itère ensuite pour étudier la façon dont évolue la population des cellules sur la grille.

################
Parallélisation du code game_of_life.py

"""
import pygame  as pg
import numpy   as np
from mpi4py import MPI

globCom = MPI.COMM_WORLD.Dup()
nbp     = globCom.size
rank    = globCom.rank
name    = MPI.Get_processor_name()

class Grille:
    """
    Grille torique décrivant l'automate cellulaire.
    En entrée lors de la création de la grille :
        - dimensions est un tuple contenant le nombre de cellules dans les deux directions (nombre lignes, nombre colonnes)
        - init_pattern est une liste de cellules initialement vivantes sur cette grille (les autres sont considérées comme mortes)
        - color_life est la couleur dans laquelle on affiche une cellule vivante
        - color_dead est la couleur dans laquelle on affiche une cellule morte
    Si aucun pattern n'est donné, on tire au hasard quels sont les cellules vivantes et les cellules mortes
    Exemple :
       grid = Grille( (10,10), init_pattern=[(2,2),(0,2),(4,2),(2,0),(2,4)], color_life=pg.Color("red"), color_dead=pg.Color("black"))
    """
    def __init__(self, dim, init_pattern=None, color_life=pg.Color("black"), color_dead=pg.Color("white")):
        self.dimensions = dim
        if init_pattern is not None:
            self.cells = np.zeros(self.dimensions, dtype=np.uint8)
            indices_i = [v[0] for v in init_pattern]
            indices_j = [v[1] for v in init_pattern]
            self.cells[indices_i,indices_j] = 1
        else:
            self.cells = np.random.randint(2, size=dim, dtype=np.uint8)
        self.col_life = color_life
        self.col_dead = color_dead

    def compute_next_iteration(self, my_slice):
        """
        Calcule la prochaine génération de cellules en suivant les règles du jeu de la vie
        ajout des tranches pour que chaque processus ait acces uniquement a sa partie de la grille 
        gain de memoire et de temps 
        """
        # Remarque 1: on pourrait optimiser en faisant du vectoriel, mais pour plus de clarté, on utilise les boucles
        # Remarque 2: on voit la grille plus comme une matrice qu'une grille géométrique. L'indice (0,0) est donc en bas à gauche de la grille !
        ny_local, nx = my_slice.shape
        next_cells = np.empty((ny_local-2,nx), dtype=np.uint8)
    
        for i in range(1,ny_local-1): 
            i_above = i-1
            i_below = i+1
            for j in range(nx):
                j_left = (j-1+nx)%nx
                j_right= (j+1)%nx

                # Somme des 8 voisins dans la tranche 
                nb_voisines_vivantes = (
                    my_slice[i_above, j_left] + my_slice[i_above, j] + my_slice[i_above, j_right] +
                    my_slice[i, j_left]                             + my_slice[i, j_right] +
                    my_slice[i_below, j_left] + my_slice[i_below, j] + my_slice[i_below, j_right]
                )
                if my_slice[i,j] == 1:
                    next_cells[i-1,j] = 1 if 2 <= nb_voisines_vivantes <= 3 else 0
                else:
                    next_cells[i-1,j] = 1 if nb_voisines_vivantes == 3 else 0
        return next_cells
    
class App:
    """
    Cette classe décrit la fenêtre affichant la grille à l'écran
        - geometry est un tuple de deux entiers donnant le nombre de pixels verticaux et horizontaux (dans cet ordre)
        - grid est la grille décrivant l'automate cellulaire (voir plus haut)
    """
    def __init__(self, geometry, grid):
        self.grid = grid
        # Calcul de la taille d'une cellule par rapport à la taille de la fenêtre et de la grille à afficher :
        self.size_x = geometry[1]//grid.dimensions[1]
        self.size_y = geometry[0]//grid.dimensions[0]
        if self.size_x > 4 and self.size_y > 4 :
            self.draw_color=pg.Color('lightgrey')
        else:
            self.draw_color=None
        # Ajustement de la taille de la fenêtre pour bien fitter la dimension de la grille
        self.width = grid.dimensions[1] * self.size_x
        self.height= grid.dimensions[0] * self.size_y
        # Création de la fenêtre à l'aide de tkinter
        self.screen = pg.display.set_mode((self.width,self.height))
        self.canvas_cells = []

    def compute_rectangle(self, i: int, j: int):
        """
        Calcul la géométrie du rectangle correspondant à la cellule (i,j)
        """
        return (self.size_x*j, self.height - self.size_y*(i + 1), self.size_x, self.size_y)

    def compute_color(self, i: int, j: int):
        if self.grid.cells[i,j] == 0:
            return self.grid.col_dead
        else:
            return self.grid.col_life

    def draw(self):
        [self.screen.fill(self.compute_color(i,j),self.compute_rectangle(i,j)) for i in range(self.grid.dimensions[0]) for j in range(self.grid.dimensions[1])]
        if (self.draw_color is not None):
            [pg.draw.line(self.screen, self.draw_color, (0,i*self.size_y), (self.width,i*self.size_y)) for i in range(self.grid.dimensions[0])]
            [pg.draw.line(self.screen, self.draw_color, (j*self.size_x,0), (j*self.size_x,self.height)) for j in range(self.grid.dimensions[1])]
        pg.display.update()

if __name__ == '__main__':
    import time
    import sys

    # Split : color = 0 pour l'affichage, color = 1 pour le calcul
    if rank == 0 :
        color = 0 
    else : 
        color = 1 

    subCom= globCom.Split(color,rank) # subCom est valide uniquement pour les ranks de calcul (rank > 0)

    dico_patterns = { # Dimension et pattern dans un tuple
        'blinker' : ((5,5),[(2,1),(2,2),(2,3)]),
        'toad'    : ((6,6),[(2,2),(2,3),(2,4),(3,3),(3,4),(3,5)]),
        "acorn"   : ((100,100), [(51,52),(52,54),(53,51),(53,52),(53,55),(53,56),(53,57)]),
        "beacon"  : ((6,6), [(1,3),(1,4),(2,3),(2,4),(3,1),(3,2),(4,1),(4,2)]),
        "boat" : ((5,5),[(1,1),(1,2),(2,1),(2,3),(3,2)]),
        "glider": ((100,90),[(1,1),(2,2),(2,3),(3,1),(3,2)]),
        "glider_gun": ((400,400),[(51,76),(52,74),(52,76),(53,64),(53,65),(53,72),(53,73),(53,86),(53,87),(54,63),(54,67),(54,72),(54,73),(54,86),(54,87),(55,52),(55,53),(55,62),(55,68),(55,72),(55,73),(56,52),(56,53),(56,62),(56,66),(56,68),(56,69),(56,74),(56,76),(57,62),(57,68),(57,76),(58,63),(58,67),(59,64),(59,65)]),
        "space_ship": ((25,25),[(11,13),(11,14),(12,11),(12,12),(12,14),(12,15),(13,11),(13,12),(13,13),(13,14),(14,12),(14,13)]),
        "die_hard" : ((100,100), [(51,57),(52,51),(52,52),(53,52),(53,56),(53,57),(53,58)]),
        "pulsar": ((17,17),[(2,4),(2,5),(2,6),(7,4),(7,5),(7,6),(9,4),(9,5),(9,6),(14,4),(14,5),(14,6),(2,10),(2,11),(2,12),(7,10),(7,11),(7,12),(9,10),(9,11),(9,12),(14,10),(14,11),(14,12),(4,2),(5,2),(6,2),(4,7),(5,7),(6,7),(4,9),(5,9),(6,9),(4,14),(5,14),(6,14),(10,2),(11,2),(12,2),(10,7),(11,7),(12,7),(10,9),(11,9),(12,9),(10,14),(11,14),(12,14)]),
        "floraison" : ((40,40), [(19,18),(19,19),(19,20),(20,17),(20,19),(20,21),(21,18),(21,19),(21,20)]),
        "block_switch_engine" : ((400,400), [(201,202),(201,203),(202,202),(202,203),(211,203),(212,204),(212,202),(214,204),(214,201),(215,201),(215,202),(216,201)]),
        "u" : ((200,200), [(101,101),(102,102),(103,102),(103,101),(104,103),(105,103),(105,102),(105,101),(105,105),(103,105),(102,105),(101,105),(101,104)]),
        "flat" : ((200,400), [(80,200),(81,200),(82,200),(83,200),(84,200),(85,200),(86,200),(87,200), (89,200),(90,200),(91,200),(92,200),(93,200),(97,200),(98,200),(99,200),(106,200),(107,200),(108,200),(109,200),(110,200),(111,200),(112,200),(114,200),(115,200),(116,200),(117,200),(118,200)])
    }
    choice = 'glider'
    if len(sys.argv) > 1 :
        choice = sys.argv[1]
    resx = 800
    resy = 800
    if len(sys.argv) > 3 :
        resx = int(sys.argv[2])
        resy = int(sys.argv[3])
    if color == 0: # Print dans le terminal uniquement pour rank = 0
        print(f"Pattern initial choisi : {choice}")
        print(f"resolution ecran : {resx,resy}")
    try:
        init_pattern = dico_patterns[choice]
    except KeyError:
        print("No such pattern. Available ones are:", dico_patterns.keys())
        exit(1)

    dimension, pattern = init_pattern
    ny, nx = dimension 
    grid = Grille(dimension, init_pattern=pattern)

    if color == 1 : 
        calc_size = subCom.size 
        calc_rank = subCom.rank
        # Découpage des lignes 
        rows_per_process = ny//calc_size
        i_start = calc_rank*rows_per_process
        if calc_rank != calc_size - 1 : 
            i_end = (calc_rank +1)*rows_per_process
        else :
            i_end = ny
        my_cells = grid.cells[i_start:i_end,:].copy()

    if color == 0 :
        pg.init()
        appli = App((resx,resy), grid)
        appli.draw()

    mustContinue = True
    timings = []  # Liste pour stocker les durées

    N_ITER_BENCHMARK = 200
    TARGET_FPS = 20
    FRAME_DURATION = 1.0 / TARGET_FPS
    iter_count = 0
    while mustContinue:
        iter_count += 1
        if iter_count >= N_ITER_BENCHMARK:
            break
        t1 = time.time()
        if color == 1:
            # Ghost Cells
            neighbor_up = (subCom.rank - 1 + subCom.size) % subCom.size
            neighbor_down = (subCom.rank + 1) % subCom.size
            
            ghost_up = np.empty(nx, dtype=np.uint8)
            ghost_down = np.empty(nx, dtype=np.uint8)
            
            # On envoie la ligne du bas au voisin du bas, et on reçoit du haut
            subCom.Sendrecv(my_cells[-1,:], dest=neighbor_down, recvbuf=ghost_up, source=neighbor_up)
            # On envoie la ligne du haut au voisin du haut, et on reçoit du bas
            subCom.Sendrecv(my_cells[0,:], dest=neighbor_up, recvbuf=ghost_down, source=neighbor_down)
            
            local_slice = np.vstack([ghost_up, my_cells, ghost_down])
            my_cells = grid.compute_next_iteration(local_slice)

            all_cells = None
            if subCom.rank == 0: 
                all_cells = np.empty((ny, nx), dtype=np.uint8)
            
            # Gatherv
            counts = [(ny // calc_size) * nx] * calc_size
            counts[-1] = (ny - (calc_size-1)*(ny // calc_size)) * nx
            displs = [sum(counts[:i]) for i in range(calc_size)]
            
            subCom.Gatherv(my_cells, [all_cells, counts, displs, MPI.UNSIGNED_CHAR], root=0)

            # Envoi pour affichage 
            if subCom.rank == 0:
                next_frame_time = np.empty(1, dtype=np.float64)
                globCom.Sendrecv(all_cells, dest=0, sendtag=11, recvbuf=next_frame_time, source=0, recvtag=22)
                # Attendre le moment autorisé avant de repartir
                sleep_time = next_frame_time[0] - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

        else :
            globCom.Recv(grid.cells,source=1, tag= 11)
            t2 = time.time()
            appli.draw()
            t3 = time.time()
            timings.append(t2 - t1) # On stocke le temps de calcul + transfert pour cette itération

            next_frame_time = t1 + FRAME_DURATION  # t1 = début de cette itération
            globCom.Send(np.array([next_frame_time]), dest=1, tag=22)
            print(f"Temps calcul prochaine generation : {t2-t1:2.2e} secondes, temps affichage : {t3-t2:2.2e} secondes\n", end='');

        if color == 0 :
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    mustContinue = False
                    globCom.Abort() # On arrête tous les processus en cas de fermeture de la fenêtre
    
    if color == 0:
        filename = f"timings_{nbp-1}procs.csv"  # nbp-1 car rank 0 = affichage
        with open(filename, "w") as f:
            f.write("nbp,iteration,calc_transfer_s\n")
            for i, tc in enumerate(timings):
                f.write(f"{nbp-1},{i},{tc:.6f}\n")

        pg.quit()
