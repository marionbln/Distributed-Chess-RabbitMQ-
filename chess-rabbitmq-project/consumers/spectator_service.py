"""
spectator_service.py

Service spectateur pour le projet d’échecs distribué avec RabbitMQ.

Rôle :
- Afficher graphiquement la partie en cours
- Rejouer les coups validés
- Montrer la position actuelle du plateau

Ce service ne décide jamais des coups.
Il se contente d’afficher l’état du jeu.
"""

import pika
import json
import chess
import matplotlib.pyplot as plt
import time
import sys

# Message de démarrage
print("spectator_service démarré")

# Configuration RabbitMQ
RABBITMQ_HOST = "localhost"
EXCHANGE_NAME = "chess.events"
QUEUE_NAME = "spectator_service"

# Plateau local pour l'affichage
board = chess.Board()

# Initialisation de l'affichage graphique
plt.ion()
fig, ax = plt.subplots(figsize=(6, 6))

# Symboles des pièces
PIECE_SYMBOLS = {
    "P": "P", "R": "R", "N": "N", "B": "B", "Q": "Q", "K": "K",
    "p": "p", "r": "r", "n": "n", "b": "b", "q": "q", "k": "k",
}


def draw_board():
    """
    Dessine le plateau et les pièces.
    """
    ax.clear()

    # Dessin des cases
    for x in range(8):
        for y in range(8):
            color = "#f0d9b5" if (x + y) % 2 == 0 else "#b58863"
            ax.add_patch(plt.Rectangle((x, y), 1, 1, color=color))

    # Dessin des pièces
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            x = chess.square_file(square)
            y = chess.square_rank(square)
            ax.text(
                x + 0.5,
                y + 0.5,
                PIECE_SYMBOLS[piece.symbol()],
                fontsize=24,
                ha="center",
                va="center",
                fontweight="bold",
                color="white" if piece.color == chess.WHITE else "black"
            )

    ax.set_xlim(0, 8)
    ax.set_ylim(0, 8)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Spectateur - Partie en cours")

    plt.draw()
    plt.pause(0.01)


def on_message(ch, method, properties, body):
    """
    Traite les messages reçus depuis RabbitMQ.
    """
    global board

    try:
        event = json.loads(body)
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        # Nouvelle partie
        if event_type == "game_started":
            print("Nouvelle partie")
            board.reset()
            draw_board()

        # Coup validé
        elif event_type == "move_validated":
            uci = payload["uci"]
            move = chess.Move.from_uci(uci)

            if move in board.legal_moves:
                board.push(move)
                print("Coup joué :", uci)
                draw_board()
            else:
                print("Coup illégal ignoré :", uci)

        # Fin de partie
        elif event_type == "game_ended":
            print("Fin de partie :", payload.get("result"))
            draw_board()

    except Exception as e:
        print("Erreur spectator :", e)


def main():
    """
    Point d'entrée principal du service spectateur.
    Le service reste bloqué en attente des événements.
    """
    print("Spectator prêt")

    while True:
        try:
            # Connexion à RabbitMQ
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )

            channel = connection.channel()

            # Déclaration de l'exchange
            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="fanout",
                durable=True
            )

            # Déclaration et liaison de la queue
            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True
            )

            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=QUEUE_NAME
            )

            # Abonnement aux messages
            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=on_message,
                auto_ack=True
            )

            draw_board()
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print("RabbitMQ indisponible :", e)
            time.sleep(5)

        except KeyboardInterrupt:
            print("Arrêt du service spectateur")
            sys.exit(0)


if __name__ == "__main__":
    main()
