"""
Service de validation des coups pour la plateforme d'échecs distribuée.

Ce service consomme les événements envoyés via RabbitMQ et vérifie
la cohérence des coups joués.
Il illustre un consommateur simple, rapide et indépendant.

Rôle :
- Vérifier les coups joués
- Filtrer les événements non pertinents
- Illustrer le découplage producteur / consommateurs
"""

import pika
import json


def callback(ch, method, properties, body):
    """
    Fonction appelée à la réception d'un message.

    Paramètres :
    - ch : canal RabbitMQ
    - method : informations de livraison (pour l'ACK)
    - properties : propriétés du message (non utilisées)
    - body : contenu du message (JSON)
    """

    # Décodage du message JSON
    message = json.loads(body)
    event_type = message["event_type"]

    # Traitement des coups joués
    if event_type == "move_played":
        move = message["payload"]

        print(
            f"[VALIDATION] Coup reçu : "
            f"{move['from']} -> {move['to']} ({move['player']})"
        )

    # Autres événements ignorés
    else:
        print(f"[VALIDATION] Événement ignoré : {event_type}")

    # Acquittement du message après traitement
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """
    Point d'entrée du service de validation.

    Initialise la connexion à RabbitMQ, déclare la queue
    et démarre la consommation des messages.
    """

    # Connexion au broker RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )
    channel = connection.channel()

    # Déclaration de la queue dédiée au service de validation
    channel.queue_declare(
        queue="validation.queue",
        durable=True
    )

    print("Service de validation en attente de messages...")

    # Inscription du callback
    channel.basic_consume(
        queue="validation.queue",
        on_message_callback=callback
    )

    # Lancement de la boucle de consommation
    channel.start_consuming()


if __name__ == "__main__":
    main()
