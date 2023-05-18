import time
import cv2
import numpy as np
import sys
import matplotlib.pyplot as plt
import os
import glob


# création de l'image à partir d'un fichier


list_widePieces = []
list_widePieces_mask = []
list_contours_sorted = []
list_cutPieces = []
list_cutPieces_mask = []
list_cutPiecesWithInfos = []


# vide les dossier
def clearFolder(filename):
    files = glob.glob(filename)
    for f in files:
        os.remove(f)


clearFolder("./Mask/cutMask/*")
clearFolder("./Mask/wideMask/*")
clearFolder("./images/cutPieces/*")
clearFolder("./images/widePieces/*")
clearFolder("./images/infoPieces/*")
clearFolder("./images/masque_binaire.jpg")
clearFolder("./images/piece_découpe.png")
clearFolder("./images/pieces_couleurs_numérotées.jpg")


def saveInFile(list, path, name=""):
    for i, piece in enumerate(list):
        # print("Sauvegarde de " + path + name + "pièce" + str(i) + ".jpg : ", end="")
        if cv2.imwrite(
            path + (("pièce" + str(i)) if name == "" else name) + ".jpg", piece
        ):
            # print("succès")
            continue

        else:
            print("Erreur")
            return False

    return True


def random_non_red_color():
    new_col_R = np.random.randint(0, 205)
    new_col_G = np.random.randint(new_col_R / 2 + 50, 255)
    new_col_B = np.random.randint(new_col_R / 2 + 50, 255)

    # Si les valeurs G et B dépassent 255, les réduire à 255
    new_col_G = min(new_col_G, 255)
    new_col_B = min(new_col_B, 255)

    return (new_col_R, new_col_G, new_col_B)


def sort_contours(contours, img, tolerance_ratio=0.1):
    # Tri des contours par ordre croissant en fonction de leur position en Y, puis en X
    contours_sorted = sorted(
        contours, key=lambda c: (cv2.boundingRect(c)[1], cv2.boundingRect(c)[0])
    )

    # Calcul de la tolérance verticale pour déterminer si deux contours sont sur la même ligne
    tolerance = int(img.shape[0] * tolerance_ratio)

    # Initialisation des lignes et de la première ligne avec le premier contour
    lines = []
    current_line = [contours_sorted[0]]
    current_line_y = cv2.boundingRect(contours_sorted[0])[1]

    # Parcours des contours triés et regroupement par ligne
    for contour in contours_sorted[1:]:
        y = cv2.boundingRect(contour)[1]
        if abs(y - current_line_y) <= tolerance:  # Si le contour est sur la même ligne
            current_line.append(contour)
        else:  # Si le contour est sur une nouvelle ligne
            lines.append(current_line)
            current_line = [contour]
            current_line_y = y

    # Ajout de la dernière ligne de contours
    lines.append(current_line)

    # Tri des contours à l'intérieur de chaque ligne par ordre croissant en fonction de leur position en X
    sorted_lines = [
        sorted(line, key=lambda c: cv2.boundingRect(c)[0]) for line in lines
    ]

    # Fusion des contours triés par ligne pour obtenir la liste finale des contours triés par lignes et colonnes
    sorted_contours = [contour for line in sorted_lines for contour in line]

    return sorted_contours


img = cv2.imread("./images/startImage.jpg")

cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

img = img[5:-5, 5:-5]


