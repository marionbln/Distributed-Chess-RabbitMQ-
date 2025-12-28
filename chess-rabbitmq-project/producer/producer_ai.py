r"""
producer_ai.py

Ce fichier définit le producteur de coups pour l’intelligence artificielle.

L’IA joue les pièces NOIRES.
Elle utilise le moteur Stockfish pour calculer ses coups.

Le rôle de ce service est de
maintenir un plateau local
attendre son tour de jeu
calculer un coup avec Stockfish
proposer ce coup au service de validation

Ce service ne valide jamais les coups.
Il attend toujours une confirmation officielle.
"""

# Bibliothèque pour communiquer avec RabbitMQ
import pika

# Bibliothèque pour manipuler le format JSON
import json

# Bibliothèque standard pour gérer les pauses temporelles
import time

# Bibliothèque python-chess pour gérer le plateau et les coups
import chess

# Interface avec le moteur Stockfish
import chess.engine

# Utilisé pour générer des horodatages UTC
from datetime import datetime, timezone

# Accès au système de fichiers
import os


# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Exchange commun à tous les services
EXCHANGE_NAME = "chess.events"


# Chemin vers l’exécutable Stockfish
# Le chemin doit être exact
STOCKFISH_PATH = (
    r"C:\Users\mario\Downloads\stockfish-windows-x86-64-avx2"
    r"\stockfish\stockfish-windows-x86-64-avx2.exe"
)


# Couleur jouée par l’IA
# Ici l’IA joue les NOIRS
AI_COLOR = chess.BLACK


# Plateau local de l’IA
# Il est synchronisé avec les coups validés
board = chess.Board()


# Indique si l’IA attend la validation de son coup
waiting_validation = False

# Indique si la partie est terminée
game_over = False


# Canal RabbitMQ global
channel = None


def publish(event_type, payload):
    """
    Publie un événement vers RabbitMQ.

    event_type indique le type d’événement.
    payload contient les données associées.
    """

    # Construction du message
    message = {
        # Type d’événement
        "event_type": event_type,

        # Horodatage UTC
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Données spécifiques
        "payload": payload
    }

    # Envoi du message à tous les services abonnés
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=json.dumps(message)
    )


def on_message(ch, method, properties, body):
    """
    Traite les événements reçus depuis RabbitMQ.

    Cette fonction permet de
    synchroniser le plateau local
    détecter la fin de partie
    """

    global waiting_validation, game_over

    # Décodage du message JSON
    event = json.loads(body)

    # Lecture du type d’événement
    event_type = event.get("event_type")

    # Lecture des données associées
    payload = event.get("payload", {})

    # Début d’une nouvelle partie
    if event_type == "game_started":
        board.reset()
        waiting_validation = False
        game_over = False

    # Coup validé par le service de validation
    elif event_type == "move_validated":
        move = chess.Move.from_uci(payload["uci"])
        board.push(move)

        # L’IA peut rejouer après validation
        waiting_validation = False

    # Fin de partie
    elif event_type == "game_ended":
        print("Partie terminée")
        game_over = True


def main():
    """
    Fonction principale de l’intelligence artificielle.

    Elle réalise les actions suivantes
    initialisation de Stockfish
    connexion à RabbitMQ
    écoute des événements
    calcul et proposition des coups
    """

    global channel, waiting_validation, game_over

    print("IA prête (joue les NOIRS)")

    # Vérification de la présence de Stockfish
    if not os.path.exists(STOCKFISH_PATH):
        raise FileNotFoundError(
            f"Stockfish introuvable : {STOCKFISH_PATH}"
        )

    # Lancement du moteur Stockfish
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    # Connexion au serveur RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )

    # Création du canal RabbitMQ
    channel = connection.channel()

    # Déclaration de l’exchange commun
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="fanout",
        durable=True
    )

    # Création d’une queue temporaire exclusive
    queue = channel.queue_declare(
        queue="",
        exclusive=True
    ).method.queue

    # Liaison de la queue à l’exchange
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=queue
    )

    # Abonnement aux messages RabbitMQ
    channel.basic_consume(
        queue=queue,
        on_message_callback=on_message,
        auto_ack=True
    )

    # Boucle principale de l’IA
    while not game_over:
        # Traitement non bloquant des messages RabbitMQ
        connection.process_data_events(time_limit=0.1)

        # Attente de la validation du coup précédent
        if waiting_validation:
            time.sleep(0.1)
            continue

        # L’IA ne joue que lorsque c’est son tour
        if board.turn != AI_COLOR:
            time.sleep(0.1)
            continue

        # Calcul du meilleur coup avec Stockfish
        result = engine.play(
            board,
            chess.engine.Limit(time=0.7)
        )

        # Récupération du coup calculé
        move = result.move

        # Envoi du coup proposé
        publish("move_proposed", {"uci": move.uci()})

        # L’IA attend la validation officielle
        waiting_validation = True

    # Fermeture propre du moteur Stockfish
    engine.quit()


# Point d’entrée du script
if __name__ == "__main__":
    main()
