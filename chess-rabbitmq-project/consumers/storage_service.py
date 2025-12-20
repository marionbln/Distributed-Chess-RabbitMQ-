import pika
import json

game_moves = []

def callback(ch, method, properties, body):
    message = json.loads(body)
    event_type = message["event_type"]
    game_id = message["game_id"]

    if event_type == "move_played":
        move = message["payload"]
        game_moves.append(
            f"{move['player']}: {move['from']} -> {move['to']}"
        )

    elif event_type == "game_ended":
        filename = f"{game_id}.txt"
        with open(filename, "w") as f:
            for m in game_moves:
                f.write(m + "\n")
        print(f"[STORAGE] Partie enregistrée dans {filename}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost")
)
channel = connection.channel()

channel.queue_declare(queue="storage.queue", durable=True)

print("Service d'enregistrement en attente de messages...")

channel.basic_consume(
    queue="storage.queue",
    on_message_callback=callback
)

channel.start_consuming()