def createBinaryMask(img, tolerance, tolA=0, tolB=0, tolL=0):
    imgBlured = cv2.medianBlur(img, 5)

    # on convertit l'image en LAB
    masqueB = cv2.cvtColor(imgBlured, cv2.COLOR_RGB2LAB)

    # Calcule l'histogramme LAB
    hist_l = cv2.calcHist([masqueB], [0], None, [256], [0, 256])
    hist_a = cv2.calcHist([masqueB], [1], None, [256], [0, 256])
    hist_b = cv2.calcHist([masqueB], [2], None, [256], [0, 256])

    # on récupère la couleur dominante
    dominant_color_l = np.argmax(hist_l)
    dominant_color_a = np.argmax(hist_a)
    dominant_color_b = np.argmax(hist_b)

    # print("dominant_color : ",dominant_color_l, dominant_color_a, dominant_color_b)

    # on parcourt l'image
    for i in range(masqueB.shape[0]):
        for j in range(masqueB.shape[1]):
            # si la couleur est trop proche de la couleur dominante
            # on la considère comme étant la couleur dominante
            if (
                abs(masqueB[i, j][0] - dominant_color_l) < tolerance + tolL
                and abs(masqueB[i, j][1] - dominant_color_a) < tolerance + tolA
                and abs(masqueB[i, j][2] - dominant_color_b) < tolerance + tolB
            ):
                masqueB[i, j] = 0
            else:
                masqueB[i, j] = 255
    # fermeture
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (6, 6))
    masqueB = cv2.morphologyEx(masqueB, cv2.MORPH_CLOSE, kernel)

    # # ouverture
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (4, 4))
    masqueB = cv2.morphologyEx(masqueB, cv2.MORPH_OPEN, kernel)

    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (6, 6))
    masqueB = cv2.morphologyEx(masqueB, cv2.MORPH_CLOSE, kernel)

    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (8, 8))
    masqueB = cv2.morphologyEx(masqueB, cv2.MORPH_OPEN, kernel)

    # # dilate
    kernel = np.ones((1, 1), np.uint8)
    masqueB = cv2.dilate(masqueB, kernel, iterations=1)

    kernel = np.ones((1, 1), np.uint8)
    masqueB = cv2.erode(masqueB, kernel, iterations=1)

    masqueB = masqueB[:, :, 0]

    # cv2.imshow("img_labL", masqueB)
    if saveInFile([masqueB], "./images/", "masque_binaire"):
        print("masque_binaire enregistré avec succès", end="\n\n")
        return masqueB, True
    else:
        print("masque_binaire non enregistré")
        return False


