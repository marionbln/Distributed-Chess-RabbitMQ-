"""
validation_service.py

Service de validation pour le projet d’échecs distribué avec RabbitMQ.

Rôle du service :
- Maintenir le plateau de vérité officiel
- Vérifier la légalité des coups proposés
- Appliquer uniquement les coups légaux
- Détecter la fin de partie (échec et mat, nulle)
- Publier les événements validés

Ce service est l’arbitre officiel du système.
"""

import pika
import json
import chess
from datetime import datetime, timezone

# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Nom de l'exchange utilisé pour les événements
EXCHANGE_NAME = "chess.events"

# Plateau officiel maintenu par la validation
board = chess.Board()


def publish(channel, event_type, payload):
    """
    Publie un événement sur RabbitMQ.

    Paramètres :
    - channel : canal RabbitMQ
    - event_type : type d'événement (string)
    - payload : données associées à l'événement (dict)
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


def on_message(channel, method, properties, body):
    """
    Traite chaque message reçu depuis RabbitMQ.

    Paramètres :
    - channel : canal RabbitMQ
    - method : informations de routage
    - properties : propriétés du message
    - body : message reçu (JSON)
    """

    global board

    # Décodage du message JSON
    message = json.loads(body)
    event_type = message.get("event_type")
    payload = message.get("payload", {})

    # Début d'une nouvelle partie
    if event_type == "game_started":
        board.reset()
        print("Nouvelle partie validée")
        return

    # Coup proposé par le producer
    if event_type == "move_proposed":
        move = chess.Move.from_uci(payload["uci"])

        # Vérification de la légalité du coup
        if move not in board.legal_moves:
            print("Coup illégal ignoré :", payload["uci"])
            return

        # Application du coup sur le plateau officiel
        board.push(move)
        print("Coup validé :", payload["uci"])

        # Publication du coup validé
        publish(channel, "move_validated", {"uci": payload["uci"]})

        # Détection de l'échec et mat
        if board.is_checkmate():
            publish(channel, "game_ended", {"result": "checkmate"})

        # Détection de la nulle (pat ou répétition)
        elif board.is_stalemate() or board.can_claim_threefold_repetition():
            publish(channel, "game_ended", {"result": "draw"})


def main():
    """
    Fonction principale du service de validation.
    Initialise la connexion RabbitMQ et attend les événements.
    """

    # Connexion au serveur RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(RABBITMQ_HOST)
    )

    # Création du canal de communication
    channel = connection.channel()

    # Déclaration de l'exchange commun
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="fanout",
        durable=True
    )

    # Création d'une queue temporaire pour ce service
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

    # Démarrage du service
    print("Validation service prêt, en attente des événements")
    channel.start_consuming()


# Point d'entrée du programme
if __name__ == "__main__":
    main()
