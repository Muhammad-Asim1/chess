import socket
import threading
import json
import chess
import time

class ChessGame:
    def __init__(self, white_player, black_player):
        self.board = chess.Board()
        self.white_player = white_player
        self.black_player = black_player
        self.current_player = white_player
        self.spectators = []
        self.game_over = False
        self.chat_messages = []
        self.time_limit = 600  # 10 minutes per player
        self.white_time = self.time_limit
        self.black_time = self.time_limit
        self.last_move_time = time.time()

    def make_move(self, move_uci):
        try:
            move = chess.Move.from_uci(move_uci)
            if move in self.board.legal_moves:
                self.board.push(move)
                self.current_player = self.black_player if self.current_player == self.white_player else self.white_player
                self.last_move_time = time.time()
                return True
            return False
        except:
            return False

    def get_game_state(self):
        return {
            'fen': self.board.fen(),
            'current_player': 'white' if self.current_player == self.white_player else 'black',
            'is_check': self.board.is_check(),
            'is_checkmate': self.board.is_checkmate(),
            'is_stalemate': self.board.is_stalemate(),
            'white_time': self.white_time,
            'black_time': self.black_time
        }

class ChessServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(10)
        self.games = {}
        self.waiting_players = []
        self.clients = {}
        self.max_games = 2  # Maximum number of concurrent games allowed
        print(f"Server started on {host}:{port}")

    def get_active_game_count(self):
        # Count unique games (each game appears twice in self.games, once for each player)
        unique_games = set()
        for game in self.games.values():
            unique_games.add(id(game))
        return len(unique_games)

    def start(self):
        while True:
            client_socket, address = self.server.accept()
            print(f"New connection from {address}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        try:
            # Initial handshake
            client_info = json.loads(client_socket.recv(1024).decode())
            client_id = client_info['client_id']
            
            # Check if server is full for new players
            if client_info['type'] == 'player':
                active_games = self.get_active_game_count()
                if active_games >= self.max_games and not self.waiting_players:
                    print(f"Server full, rejecting client {client_id}")
                    error_msg = {
                        'type': 'error',
                        'message': 'Server is full. Maximum number of games (2) reached.'
                    }
                    client_socket.send(json.dumps(error_msg).encode())
                    client_socket.close()
                    return

            self.clients[client_id] = client_socket
            print(f"Received connection from client {client_id} of type {client_info['type']}")

            if client_info['type'] == 'player':
                self.handle_player(client_id, client_socket)
            elif client_info['type'] == 'spectator':
                self.handle_spectator(client_id, client_socket, client_info['game_id'])
        except Exception as e:
            print(f"Error in handle_client: {str(e)}")
            if 'client_id' in locals():
                self.remove_client(client_id)

    def handle_spectator(self, client_id, client_socket, game_id):
        try:
            print(f"Spectator {client_id} trying to watch game {game_id}")
            game = self.games.get(game_id)
            if game:
                print(f"Game found, adding spectator {client_id}")
                game.spectators.append(client_id)
                
                # Send initial game state
                initial_state = {
                    'type': 'game_state',
                    'state': game.get_game_state()
                }
                self.send_message(client_id, initial_state)
                
                # Keep spectator connected
                while True:
                    try:
                        if not client_socket.recv(1024):
                            break
                    except:
                        break
            else:
                print(f"Game {game_id} not found")
                self.send_message(client_id, {
                    'type': 'error',
                    'message': 'Game not found'
                })
        except Exception as e:
            print(f"Error in handle_spectator: {str(e)}")
        finally:
            print(f"Spectator {client_id} disconnected")
            self.remove_client(client_id)

    def handle_player(self, client_id, client_socket):
        if len(self.waiting_players) > 0:
            # Match with waiting player
            opponent_id = self.waiting_players.pop(0)
            game = ChessGame(opponent_id, client_id)  # First player is white
            self.games[opponent_id] = game
            self.games[client_id] = game
            
            print(f"Created game between {opponent_id} (white) and {client_id} (black)")
            
            # Notify both players
            self.send_message(opponent_id, {'type': 'game_start', 'color': 'white'})
            self.send_message(client_id, {'type': 'game_start', 'color': 'black'})
            
            # Send initial game state
            initial_state = game.get_game_state()
            self.broadcast_game_state(game, initial_state)
        else:
            self.waiting_players.append(client_id)
            print(f"Player {client_id} added to waiting list")
            self.send_message(client_id, {'type': 'waiting'})

        while True:
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                
                message = json.loads(data)
                if message['type'] == 'move':
                    game = self.games.get(client_id)
                    if game and game.current_player == client_id:
                        if game.make_move(message['move']):
                            game_state = game.get_game_state()
                            self.broadcast_game_state(game, game_state)
                elif message['type'] == 'chat':
                    game = self.games.get(client_id)
                    if game:
                        sender_color = "White" if client_id == game.white_player else "Black"
                        self.broadcast_chat(game, client_id, sender_color, message['message'])
            except Exception as e:
                print(f"Error handling player message: {str(e)}")
                break

        self.remove_client(client_id)

    def broadcast_game_state(self, game, state):
        recipients = [game.white_player, game.black_player] + game.spectators
        message = {
            'type': 'game_state',
            'state': state
        }
        for recipient in recipients:
            self.send_message(recipient, message)

    def broadcast_chat(self, game, sender_id, sender_color, message):
        recipients = [game.white_player, game.black_player] + game.spectators
        chat_message = {
            'type': 'chat',
            'sender': sender_color,
            'message': message
        }
        game.chat_messages.append(chat_message)
        for recipient in recipients:
            self.send_message(recipient, chat_message)

    def send_message(self, client_id, message):
        try:
            client_socket = self.clients.get(client_id)
            if client_socket:
                client_socket.send(json.dumps(message).encode())
        except Exception as e:
            print(f"Error sending message to {client_id}: {str(e)}")
            self.remove_client(client_id)

    def remove_client(self, client_id):
        if client_id in self.waiting_players:
            self.waiting_players.remove(client_id)
        if client_id in self.clients:
            try:
                self.clients[client_id].close()
            except:
                pass
            del self.clients[client_id]
        game = self.games.get(client_id)
        if game:
            if client_id in game.spectators:
                game.spectators.remove(client_id)
            else:
                opponent_id = game.black_player if client_id == game.white_player else game.white_player
                if opponent_id in self.clients:
                    self.send_message(opponent_id, {'type': 'opponent_disconnected'})
                del self.games[client_id]
                if opponent_id in self.games:
                    del self.games[opponent_id]

if __name__ == "__main__":
    server = ChessServer()
    server.start()