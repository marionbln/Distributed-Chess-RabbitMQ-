"""
Service d'analyse pour la plateforme d'échecs distribuée.

Ce service consomme les événements envoyés via RabbitMQ et
simule une analyse de position après chaque coup joué.
Il permet d'illustrer qu'un consommateur lent n'impacte pas
le déroulement global du système.

Rôle :
- Simuler un traitement coûteux en temps
- Illustrer la communication asynchrone
- Démontrer l'indépendance des consommateurs
"""

import pika
import json
import time


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

    # Traitement uniquement des coups joués
    if event_type == "move_played":
        move = message["payload"]

        print(
            f"[ANALYSIS] Analyse du coup "
            f"{move['from']} -> {move['to']}..."
        )

        # Simulation d'un calcul long
        time.sleep(3)

        print("[ANALYSIS] Analyse terminée")

    # Acquittement du message après traitement
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """
    Point d'entrée du service d'analyse.

    Initialise la connexion à RabbitMQ, déclare la queue
    et démarre la consommation des messages.
    """

    # Connexion au broker RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )
    channel = connection.channel()

    # Déclaration de la queue dédiée au service d'analyse
    channel.queue_declare(
        queue="analysis.queue",
        durable=True
    )

    print("Service d'analyse en attente de messages...")

    # Inscription du callback
    channel.basic_consume(
        queue="analysis.queue",
        on_message_callback=callback
    )

    # Lancement de la boucle de consommation
    channel.start_consuming()


if __name__ == "__main__":
    main()
