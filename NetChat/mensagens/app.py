from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room
import base64
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'segredo'
socketio = SocketIO(app, cors_allowed_origins='*')

# Diretório de stickers
STICKER_DIR = os.path.join(app.static_folder, "stickers")

# Histórico por sala
historico = {}

# ---------------------------------------------------------
# ROTAS
# ---------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat")
def room_select():
    return render_template("room.html")


@app.route("/chat/<sala>")
def chat(sala):
    username = request.args.get("username", "anon")
    return render_template("chat.html", channel=sala, username=username)


@app.route("/stickers")
def listar_stickers():
    """Lista as figurinhas existentes."""
    if not os.path.isdir(STICKER_DIR):
        return jsonify([])

    arquivos = []
    for file in os.listdir(STICKER_DIR):
        if file.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            arquivos.append("/static/stickers/" + file)

    return jsonify(arquivos)


@app.route("/upload", methods=["POST"])
def upload_file():
    """Envio de arquivos comuns (PDF, ZIP, PNG etc.)"""
    sala = request.form.get("room")
    username = request.form.get("username")
    f = request.files.get("file")

    if not f:
        return "Nenhum arquivo enviado."

    # garante que a sala existe
    if sala not in historico:
        historico[sala] = []

    data = f.read()
    base64_file = "data:application/octet-stream;base64," + base64.b64encode(data).decode()

    mensagem = {
        "type": "file",
        "username": username,
        "filename": f.filename,
        "base64": base64_file
    }

    historico[sala].append(mensagem)
    socketio.emit("mensagem", mensagem, room=sala)
    return "ok"


# ---------------------------------------------------------
# WEBSOCKET
# ---------------------------------------------------------

@socketio.on("join")
def entrar(data):
    sala = data["sala"]
    username = data["username"]

    join_room(sala)

    # cria histórico se não existir
    if sala not in historico:
        historico[sala] = []

    # envia histórico apenas para o novo usuário
    socketio.emit("history", historico[sala], room=request.sid)

    msg = {"type": "sys", "text": f"{username} entrou na sala."}
    historico[sala].append(msg)
    socketio.emit("mensagem", msg, room=sala)


@socketio.on("mensagem")
def receber_mensagem(data):
    sala = data["sala"]

    # garante que a sala existe
    if sala not in historico:
        historico[sala] = []

    # ----- comando !torre -----
    if data.get("text") == "!torre":
        # limpa histórico
        if sala in historico:
            historico[sala].clear()

        # avisa a sala inteira
        socketio.emit("system_command", {
            "cmd": "!torre",
            "msg": "A torre ruiu. Você foi desconectado."
        }, room=sala)

        # força desconexão de todos os SIDs
        for sid in list(socketio.server.manager.rooms.get(sala, {})):
            try:
                socketio.server.disconnect(sid)
            except:
                pass

        return

    # ----- sticker -----
    if data.get("type") == "sticker":
        mensagem = {
            "type": "sticker",
            "username": data["username"],
            "base64": data["base64"]
        }
        historico[sala].append(mensagem)
        socketio.emit("mensagem", mensagem, room=sala)
        return

    # ----- texto -----
    msg = {
        "type": "msg",
        "username": data["username"],
        "text": data["text"]
    }

    historico[sala].append(msg)
    socketio.emit("mensagem", msg, room=sala)


# ---------------------------------------------------------
# EXECUTAR
# ---------------------------------------------------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
