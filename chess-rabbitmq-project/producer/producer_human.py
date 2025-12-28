r"""
producer_human.py

Ce fichier définit le producteur de coups pour un joueur humain.

Le joueur humain joue les pièces BLANCHES.
Il saisit ses coups manuellement au clavier.

Le rôle de ce service est uniquement de
envoyer les coups proposés
recevoir les coups validés
maintenir un plateau local cohérent

Ce service ne valide jamais les coups.
Ce service ne décide pas si un coup est légal.
Cette responsabilité appartient au service de validation.
"""

# Bibliothèque utilisée pour communiquer avec RabbitMQ
import pika

# Bibliothèque utilisée pour encoder et décoder le JSON
import json

# Bibliothèque python-chess pour manipuler un plateau d’échecs
import chess

# Utilisé pour générer un horodatage UTC
from datetime import datetime, timezone


# Adresse du serveur RabbitMQ
# Tous les services utilisent la même adresse
RABBITMQ_HOST = "localhost"

# Nom de l’exchange commun utilisé pour diffuser les événements
EXCHANGE_NAME = "chess.events"


# Couleur jouée par le joueur humain
# Ici le joueur joue les BLANCS
HUMAN_COLOR = chess.WHITE


# Plateau d’échecs local
# Il sert uniquement à savoir quand le joueur peut jouer
# et à vérifier la légalité locale des coups
board = chess.Board()

# Canal RabbitMQ
# Il sera initialisé dans la fonction main
channel = None


def publish(event_type, payload):
    """
    Envoie un événement sur RabbitMQ.

    event_type décrit le type d’événement envoyé.
    payload contient les données associées à l’événement.

    Cette fonction est utilisée pour
    démarrer une partie
    proposer un coup
    """

    # Construction du message sous forme de dictionnaire Python
    message = {
        # Type de l’événement
        "event_type": event_type,

        # Horodatage UTC au format ISO 8601
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Données spécifiques à l’événement
        "payload": payload
    }

    # Publication du message sur l’exchange RabbitMQ
    # Le fanout diffuse le message à tous les services abonnés
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=json.dumps(message)
    )


def on_message(ch, method, properties, body):
    """
    Fonction appelée automatiquement à chaque message reçu.

    Elle permet de maintenir le plateau local synchronisé
    avec la partie officielle validée.
    """

    # Décodage du message JSON reçu
    event = json.loads(body)

    # Lecture du type d’événement
    event_type = event.get("event_type")

    # Lecture des données associées à l’événement
    payload = event.get("payload", {})

    # Début d’une nouvelle partie
    # Le plateau local est réinitialisé
    if event_type == "game_started":
        board.reset()

    # Coup validé par le service de validation
    # Le coup est appliqué sur le plateau local
    elif event_type == "move_validated":
        move = chess.Move.from_uci(payload["uci"])
        board.push(move)

    # Fin de partie
    # Le programme s’arrête proprement
    elif event_type == "game_ended":
        print("Partie terminée")
        exit(0)


def main():
    """
    Fonction principale du joueur humain.

    Elle réalise les actions suivantes
    connexion à RabbitMQ
    abonnement aux événements
    initialisation de la partie
    saisie des coups au clavier
    """

    # Le canal RabbitMQ est global
    global channel

    # Messages affichés pour l’utilisateur
    print("Joueur humain prêt (BLANCS)")
    print("Entre les coups au format UCI (ex: e2e4)")

    # Connexion au serveur RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )

    # Création du canal de communication RabbitMQ
    channel = connection.channel()

    # Déclaration de l’exchange commun
    # fanout signifie diffusion vers tous les consommateurs
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="fanout",
        durable=True
    )

    # Création d’une queue temporaire exclusive
    # Elle sera supprimée automatiquement à la fermeture du service
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

    # Envoi de l’événement de démarrage de partie
    publish("game_started", {})

    # Boucle principale du programme
    while True:
        # Traitement non bloquant des événements RabbitMQ
        connection.process_data_events(time_limit=0.1)

        # Le joueur peut jouer uniquement si c’est son tour
        if board.turn == HUMAN_COLOR:

            # Lecture du coup entré par l’utilisateur
            move_uci = input("Ton coup : ").strip()

            # Vérification du format UCI
            try:
                move = chess.Move.from_uci(move_uci)
            except ValueError:
                print("Format invalide")
                continue

            # Vérification de la légalité du coup
            if move not in board.legal_moves:
                print("Coup illégal")
                continue

            # Envoi du coup proposé au service de validation
            publish("move_proposed", {"uci": move_uci})


# Point d’entrée du script
if __name__ == "__main__":
    main()
