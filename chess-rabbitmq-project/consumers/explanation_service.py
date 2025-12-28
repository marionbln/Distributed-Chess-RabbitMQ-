r"""
explanation_service.py

Ce fichier définit le service d’explication pédagogique des coups d’échecs.

Ce service écoute
les coups validés
les analyses Stockfish

À partir de ces informations,
il génère un court texte explicatif
destiné à un spectateur humain.

Ce service est passif.
Il ne joue pas.
Il ne valide pas.
Il produit uniquement du texte explicatif.
"""

# Bibliothèque pour communiquer avec RabbitMQ
import pika

# Bibliothèque pour manipuler le format JSON
import json

# Bibliothèque python-chess pour reconstruire le plateau
import chess

# Accès aux variables d’environnement
import os

# Client OpenAI et gestion des erreurs
from openai import OpenAI, RateLimitError, OpenAIError


# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Exchange commun à tous les services
EXCHANGE_NAME = "chess.events"


# Modèle d’IA utilisé pour générer le texte
MODEL = "gpt-4o-mini"


# Récupération de la clé OpenAI depuis les variables d’environnement
api_key = os.getenv("OPENAI_API_KEY")

# Sécurité
# Le service ne démarre pas sans clé API
if not api_key:
    raise RuntimeError(
        "La variable OPENAI_API_KEY n'est pas définie"
    )

# Création du client OpenAI
client = OpenAI(api_key=api_key)


# Plateau local
# Il sert uniquement à reconstruire la position courante
board = chess.Board()

# Dernière analyse Stockfish reçue
# Elle sert de contexte pour l’explication
last_analysis = {
    "score": 0.0,
    "best_move": "—"
}

# Canal RabbitMQ global
channel = None


def publish(event_type, payload):
    """
    Publie un événement vers RabbitMQ.

    event_type indique le type d’événement.
    payload contient les données associées.
    """

    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key="",
        body=json.dumps({
            "event_type": event_type,
            "payload": payload
        })
    )


def call_llm(move, score, best_move, fen):
    """
    Génère une explication pédagogique via l’IA.

    move est le coup joué.
    score est l’évaluation Stockfish.
    best_move est le coup recommandé.
    fen représente la position actuelle.
    """

    # Construction du prompt pédagogique
    prompt = f"""
Tu es un professeur d'échecs pédagogue.

Position actuelle (FEN) : {fen}
Coup joué : {move}
Meilleur coup recommandé : {best_move}
Évaluation Stockfish : {score:+.2f}

Rédige un court paragraphe expliquant
si le coup est bon ou mauvais
l’idée stratégique du coup
ce que le joueur aurait dû chercher
"""

    try:
        # Appel à l’API OpenAI
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un entraîneur d'échecs expérimenté."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4
        )

        # Retour du texte généré
        return response.choices[0].message.content.strip()

    except RateLimitError:
        # Texte de secours en cas de dépassement de quota
        return (
            "Ce coup modifie l’équilibre de la position. "
            "À ce stade de la partie, il était important de "
            "terminer le développement et de sécuriser le roi. "
            "Une approche plus prudente aurait permis de conserver "
            "une meilleure coordination des pièces."
        )

    except OpenAIError:
        # Texte de secours en cas d’erreur OpenAI
        return (
            "Ce coup mérite une analyse stratégique. "
            "Il est généralement préférable ici de privilégier "
            "l’activité des pièces et d’éviter les faiblesses inutiles."
        )

    except Exception:
        # Sécurité ultime
        return (
            "Ce coup influence la dynamique de la position. "
            "Une réflexion plus approfondie sur le plan général "
            "aurait été bénéfique à ce moment de la partie."
        )


def on_message(ch, method, properties, body):
    """
    Traite les événements reçus depuis RabbitMQ.

    Cette fonction
    met à jour le plateau local
    mémorise la dernière analyse
    génère l’explication après chaque coup validé
    """

    global last_analysis

    # Décodage du message JSON
    event = json.loads(body)

    # Lecture du type d’événement
    event_type = event.get("event_type")

    # Lecture des données associées
    payload = event.get("payload", {})

    # Début d’une nouvelle partie
    if event_type == "game_started":
        board.reset()

    # Réception d’une analyse Stockfish
    elif event_type == "analysis":
        last_analysis["score"] = payload.get("score", 0.0)
        last_analysis["best_move"] = payload.get("best_move", "—")

    # Coup validé
    elif event_type == "move_validated":
        move = chess.Move.from_uci(payload["uci"])
        board.push(move)

        # Génération du texte explicatif
        explanation = call_llm(
            payload["uci"],
            last_analysis["score"],
            last_analysis["best_move"],
            board.fen()
        )

        # Diffusion de l’explication
        publish(
            "move_explained",
            {
                "uci": payload["uci"],
                "text": explanation
            }
        )


def main():
    """
    Point d’entrée principal du service d’explication.

    Cette fonction
    initialise RabbitMQ
    s’abonne aux événements
    démarre l’écoute
    """

    global channel

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

    print("Explanation service prêt")

    # Démarrage de la boucle d’écoute
    channel.start_consuming()


# Point d’entrée du script
if __name__ == "__main__":
    main()
