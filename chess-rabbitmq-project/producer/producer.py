"""
producer.py

Service producteur pour le projet d’échecs distribué avec RabbitMQ.

Rôle du service :
- Utiliser Stockfish pour calculer les coups
- Proposer les coups au service de validation
- Attendre la validation avant de proposer un nouveau coup
- Arrêter la partie lorsque la validation annonce la fin

Ce service ne décide jamais de la légalité des coups.
Il propose uniquement des coups et attend la réponse de la validation.
"""

import pika
import json
import time
import chess
import chess.engine
from datetime import datetime, timezone

# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Nom de l'exchange utilisé pour les événements
EXCHANGE_NAME = "chess.events"

# Chemin complet vers l'exécutable Stockfish
STOCKFISH_PATH = r"C:\Users\mario\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"

# Plateau local utilisé uniquement pour proposer les coups
board = chess.Board()

# Indique si la partie est terminée
game_over = False

# Indique si le producer attend une validation
waiting_validation = False


def publish(channel, event_type, payload):
    """
    Publie un événement sur RabbitMQ.

    Paramètres :
    - channel : canal RabbitMQ
    - event_type : type d'événement
    - payload : données associées à l'événement
    """

    message = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }

    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=json.dumps(message)
    )


def on_message(ch, method, properties, body):
    """
    Traite les messages reçus depuis RabbitMQ.

    Paramètres :
    - ch : canal RabbitMQ
    - method : informations de routage
    - properties : propriétés du message
    - body : message reçu (JSON)
    """

    global game_over, waiting_validation

    # Décodage du message JSON
    event = json.loads(body)
    event_type = event.get("event_type")
    payload = event.get("payload", {})

    # Coup validé par la validation
    if event_type == "move_validated":
        move = chess.Move.from_uci(payload["uci"])
        board.push(move)

        # La validation a répondu, on peut proposer un nouveau coup
        waiting_validation = False

    # Fin de partie annoncée par la validation
    elif event_type == "game_ended":
        print("Partie terminée :", payload.get("result"))
        game_over = True


def main():
    """
    Fonction principale du service producteur.
    Initialise Stockfish, se connecte à RabbitMQ
    et propose les coups jusqu'à la fin de la partie.
    """

    global waiting_validation

    print("Producer démarré")

    # Démarrage du moteur Stockfish
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    # Configuration du moteur
    engine.configure({
        "Skill Level": 20,
        "Threads": 4,
        "Hash": 256
    })

    # Connexion à RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )

    # Création du canal de communication
    channel = connection.channel()

    # Déclaration de l'exchange commun
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="fanout",
        durable=True
    )

    # Création d'une queue temporaire pour recevoir les réponses
    queue = channel.queue_declare(queue="", exclusive=True).method.queue

    # Liaison de la queue à l'exchange
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=queue
    )

    # Abonnement aux messages
    channel.basic_consume(
        queue=queue,
        on_message_callback=on_message,
        auto_ack=True
    )

    # Démarrage d'une nouvelle partie
    publish(channel, "game_started", {})
    print("Nouvelle partie lancée")

    # Boucle principale du jeu
    while not game_over:

        # Attente de la validation du coup précédent
        if waiting_validation:
            channel.connection.process_data_events(time_limit=0.2)
            time.sleep(0.05)
            continue

        # Calcul du prochain coup par Stockfish
        result = engine.play(
            board,
            chess.engine.Limit(time=0.7)
        )

        move = result.move
        if move is None:
            break

        # Publication du coup proposé
        print("Coup proposé :", move.uci())
        publish(channel, "move_proposed", {"uci": move.uci()})

        # Blocage en attente de la validation
        waiting_validation = True

    # Arrêt du moteur et fermeture de la connexion
    engine.quit()
    connection.close()
    print("Producer arrêté")


# Point d'entrée du programme
if __name__ == "__main__":
    main()