def extractPieces(masqueB):
    # # find contours
    contours, hierarchy = cv2.findContours(
        masqueB, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )

    # Regarde si les contours ont été trouvés
    if len(contours) > 0:
        # print("Nombre de contours trouvés = " + str(len(contours)))

        contours = sort_contours(contours, masqueB)

        # enleve le dernier contour car c'est le logo
        contours = contours[:-1]

        # Créer une image vierge de la même taille que l'original
        img_pieces = np.zeros_like(masqueB)

        img_pieces = cv2.cvtColor(img_pieces, cv2.COLOR_GRAY2RGB)

        for i, cnt in enumerate(contours):
            # Remplir la pièce avec une couleur aléatoire
            newColor = random_non_red_color()
            cv2.drawContours(img_pieces, contours, i, newColor, -1)

            x, y, w, h = cv2.boundingRect(cnt)
            center_x, center_y = x + w // 2, y + h // 2

            # Dessiner l'indice de la pièce au centre
            cv2.putText(
                img_pieces,
                str(i),
                (center_x, center_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.1,  # Taille de la police
                (0, 0, 255),  # Couleur en BGR (rouge)
                2,  # Epaisseur de la ligne
            )

        # cv2.imshow("Pièces de puzzle en couleurs", img_pieces)
        # cv2.waitKey(0)
        saveInFile([img_pieces], "./images/", "pieces_couleurs_numérotées")

        # avec chaque contour, on va créer un masque pour isoler la pièce
        # et on va la stocker dans une liste

        for i, cnt in enumerate(contours):
            # Créer un masque vide
            mask = np.zeros_like(masqueB)

            # Dessiner le contour sur le masque pour isoler la pièce
            cv2.drawContours(mask, contours, i, 255, -1)

            # Extraire la pièce de l'image originale
            piece = cv2.bitwise_and(masqueB, masqueB, mask=mask)

            list_widePieces_mask.append(piece)

            x, y, w, h = cv2.boundingRect(cnt)

            # Extraire la pièce de l'image originale
            piece = piece[y : y + h, x : x + w]

            list_cutPieces_mask.append(piece)

        # on applique les masques sur l'image originale img
        for i, piece in enumerate(list_widePieces_mask):
            widePiece = cv2.bitwise_and(img, img, mask=piece)
            list_widePieces.append(widePiece)

            x, y, w, h = cv2.boundingRect(contours[i])

            cutPiece = img[y : y + h, x : x + w]
            list_cutPieces.append(cutPiece)

        if (
            saveInFile(list_cutPieces_mask, "Mask/cutMask/")
            & saveInFile(list_widePieces_mask, "Mask/wideMask/")
            & saveInFile(list_cutPieces, "images/cutPieces/")
            & saveInFile(list_widePieces, "images/widePieces/")
        ):
            print("Pièces enregistrées avec succès", end="\n\n")
            return True

    else:
        print("No puzzle pieces found")
        return False


# Crée les différentes vue d'une pièce
def view_piece(
    pieceIndex,
    img=img,
    list_cutPieces=list_cutPieces,
    list_cutPieces_mask=list_cutPieces_mask,
    list_widePieces=list_widePieces,
    list_widePieces_mask=list_widePieces_mask,
):
    # partage le graphique en 4 colonnes
    fig, axs = plt.subplots(2, 2, figsize=(10, 10))
    fig.suptitle("Vertically stacked subplots")

    axs[0][0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axs[0][0].set_title("Image originale")
    axs[0][1].imshow(list_widePieces_mask[pieceIndex], cmap="gray")
    axs[0][1].set_title("Masque de la pièce")
    axs[1][0].imshow(cv2.cvtColor(list_cutPieces[pieceIndex], cv2.COLOR_BGR2RGB))
    axs[1][0].set_title("Pièce coupée")
    axs[1][1].imshow(list_cutPieces_mask[pieceIndex], cmap="gray")
    axs[1][1].set_title("Masque de la pièce coupée")

    # plt.show()
    # enregistre l'image du graphique dans un fichier
    plt.savefig("images/piece_découpe.png")

    print(
        "Vues de la pièce " + str(pieceIndex) + " enregistrée avec succès", end="\n\n"
    )
    return True


# Compte le nombre de contact entre une ligne et le contour d'une pièce
def count_line_contacts(line, contour_mask, image):
    contacts = 0
    contacts_points = []

    for point in line:
        if contour_mask[point[1], point[0]] > 0:
            contacts += 1
            contacts_points.append(point)
            cv2.circle(image, point, 2, (0, 0, 255), -1)

    return contacts, contacts_points


# Affiche les différentes vue d'une pièce avec ses infos (Protubérances, Trous)
def extract_infos_pieces():
    for pieceIndex in range(len(list_cutPieces)):
        cv2.cvtColor(list_cutPieces[pieceIndex], cv2.COLOR_BGR2RGB)

        contour, _ = cv2.findContours(
            list_cutPieces_mask[pieceIndex], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )

        cutedpiece = list_cutPieces[pieceIndex].copy()
        # Regarde si les contours ont été trouvés
        if len(contour) > 0:
            # on simplifie les contours pour avoir moins de points

            epsilon = 0.01 * cv2.arcLength(contour[0], True)
            approx = cv2.approxPolyDP(contour[0], epsilon, True)

            piece_cutWithCnt = cv2.drawContours(
                cutedpiece, [approx], -1, (255, 0, 255), 2, cv2.LINE_AA
            )

        # dessine des droitres partant de p1 {x1=18, y1=0} vers p2 {x2=4180, y2=max} avec une épaisseur de 2 pixels
        cv2.line(piece_cutWithCnt, (18, 0), (23, 1000), (0, 0, 255), 1)
        # dessine des droitres partant de p1 {x1=0, y1=23} vers p2 {x2=max, y2=23} avec une épaisseur de 2 pixels
        cv2.line(piece_cutWithCnt, (0, 23), (1000, 23), (0, 0, 255), 1)

        # dessine des droitres partant de p1 {x1=piece_cutWithCnt.shape[1]-23, y1=0} vers p2 {x2=shape[1]-23, y2=shpae[0]} avec une épaisseur de 1 pixel
        cv2.line(
            piece_cutWithCnt,
            (piece_cutWithCnt.shape[1] - 23, 0),
            (piece_cutWithCnt.shape[1] - 23, piece_cutWithCnt.shape[0]),
            (0, 0, 255),
            1,
        )
        # dessine des droitres partant de p1 {x1=0, y1=shape[0]-23} vers p2 {x2=shape[1], y2=shape[0]-23} avec une épaisseur de 1 pixel
        cv2.line(
            piece_cutWithCnt,
            (0, piece_cutWithCnt.shape[0] - 23),
            (piece_cutWithCnt.shape[1], piece_cutWithCnt.shape[0] - 23),
            (0, 0, 255),
            1,
        )

        # Récupérez le masque du contour pour faciliter la détection des contacts
        contour_mask = cv2.drawContours(
            np.zeros_like(list_cutPieces_mask[pieceIndex]), contour, -1, 255, 1
        )

        # Définissez les lignes à tracer
        lines = [
            ([(18, y) for y in range(piece_cutWithCnt.shape[0])], "Vertical 1"),
            (
                [
                    (piece_cutWithCnt.shape[1] - 23, y)
                    for y in range(piece_cutWithCnt.shape[0])
                ],
                "Vertical 2",
            ),
            ([(x, 23) for x in range(piece_cutWithCnt.shape[1])], "Horizontal 1"),
            (
                [
                    (x, piece_cutWithCnt.shape[0] - 23)
                    for x in range(piece_cutWithCnt.shape[1])
                ],
                "Horizontal 2",
            ),
        ]

        centers = []

        # Parcoure les lignes et compte les contacts avec les contours
        for line, line_name in lines:
            contacts, contacts_points = count_line_contacts(
                line, contour_mask, piece_cutWithCnt
            )
            if contacts == 4:
                # on fait la moyenne des points de contact pour trouver le centre du trou
                center = (
                    int(np.mean([point[0] for point in contacts_points])),
                    int(np.mean([point[1] for point in contacts_points])),
                )

                centers.append((center, "T"))
            elif contacts == 2:
                # on fait la différence entre les deux points pour trouver la longueur du bord
                length = int(
                    np.sqrt(
                        (contacts_points[0][0] - contacts_points[1][0]) ** 2
                        + (contacts_points[0][1] - contacts_points[1][1]) ** 2
                    )
                )
                # si elle est supérieure à 60 pixels, on considère que c'est le corps de la pièce
                if length > 60:
                    continue
                else:
                    # on fait la moyenne des points de contact pour trouver le centre du trou
                    center = (
                        int(np.mean([point[0] for point in contacts_points])),
                        int(np.mean([point[1] for point in contacts_points])),
                    )

                    centers.append((center, "P"))

            else:
                print(
                    f"{line_name} n'a pas de trou ni de protubérance, ce qui est impossible"
                )

        for center, label in centers:
            cv2.circle(piece_cutWithCnt, center, 2, (0, 255, 0), -1)
            cv2.putText(
                piece_cutWithCnt,
                label,
                (center[0] + 5, center[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 0),
                2,
            )

        list_cutPiecesWithInfos.append(piece_cutWithCnt)

    if saveInFile(list_cutPiecesWithInfos, "images/infoPieces/"):
        print("Infos des pièces enregistrées avec succès", end="\n\n")
        return True
    else:
        return False


# -------------------------------------------------------------------------------


print("Début du programme", end="\n\n")

start_full_time = time.time()

# -----------------------------------------------------------------------------#

print("-------------------- Creating binary mask... --------------------", end="\n\n")
start_time = time.time()

masqueB, isGood = createBinaryMask(img, 12, 4, 5, 10)

if isGood:
    # print icone grand format vert
    print("----- Creating binary mask..." + "\033[92m" + " - OK" + "\033[0m", end="\n")
else:
    # print icone grand format rouge
    print("----- Creating binary mask..." + "\033[91m" + " - X" + "\033[0m", end="\n")

print("Temps d execution : %s secondes ---" % (time.time() - start_time), end="\n\n")

# -----------------------------------------------------------------------------#

print("-------------------- Extracting pieces... --------------------", end="\n\n")
start_time = time.time()

if extractPieces(masqueB):
    # print icone grand format vert
    print("----- Extracting pieces..." + "\033[92m" + "- OK" + "\033[0m", end="\n")
else:
    # print icone grand format rouge
    print("----- Extracting pieces..." + "\033[91m" + "- X" + "\033[0m", end="\n")


print("Temps d execution : %s secondes ---" % (time.time() - start_time), end="\n\n")

# -----------------------------------------------------------------------------#

print("-------------------- Extracting views... --------------------", end="\n\n")
start_time = time.time()

if view_piece(7):
    # print icone grand format vert
    print("----- Extracting views..." + "\033[92m" + "- OK" + "\033[0m", end="\n")
else:
    # print icone grand format rouge
    print("----- Extracting views..." + "\033[91m" + "- X" + "\033[0m", end="\n")

print("Temps d execution : %s secondes ---" % (time.time() - start_time), end="\n\n")

# -----------------------------------------------------------------------------#

print(
    "-------------------- Extracting infos pieces... --------------------", end="\n\n"
)
start_time = time.time()

if extract_infos_pieces():
    # print icone grand format vert
    print(
        "----- Extracting infos pieces..." + "\033[92m" + "- OK" + "\033[0m", end="\n"
    )
else:
    # print icone grand format rouge
    print("----- Extracting infos pieces..." + "\033[91m" + "- X" + "\033[0m", end="\n")

print("Temps d execution : %s secondes ---" % (time.time() - start_time), end="\n\n")

# -----------------------------------------------------------------------------#

print("Fin du programme !", end="\n\n")
print("Temps d execution total : %s secondes ---" % (time.time() - start_full_time))


cv2.destroyAllWindows()
sys.exit(0)
