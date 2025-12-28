r"""
storage_service.py

Ce fichier définit le service de stockage du projet d’échecs distribué.

Ce service a pour rôle de
enregistrer les événements importants de la partie
conserver l’historique des coups
permettre une persistance minimale de la partie

Ce service est passif.
Il ne joue pas.
Il ne valide pas.
Il écoute uniquement les événements diffusés via RabbitMQ.
"""

# Bibliothèque pour communiquer avec RabbitMQ
import pika

# Bibliothèque pour manipuler le format JSON
import json

# Accès au système de fichiers
import os

# Utilisé pour créer des horodatages simples
from datetime import datetime


# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Exchange commun à tous les services
EXCHANGE_NAME = "chess.events"


# Dossier de stockage des parties
# Les fichiers seront créés automatiquement
STORAGE_DIR = "games_storage"


# Création du dossier s’il n’existe pas
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)


# Fichier courant de stockage
# Un nouveau fichier est créé à chaque partie
current_file = None


def open_new_game_file():
    """
    Crée un nouveau fichier pour stocker une partie.

    Le nom du fichier contient un horodatage
    afin d’éviter les collisions.
    """

    global current_file

    # Création d’un nom de fichier unique
    filename = datetime.now().strftime(
        "game_%Y%m%d_%H%M%S.json"
    )

    # Chemin complet du fichier
    path = os.path.join(STORAGE_DIR, filename)

    # Ouverture du fichier en écriture
    current_file = open(path, "w", encoding="utf-8")

    # Initialisation du contenu
    current_file.write("[\n")


def close_game_file():
    """
    Ferme proprement le fichier de la partie.
    """

    global current_file

    if current_file:
        current_file.write("\n]\n")
        current_file.close()
        current_file = None


def store_event(event):
    """
    Écrit un événement dans le fichier de stockage.

    event est un dictionnaire Python représentant l’événement.
    """

    global current_file

    if current_file is None:
        return

    # Conversion de l’événement en JSON lisible
    json.dump(event, current_file, ensure_ascii=False, indent=2)

    # Ajout d’une virgule pour séparer les événements
    current_file.write(",\n")


def on_message(ch, method, properties, body):
    """
    Traite les événements reçus depuis RabbitMQ.

    Cette fonction décide
    quand ouvrir un fichier
    quoi stocker
    quand fermer le fichier
    """

    global current_file

    # Décodage du message JSON
    event = json.loads(body)

    # Lecture du type d’événement
    event_type = event.get("event_type")

    # Démarrage d’une nouvelle partie
    if event_type == "game_started":
        close_game_file()
        open_new_game_file()
        store_event(event)

    # Coup validé
    elif event_type == "move_validated":
        store_event(event)

    # Fin de partie
    elif event_type == "game_ended":
        store_event(event)
        close_game_file()


def main():
    """
    Point d’entrée principal du service de stockage.

    Cette fonction
    se connecte à RabbitMQ
    s’abonne aux événements
    démarre l’écoute
    """

    print("Storage service démarré")

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
        exchange=EXCHANGE_NAME, queue=queue
    )

    # Abonnement aux messages RabbitMQ
    channel.basic_consume(
        queue=queue,
        on_message_callback=on_message,
        auto_ack=True
    )

    print("Storage prêt, en attente des événements")

    # Démarrage de la boucle d’écoute
    channel.start_consuming()


# Point d’entrée du script
if __name__ == "__main__":
    main()
