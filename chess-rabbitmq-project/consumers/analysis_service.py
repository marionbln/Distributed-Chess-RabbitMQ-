r"""
analysis_service.py

Ce fichier définit le service d’analyse du projet d’échecs distribué.

Ce service est passif.
Il ne joue pas.
Il ne valide pas.
Il ne modifie jamais la partie officielle.

Son rôle est uniquement de
écouter les coups validés
rejouer la partie localement
analyser chaque position avec Stockfish
diffuser une évaluation lisible de la position

Plusieurs services d’analyse peuvent fonctionner en parallèle
sans interférer avec la partie.
"""

# Bibliothèque pour communiquer avec RabbitMQ
import pika

# Bibliothèque pour manipuler le format JSON
import json

# Bibliothèque python-chess pour gérer le plateau et les coups
import chess

# Interface avec le moteur Stockfish
import chess.engine

# Accès au système de fichiers
import os


# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Exchange commun utilisé par tous les services
EXCHANGE_NAME = "chess.events"


# Chemin vers l’exécutable Stockfish
# Le chemin doit être exact pour que le moteur démarre
STOCKFISH_PATH = (
    r"C:\Users\mario\Downloads\stockfish-windows-x86-64-avx2"
    r"\stockfish\stockfish-windows-x86-64-avx2.exe"
)


# Plateau local utilisé uniquement pour l’analyse
# Il est reconstruit à partir des coups validés
board = chess.Board()

# Canal RabbitMQ global
channel = None

# Instance du moteur Stockfish
engine = None


def publish(event_type, payload):
    """
    Publie un événement d’analyse vers RabbitMQ.

    event_type décrit le type d’événement envoyé.
    payload contient les données associées à l’analyse.
    """

    # Construction du message
    message = {
        "event_type": event_type,
        "payload": payload
    }

    # Envoi du message sur l’exchange commun
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=json.dumps(message)
    )


def analyse_position():
    """
    Analyse la position actuelle du plateau local.

    Cette fonction
    demande une évaluation à Stockfish
    interprète le score
    calcule le meilleur coup
    diffuse les résultats
    """

    # Analyse de la position avec une limite de temps
    info = engine.analyse(
        board,
        chess.engine.Limit(time=0.5)
    )

    # Récupération du score retourné par Stockfish
    score = info["score"]

    # Cas particulier où un mat est détecté
    if score.is_mate():
        mate = score.mate()

        if mate > 0:
            value = 100.0
            text = f"Mat BLANC en {mate}"
        else:
            value = -100.0
            text = f"Mat NOIR en {abs(mate)}"

    else:
        # Score classique en centipawns
        value = score.white().score() / 100.0
        text = f"{value:+.2f}"

    # Calcul du meilleur coup recommandé par Stockfish
    best = engine.play(
        board,
        chess.engine.Limit(time=0.3)
    ).move.uci()

    # Diffusion de l’analyse
    publish(
        "analysis",
        {
            "score": value,
            "best_move": best,
            "text": text
        }
    )


def on_message(ch, method, properties, body):
    """
    Traite les événements reçus depuis RabbitMQ.

    Cette fonction permet de
    reconstruire la partie localement
    déclencher l’analyse après chaque coup validé
    """

    # Décodage du message JSON
    event = json.loads(body)

    # Lecture du type d’événement
    event_type = event.get("event_type")

    # Lecture des données associées
    payload = event.get("payload", {})

    # Début d’une nouvelle partie
    if event_type == "game_started":
        board.reset()

    # Coup validé par le service de validation
    elif event_type == "move_validated":
        move = chess.Move.from_uci(payload["uci"])
        board.push(move)

        # Analyse immédiate après le coup
        analyse_position()

    # Fin de partie
    elif event_type == "game_ended":
        print("Analyse terminée")


def main():
    """
    Point d’entrée principal du service d’analyse.

    Cette fonction
    vérifie la présence de Stockfish
    initialise le moteur
    se connecte à RabbitMQ
    s’abonne aux événements
    démarre l’écoute
    """

    global channel, engine

    print("Analysis service démarré")

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

    print("Analysis prête, en attente des coups")

    # Démarrage de la boucle d’écoute
    channel.start_consuming()


# Point d’entrée du script
if __name__ == "__main__":
    main()

