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

Pour lancer le programme avec 4 processus : mpiexec -n 4 python3 game_of_life_domain_decomposition.py


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
        import random
        self.dimensions_global= dim
        self.dimensions_local = (dim[0]//nbp, dim[1]) # On suppose que le nombre de processus divise le nombre de lignes de la grille
        self.cells = np.empty((self.dimensions_local[0]+2, self.dimensions_local[1]), dtype=np.uint8) # +2 pour prendre les ghost cells en dessous et au dessus
        if init_pattern is not None:
            self.cells[:, :] = 0 # On initialise la grille à 0 (toutes les cellules mortes)
            self.fill_with_pattern(init_pattern)
        else:
            self.cells[1:self.dimensions_local[0]+1,:] = np.random.randint(2, size=self.dimensions_local, dtype=np.uint8) # On remplit la partie centrale de la grille (sans les ghost cells) avec des 0 ou des 1 tirés au hasard
        self.col_life = color_life
        self.col_dead = color_dead
    

    def fill_with_pattern(self, init_pattern):
        """ 
        Rempli la grille avec le pattern donné en argument, en tenant compte du rang du processus pour ne remplir que la partie de la grille qui lui est attribuée
        """
        start_row = self.dimensions_local[0]*rank
        end_row   = self.dimensions_local[0]*(rank+1) # chaque processus prend une seule ligne  

        for (i,j) in init_pattern:
            if start_row <= i < end_row :
                self.cells[i -start_row + 1, j] = 1  

    def compute_next_iteration(self):
        """
        Calcule la prochaine génération de cellules en suivant les règles du jeu de la vie
        """
        # Remarque 1: on pourrait optimiser en faisant du vectoriel, mais pour plus de clarté, on utilise les boucles
        # Remarque 2: on voit la grille plus comme une matrice qu'une grille géométrique. L'indice (0,0) est donc en bas
        #             à gauche de la grille !
        ny = self.dimensions_local[0]
        nx = self.dimensions_global[1] # dimensions_global[1]=dimensions_local[1] chaque ligne reste de la même longueur pour tous les processus
        #next_cells = np.empty(self.dimensions_local, dtype=np.uint8)
        next_cells = np.empty((ny+2,nx), dtype=np.uint8) # +2 pour les ghost cells
        diff_cells = []
        for i in range(1, ny+1):
            i_above = i-1  #(i+ny-1)%ny
            i_below = i+1  #(i+1)%ny
            for j in range(nx):
                j_left = (j-1+nx)%nx
                j_right= (j+1)%nx
                voisins_i = [i_above,i_above,i_above, i     , i      , i_below, i_below, i_below]
                voisins_j = [j_left ,j      ,j_right, j_left, j_right, j_left , j      , j_right]
                voisines = np.array(self.cells[voisins_i,voisins_j])
                nb_voisines_vivantes = np.sum(voisines)
                if self.cells[i,j] == 1: # Si la cellule est vivante
                    if (nb_voisines_vivantes < 2) or (nb_voisines_vivantes > 3):
                        next_cells[i,j] = 0 # Cas de sous ou sur population, la cellule meurt
                        diff_cells.append(i*nx+j)
                    else:
                        next_cells[i,j] = 1 # Sinon elle reste vivante
                elif nb_voisines_vivantes == 3: # Cas où cellule morte mais entourée exactement de trois vivantes
                    next_cells[i,j] = 1         # Naissance de la cellule
                    diff_cells.append(i*nx+j)
                else:
                    next_cells[i,j] = 0         # Morte, elle reste morte.
        self.cells[1:ny+1, :] = next_cells[1:ny+1, :]  # on remplace juste les lignes réelles et pas les ghosts cells
        return diff_cells

    def sync_ghosts_cells(self):
        """
        Synchronise les ghost cells de la grille en envoyant les lignes de bordure à l'aide de globCom
        """
        voisin_haut = (rank-1)%nbp
        voisin_bas  = (rank+1)%nbp

        # Vers le haut
        if rank%2 == 0 : # Processus pairs, on fait d'abord les échanges dans un sens, puis dans l'autre pour éviter les interblocages
            globCom.Send(self.cells[1,:], dest=voisin_haut) # On envoie la première ligne de la partie centrale de la grille (sans les ghost cells) au voisin du haut
            globCom.Recv(self.cells[self.dimensions_local[0]+1,:], source=voisin_bas) # On reçoit la ligne de bordure du voisin du bas et on la stocke dans la ghost cell du bas (la dernière ligne de self.cells)

        else : # processus impairs
            globCom.Recv(self.cells[self.dimensions_local[0]+1,:], source=voisin_bas)
            globCom.Send(self.cells[1,:], dest=voisin_haut)

        # Vers le bas
        if rank%2 == 0 : # Processus pairs, on fait d'abord les échanges dans un sens, puis dans l'autre pour éviter les interblocages
            globCom.Send(self.cells[self.dimensions_local[0],:], dest=voisin_bas) # On envoie la dernière ligne de la partie centrale de la grille (sans les ghost cells) au voisin du bas
            globCom.Recv(self.cells[0,:], source=voisin_haut) # On reçoit la ligne de bordure du voisin du haut et on la stocke dans la ghost cell du haut (la première ligne de self.cells)   

        else : # processus impairs
            globCom.Recv(self.cells[0,:], source=voisin_haut)
            globCom.Send(self.cells[self.dimensions_local[0],:], dest=voisin_bas)

class App:
    """
    Cette classe décrit la fenêtre affichant la grille à l'écran
        - geometry est un tuple de deux entiers donnant le nombre de pixels verticaux et horizontaux (dans cet ordre)
        - grid est la grille décrivant l'automate cellulaire (voir plus haut)
    """
    def __init__(self, geometry, grid):
        self.grid = grid
        # Calcul de la taille d'une cellule par rapport à la taille de la fenêtre et de la grille à afficher :
        self.size_x = geometry[1]//grid.dimensions_global[1]
        self.size_y = geometry[0]//grid.dimensions_global[0]
        if self.size_x > 4 and self.size_y > 4 :
            self.draw_color=pg.Color('lightgrey')
        else:
            self.draw_color=None
        # Ajustement de la taille de la fenêtre pour bien fitter la dimension de la grille
        self.width = grid.dimensions_global[1] * self.size_x
        self.height= grid.dimensions_global[0] * self.size_y
        # Création de la fenêtre à l'aide de tkinter
        self.screen = pg.display.set_mode((self.width,self.height))
        #
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

    def draw(self, global_cells):
        for i in range(self.grid.dimensions_global[0]):
            for j in range(self.grid.dimensions_global[1]):
                color = self.grid.col_life if global_cells[i, j] else self.grid.col_dead
                self.screen.fill(color, self.compute_rectangle(i, j))
        if self.draw_color is not None:
            for i in range(self.grid.dimensions_global[0]):
                pg.draw.line(self.screen, self.draw_color, (0, i*self.size_y), (self.width, i*self.size_y))
            for j in range(self.grid.dimensions_global[1]):
                pg.draw.line(self.screen, self.draw_color, (j*self.size_x, 0), (j*self.size_x, self.height))
        pg.display.update()

if __name__ == '__main__':
    import time
    import sys

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
    if rank == 0:
        print(f"\nPattern initial choisi : {choice}")
        print(f"resolution ecran : {resx,resy}\n")
    try:
        init_pattern = dico_patterns[choice]
    except KeyError:
        print("No such pattern. Available ones are:", dico_patterns.keys())
        exit(1)
    
    dim_global = init_pattern[0]
    init_coord = init_pattern[1]
    grid = Grille(dim=dim_global, init_pattern=init_coord)

    if rank == 0 :
        pg.init()
        appli = App((resx, resy), grid)
    
    mustContinue = True
    while mustContinue:
        t1 = time.time()
        grid.sync_ghosts_cells() # synchronisation des ghost cells avant de calculer la prochaine génération
        grid.compute_next_iteration() # calcul de la prochaine génération

        # reconstruction grille globale
        local_block = grid.cells[1:grid.dimensions_local[0]+1,:] # partie centrale de la grille sans les ghost cells
        local_flat = local_block.flatten() # on aplatit le bloc local pour pouvoir l'envoyer avec globCom

        recvbuff = None
        if rank == 0:
            recvbuff = np.empty(dim_global[0] * dim_global[1], dtype=np.uint8)

        globCom.Gather(local_flat, recvbuff, root=0) # rassemblement de tous les blocs locaux dans recvbuff sur le processus 0

        if rank == 0:
            global_grid = recvbuff.reshape(dim_global)

            t_disp_start = time.time()
            appli.draw(global_grid)
            t_disp = time.time() - t_disp_start
            t_total = time.time() - t1
            print(f"[Rank 0] Total iter : {t_total:2.2e}s | Affichage : {t_disp:2.2e}s")

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    mustContinue = False
        
        mustContinue = globCom.bcast(mustContinue, root=0) # communication globale de l'arrêt (fermeture fenêtre d'affichage)
    pg.quit()