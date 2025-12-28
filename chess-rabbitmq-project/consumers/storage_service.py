"""
analysis_service.py

Service d'analyse pour le projet d'échecs distribué utilisant RabbitMQ.

Objectif général :
Ce service permet d'analyser une partie d'échecs en cours à partir des
coups reçus via RabbitMQ. Il utilise le moteur Stockfish pour fournir
une évaluation de la position après chaque coup.

Rôles détaillés :
- Maintenir un plateau local indépendant
- Rejouer les coups reçus dans l'ordre
- Analyser chaque position avec Stockfish
- Afficher l'évaluation de la position

Contraintes :
- Ce service ne décide jamais des coups
- Il ne valide rien
- Il ne modifie pas la partie officielle
- Il écoute uniquement les événements diffusés
"""

import pika
import json
import chess
import chess.engine

# Adresse du serveur RabbitMQ
RABBITMQ_HOST = "localhost"

# Nom de l'exchange RabbitMQ utilisé pour la diffusion des événements
EXCHANGE_NAME = "chess.events"

# Chemin complet vers l'exécutable Stockfish
STOCKFISH_PATH = r"C:\Users\mario\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"


def main():
    """
    Fonction principale du service d'analyse.

    Elle effectue les opérations suivantes :
    - Initialise le plateau d'échecs local
    - Lance le moteur Stockfish
    - Se connecte à RabbitMQ
    - S'abonne aux événements de la partie
    - Analyse chaque coup reçu
    """

    # Plateau local utilisé uniquement pour l'analyse
    # Il ne correspond pas au plateau officiel de la validation
    board = chess.Board()

    # Démarrage du moteur Stockfish via l'interface UCI
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    # Connexion au serveur RabbitMQ
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )

    # Création d'un canal de communication RabbitMQ
    channel = connection.channel()

    # Déclaration de l'exchange commun à tous les services
    # Le type fanout permet de diffuser chaque message à tous les consommateurs
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="fanout",
        durable=True
    )

    # Création d'une queue temporaire spécifique à ce service
    # Elle sera supprimée automatiquement à l'arrêt du service
    queue = channel.queue_declare(queue="", exclusive=True).method.queue

    # Liaison de la queue à l'exchange
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=queue
    )

    def on_message(ch, method, properties, body):
        """
        Fonction appelée automatiquement à chaque message reçu depuis RabbitMQ.

        Paramètres :
        - ch : canal RabbitMQ
        - method : informations de routage
        - properties : propriétés du message
        - body : contenu du message (JSON)
        """

        # Conversion du message JSON en dictionnaire Python
        event = json.loads(body)

        # Récupération du type d'événement
        event_type = event.get("event_type")

        # Récupération des données associées à l'événement
        payload = event.get("payload", {})

        # Réinitialisation du plateau lors d'une nouvelle partie
        if event_type == "game_started":
            board.reset()
            print("Nouvelle partie reçue pour analyse")
            return

        # Traitement d'un coup joué
        if event_type == "move_played":
            # Conversion du coup UCI en objet Move
            move = chess.Move.from_uci(payload["uci"])

            # Application du coup sur le plateau local
            board.push(move)

            # Analyse de la position actuelle par Stockfish
            info = engine.analyse(
                board,
                chess.engine.Limit(depth=10)
            )

            # Récupération du score relatif (du point de vue du joueur au trait)
            score = info["score"].relative

            # Affichage du résultat de l'analyse
            if score.is_mate():
                print("Mat en", score.mate())
            else:
                print("Evaluation :", score.score())

    # Abonnement de la queue à la fonction de traitement
    channel.basic_consume(
        queue=queue,
        on_message_callback=on_message,
        auto_ack=True
    )

    # Lancement de l'écoute des messages RabbitMQ
    print("Analysis service prêt, en attente des événements")
    channel.start_consuming()


# Point d'entrée du programme
if __name__ == "__main__":
    main()
