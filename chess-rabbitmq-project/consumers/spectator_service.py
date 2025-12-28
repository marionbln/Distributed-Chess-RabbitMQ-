r"""
spectator_service.py

Ce fichier définit l’interface spectateur du projet d’échecs distribué.

Ce service permet de
visualiser le plateau d’échecs
afficher l’évaluation Stockfish
indiquer le camp avantagé
montrer le meilleur coup recommandé
afficher une explication pédagogique générée par l’IA

Ce service est entièrement passif.
Il ne joue pas.
Il ne valide pas.
Il écoute uniquement les événements RabbitMQ.
"""

# Bibliothèque pour communiquer avec RabbitMQ
import pika

# Bibliothèque pour manipuler le format JSON
import json

# Bibliothèque python-chess pour gérer le plateau
import chess

# Bibliothèque pour créer l’interface graphique
import tkinter as tk

# Widgets Tkinter supplémentaires
from tkinter import Text, Scrollbar

# Bibliothèque pour afficher les images
from PIL import Image, ImageTk

# Accès au système de fichiers
import os


# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Exchange commun utilisé par tous les services
EXCHANGE_NAME = "chess.events"


# Dossier contenant les images PNG des pièces d’échecs
# Les images doivent respecter la notation standard
PIECES_PATH = r"C:\Users\mario\OneDrive\Images\cburnett"


# Taille d’une case du plateau en pixels
SQUARE_SIZE = 64


# Plateau local du spectateur
# Il est synchronisé avec les coups validés
board = chess.Board()

# Dictionnaire contenant les images des pièces
piece_images = {}


# Dernière évaluation reçue
current_score = 0.0

# Dernier meilleur coup recommandé
best_move = "—"

# Dernière explication pédagogique
current_explanation = ""


def load_images():
    """
    Charge les images des pièces d’échecs en mémoire.

    Les images sont redimensionnées
    puis stockées dans un dictionnaire.
    """

    pieces = {
        "P": "wP.png",
        "R": "wR.png",
        "N": "wN.png",
        "B": "wB.png",
        "Q": "wQ.png",
        "K": "wK.png",
        "p": "bP.png",
        "r": "bR.png",
        "n": "bN.png",
        "b": "bB.png",
        "q": "bQ.png",
        "k": "bK.png",
    }

    for symbol, filename in pieces.items():
        path = os.path.join(PIECES_PATH, filename)

        # Ouverture de l’image
        img = Image.open(path).convert("RGBA")

        # Redimensionnement de l’image
        img = img.resize((SQUARE_SIZE - 8, SQUARE_SIZE - 8))

        # Conversion en image compatible Tkinter
        piece_images[symbol] = ImageTk.PhotoImage(img)


def draw_board():
    """
    Dessine le plateau d’échecs et les pièces.

    Cette fonction est appelée
    après chaque mise à jour de l’état du jeu.
    """

    canvas.delete("all")

    # Dessin des cases du plateau
    for row in range(8):
        for col in range(8):
            color = "#EEEED2" if (row + col) % 2 == 0 else "#769656"

            x1 = col * SQUARE_SIZE
            y1 = (7 - row) * SQUARE_SIZE
            x2 = x1 + SQUARE_SIZE
            y2 = y1 + SQUARE_SIZE

            canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=color,
                outline=color
            )

    # Dessin des pièces
    for square in chess.SQUARES:
        piece = board.piece_at(square)

        if piece:
            col = chess.square_file(square)
            row = chess.square_rank(square)

            x = col * SQUARE_SIZE + 4
            y = (7 - row) * SQUARE_SIZE + 4

            canvas.create_image(
                x,
                y,
                anchor="nw",
                image=piece_images[piece.symbol()]
            )

    # Mise à jour du panneau d’informations
    update_side_panel()


