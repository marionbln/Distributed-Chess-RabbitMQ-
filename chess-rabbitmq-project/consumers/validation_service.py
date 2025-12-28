r"""
validation_service.py

Ce fichier définit le service de validation du projet d’échecs distribué.

Ce service est l’autorité centrale de la partie.
Il est le seul à décider si un coup est légal ou non.

Rôle du service
recevoir les coups proposés
vérifier leur légalité
mettre à jour le plateau officiel
diffuser les coups validés
détecter la fin de la partie

Tous les autres services sont passifs
ils écoutent uniquement les événements diffusés.
"""

# Bibliothèque pour communiquer avec RabbitMQ
import pika

# Bibliothèque pour manipuler le format JSON
import json

# Bibliothèque python-chess pour gérer le plateau et la légalité des coups
import chess


# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Nom de l’exchange commun à tous les services
EXCHANGE_NAME = "chess.events"


# Plateau officiel de la partie
# Ce plateau est la référence unique de l’état du jeu
board = chess.Board()

# Canal RabbitMQ global
# Il est utilisé dans le callback
channel = None


def publish(channel, event_type, payload):
    """
    Publie un événement vers RabbitMQ.

    channel est le canal RabbitMQ utilisé.
    event_type décrit le type d’événement.
    payload contient les données associées.
    """

    # Construction du message
    message = {
        # Type d’événement
        "event_type": event_type,

        # Données spécifiques à l’événement
        "payload": payload
    }

    # Envoi du message sur l’exchange
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=json.dumps(message)
    )


def on_message(ch, method, properties, body):
    """
    Traite les événements reçus depuis RabbitMQ.

    Cette fonction est appelée automatiquement
    à chaque message reçu.
    """

    global board

    # Décodage du message JSON
    event = json.loads(body)

    # Lecture du type d’événement
    event_type = event.get("event_type")

    # Lecture des données associées
    payload = event.get("payload", {})

    # Réception d’un coup proposé par un joueur
    if event_type == "move_proposed":

        # Lecture du coup au format UCI
        uci = payload.get("uci")

        # Tentative de création du coup
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            # Format de coup invalide
            print("Coup invalide (format) :", uci)
            return

        # Vérification de la légalité du coup
        if move in board.legal_moves:

            # Application du coup sur le plateau officiel
            board.push(move)

            print("Coup validé :", uci)

            # Diffusion du coup validé
            publish(channel, "move_validated", {"uci": uci})

            # Vérification de la fin de partie
            if board.is_game_over():

                # Récupération du résultat officiel
                result = board.result()

                # Diffusion de l’événement de fin de partie
                publish(channel, "game_ended", {"result": result})

                print("Partie terminée :", result)

        else:
            # Coup illégal selon les règles des échecs
            print("Coup illégal :", uci)


def main():
    """
    Point d’entrée du service de validation.

    Cette fonction
    initialise RabbitMQ
    s’abonne aux événements
    lance la boucle d’écoute
    """

    global channel

    print("Validation service démarré")

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

    print("Validation prête, en attente des coups")

    # Démarrage de la boucle d’écoute
    channel.start_consuming()


# Point d’entrée du script
if __name__ == "__main__":
    main()
