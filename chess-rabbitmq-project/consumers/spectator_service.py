"""
Service spectateur pour la plateforme d'échecs distribuée.

Ce service consomme tous les événements envoyés via RabbitMQ
et les affiche en temps réel.
Il ne modifie pas les messages et ne possède aucune logique métier.

Rôle :
- Illustrer l'ajout dynamique d'un consommateur
- Montrer le découplage total avec le producteur
- Fournir une visualisation simple du déroulement de la partie
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

    # Décodage du message
    message = json.loads(body)

    # Affichage de l'événement reçu
    print(f"[SPECTATOR] {message}")

    # Acquittement du message après affichage
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """
    Point d'entrée du service spectateur.

    Initialise la connexion à RabbitMQ, déclare la queue
    et démarre la consommation des événements.
    """

    # Connexion au broker RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )
    channel = connection.channel()

    # Déclaration de la queue dédiée au service spectateur
    channel.queue_declare(
        queue="spectator.queue",
        durable=True
    )

    print("Service spectateur connecté et en attente de messages...")

    # Inscription du callback
    channel.basic_consume(
        queue="spectator.queue",
        on_message_callback=callback
    )

    # Lancement de la boucle de consommation
    channel.start_consuming()


if __name__ == "__main__":
    main()