def update_side_panel():
    """
    Met à jour les informations affichées à droite du plateau.

    Affiche
    l’évaluation
    le camp avantagé
    le meilleur coup
    """

    score_label.config(text=f"Évaluation : {current_score:+.2f}")

    if current_score > 0:
        side_label.config(text="Avantage BLANC", fg="green")
    elif current_score < 0:
        side_label.config(text="Avantage NOIR", fg="red")
    else:
        side_label.config(text="Position équilibrée", fg="black")

    move_label.config(text=f"Meilleur coup : {best_move}")


def on_message(ch, method, properties, body):
    """
    Traite les événements reçus depuis RabbitMQ.

    Cette fonction met à jour
    le plateau
    l’évaluation
    l’explication pédagogique
    """

    global current_score, best_move

    event = json.loads(body)
    event_type = event.get("event_type")
    payload = event.get("payload", {})

    if event_type == "game_started":
        board.reset()
        explanation_box.delete("1.0", tk.END)
        draw_board()

    elif event_type == "move_validated":
        move = chess.Move.from_uci(payload["uci"])
        board.push(move)
        draw_board()

    elif event_type == "analysis":
        current_score = payload.get("score", 0.0)
        best_move = payload.get("best_move", "—")
        update_side_panel()

    elif event_type == "move_explained":
        explanation_box.delete("1.0", tk.END)
        explanation_box.insert(tk.END, payload.get("text", ""))

    elif event_type == "game_ended":
        side_label.config(text="Partie terminée")


def rabbitmq_loop():
    """
    Permet d’intégrer RabbitMQ à la boucle Tkinter.

    Cette fonction est appelée régulièrement
    pour traiter les événements sans bloquer l’interface.
    """

    connection.process_data_events(time_limit=0.1)
    root.after(100, rabbitmq_loop)


# Création de la fenêtre principale
root = tk.Tk()
root.title("Spectator – Échecs avec IA pédagogique")


# Cadre principal
main_frame = tk.Frame(root)
main_frame.pack()


# Zone de dessin du plateau
canvas = tk.Canvas(
    main_frame,
    width=8 * SQUARE_SIZE,
    height=8 * SQUARE_SIZE,
    highlightthickness=2,
    highlightbackground="#333333"
)
canvas.pack(side="left")


# Panneau d’informations à droite
info_frame = tk.Frame(main_frame, padx=20)
info_frame.pack(side="right", fill="y")


# Titres et labels
tk.Label(info_frame, text="Analyse", font=("Arial", 18, "bold")).pack(pady=10)

score_label = tk.Label(info_frame, font=("Arial", 16, "bold"))
score_label.pack(pady=5)

side_label = tk.Label(info_frame, font=("Arial", 14))
side_label.pack(pady=5)

move_label = tk.Label(info_frame, font=("Arial", 12, "italic"))
move_label.pack(pady=10)

tk.Label(
    info_frame,
    text="Explication IA",
    font=("Arial", 14, "bold")
).pack(pady=5)


# Zone de texte pour l’explication
scrollbar = Scrollbar(info_frame)
scrollbar.pack(side="right", fill="y")

explanation_box = Text(
    info_frame,
    wrap="word",
    height=10,
    width=45,
    yscrollcommand=scrollbar.set,
    font=("Arial", 11)
)
explanation_box.pack()

scrollbar.config(command=explanation_box.yview)


# Chargement des images et dessin initial
load_images()
draw_board()


# Connexion RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST)
)

channel = connection.channel()

channel.exchange_declare(
    exchange=EXCHANGE_NAME,
    exchange_type="fanout",
    durable=True
)

queue = channel.queue_declare(
    queue="",
    exclusive=True
).method.queue

channel.queue_bind(
    exchange=EXCHANGE_NAME,
    queue=queue
)

channel.basic_consume(
    queue=queue,
    on_message_callback=on_message,
    auto_ack=True
)


# Lancement de la boucle RabbitMQ intégrée à Tkinter
root.after(100, rabbitmq_loop)
root.mainloop()
