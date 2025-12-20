"""
Producteur d'événements pour la plateforme d'échecs distribuée.

Ce programme joue le rôle de moteur de partie d'échecs.
Il publie les événements de jeu (début de partie, coups joués, fin de partie)
dans RabbitMQ sans dépendre des services consommateurs.

Rôle :
- Générer les événements de la partie
- Publier les messages de manière asynchrone
- Illustrer le découplage producteur / consommateurs
"""

import pika
import json
import time
from datetime import datetime, timezone


def publish_event(channel, game_id, event_type, payload):
    """
    Publie un événement sur l'exchange RabbitMQ.

    Paramètres :
    - channel : canal RabbitMQ utilisé pour la publication
    - game_id : identifiant unique de la partie
    - event_type : type de l'événement (game_started, move_played, game_ended)
    - payload : données spécifiques à l'événement
    """

    message = {
        "event_type": event_type,
        "game_id": game_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }

    channel.basic_publish(
        exchange="chess.events",
        routing_key="",
        body=json.dumps(message)
    )

    print(f"[PRODUCER] Événement envoyé : {message}")


def main():
    """
    Point d'entrée du producteur.

    Initialise la connexion à RabbitMQ, déclare l'exchange
    et simule le déroulement d'une partie d'échecs.
    """

    # Connexion à RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )
    channel = connection.channel()

    # Déclaration de l'exchange (fanout)
    channel.exchange_declare(
        exchange="chess.events",
        exchange_type="fanout",
        durable=True
    )

    game_id = "game_123"

    # Début de partie
    publish_event(
        channel,
        game_id,
        "game_started",
        {
            "white": "Alice",
            "black": "Bob"
        }
    )

    # Liste de coups simulés
    moves = [
        ("e2", "e4", "white"),
        ("e7", "e5", "black"),
        ("g1", "f3", "white"),
        ("b8", "c6", "black")
    ]

    # Publication des coups
    for from_sq, to_sq, player in moves:
        time.sleep(1)
        publish_event(
            channel,
            game_id,
            "move_played",
            {
                "from": from_sq,
                "to": to_sq,
                "player": player
            }
        )

    # Fin de partie
    publish_event(
        channel,
        game_id,
        "game_ended",
        {
            "result": "1-0"
        }
    )

    # Fermeture de la connexion
    connection.close()


if __name__ == "__main__":
    main()
