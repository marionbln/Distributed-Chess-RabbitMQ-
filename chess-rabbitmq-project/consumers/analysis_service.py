"""
analysis_service.py

Service d'analyse pour le projet d'échecs distribué utilisant RabbitMQ.

Rôle du service :
- Rejouer la partie à partir des coups validés
- Maintenir un plateau local uniquement pour l'analyse
- Analyser chaque position avec le moteur Stockfish
- Afficher une analyse claire et lisible :
  - Avantage BLANC ou NOIR
  - Importance de l'avantage (en pions)
  - Détection des positions équilibrées
  - Annonce d'un mat forcé si présent

Ce service ne décide jamais des coups et ne modifie pas la partie officielle.
Il écoute uniquement les événements diffusés sur RabbitMQ.
"""

import pika
import json
import chess
import chess.engine

# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Nom de l'exchange utilisé pour les événements
EXCHANGE_NAME = "chess.events"

# Chemin complet vers l'exécutable Stockfish
STOCKFISH_PATH = r"C:\Users\mario\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"


def main():
    """
    Fonction principale du service d'analyse.
    Initialise le plateau, le moteur Stockfish et la connexion RabbitMQ,
    puis attend les événements pour analyser la partie.
    """

    # Plateau local utilisé uniquement pour l'analyse
    board = chess.Board()

    # Démarrage du moteur Stockfish
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    # Connexion au serveur RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )

    # Création du canal de communication
    channel = connection.channel()

    # Déclaration de l'exchange commun
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="fanout",
        durable=True
    )

    # Création d'une queue temporaire propre à ce service
    queue = channel.queue_declare(queue="", exclusive=True).method.queue

    # Liaison de la queue à l'exchange
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=queue
    )

    def on_message(ch, method, properties, body):
        """
        Fonction appelée automatiquement à chaque message reçu depuis RabbitMQ.
        Analyse la position après chaque coup validé.
        """

        # Décodage du message JSON
        event = json.loads(body)
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        # Début d'une nouvelle partie
        if event_type == "game_started":
            board.reset()
            print("Nouvelle partie à analyser")
            return

        # Coup validé par la validation
        if event_type == "move_validated":
            move = chess.Move.from_uci(payload["uci"])
            board.push(move)

            # Analyse de la position actuelle
            info = engine.analyse(
                board,
                chess.engine.Limit(depth=12)
            )

            # Récupération du score relatif
            score = info["score"].relative

            # Cas d'un mat forcé
            if score.is_mate():
                mate_in = score.mate()
                if mate_in > 0:
                    print("Mat forcé pour BLANC en", mate_in, "coups")
                else:
                    print("Mat forcé pour NOIR en", abs(mate_in), "coups")
                return

            # Score en centipawns
            cp = score.score()

            # Conversion en pions
            pions = abs(cp) / 100

            # Interprétation humaine du score
            if abs(cp) < 20:
                print("Position équilibrée")

            elif cp > 0:
                print(f"Avantage BLANC : {pions:.2f} pion(s)")

            else:
                print(f"Avantage NOIR : {pions:.2f} pion(s)")

        # Fin de partie
        if event_type == "game_ended":
            print("Fin de partie :", payload.get("result"))

    # Abonnement de la queue à la fonction de traitement
    channel.basic_consume(
        queue=queue,
        on_message_callback=on_message,
        auto_ack=True
    )

    # Lancement de l'écoute des messages
    print("Analysis service prêt, en attente des événements")
    channel.start_consuming()


# Point d'entrée du programme
if __name__ == "__main__":
    main()
