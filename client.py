import socket
import json
import threading
import pygame
import chess
import uuid
import time
import sys

# Initialize Pygame
pygame.init()

# Constants
WINDOW_SIZE = 1000  # Increased window size to accommodate chat
BOARD_SIZE = 600
SQUARE_SIZE = BOARD_SIZE // 8
PIECE_SIZE = SQUARE_SIZE - 10
CHAT_WIDTH = 300  # Width of chat panel
CHAT_HEIGHT = BOARD_SIZE
CHAT_INPUT_HEIGHT = 40
MAX_CHAT_MESSAGES = 15

# Colors
WHITE = (0, 0, 0)
BLACK = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_SQUARE = (118, 150, 86)
LIGHT_SQUARE = (238, 238, 210)
HIGHLIGHT = (186, 202, 43)
CHAT_BG = (240, 240, 240)
INPUT_BG = (255, 255, 255)

class ChessClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.client_id = str(uuid.uuid4())
        self.board = chess.Board()
        self.color = None
        self.is_my_turn = False
        self.selected_square = None
        self.chat_messages = []
        self.chat_input = ""
        self.game_started = False
        self.running = True
        
        # Initialize Pygame window
        self.screen = pygame.display.set_mode((WINDOW_SIZE, BOARD_SIZE))
        pygame.display.set_caption("Multiplayer Chess")
        
        # Initialize fonts
        self.piece_font = pygame.font.SysFont('Arial', PIECE_SIZE)
        self.chat_font = pygame.font.SysFont('Arial', 16)
        self.status_font = pygame.font.SysFont('Arial', 20)
        print(f"\n=== Your Game ID: {self.client_id} ===\n")
        
        # Simple letters for pieces
        self.pieces = {
            'P': 'P', 'R': 'R', 'N': 'H', 'B': 'B', 'Q': 'Q', 'K': 'K',  # White pieces (uppercase)
            'p': 'p', 'r': 'r', 'n': 'h', 'b': 'b', 'q': 'q', 'k': 'k'   # Black pieces (lowercase)
        }

    def connect(self):
        try:
            self.client.connect((self.host, self.port))
            # Send initial handshake
            self.send_message({
                'type': 'player',
                'client_id': self.client_id
            })
            
            # Wait for initial response to check if server is full
            try:
                response = json.loads(self.client.recv(1024).decode())
                if response.get('type') == 'error':
                    print(f"\nServer Message: {response['message']}")
                    self.running = False
                    pygame.quit()
                    sys.exit()
                    return False
                self.handle_message(response)
            except json.JSONDecodeError:
                pass
            
            # Start receiving messages in a separate thread
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except ConnectionRefusedError:
            print("\nServer is not running")
            return False
        except Exception as e:
            print(f"\nFailed to connect to server: {str(e)}")
            return False

    def send_message(self, message):
        try:
            self.client.send(json.dumps(message).encode())
        except:
            print("Failed to send message")
            self.running = False

    def send_chat(self, message):
        self.send_message({
            'type': 'chat',
            'message': message
        })

    def receive_messages(self):
        while self.running:
            try:
                data = self.client.recv(1024).decode()
                if not data:
                    print("Server closed connection")
                    self.running = False
                    break
                
                message = json.loads(data)
                if message.get('type') == 'error':
                    print(f"\nServer Message: {message['message']}")
                    self.running = False
                    break
                self.handle_message(message)
            except json.JSONDecodeError:
                print("Received invalid message format")
            except ConnectionResetError:
                print("Server connection was forcibly closed")
                self.running = False
                break
            except Exception as e:
                print(f"Lost connection to server: {str(e)}")
                self.running = False
                break
        
        pygame.quit()
        sys.exit()

    def handle_message(self, message):
        if message['type'] == 'game_start':
            self.color = message['color']
            self.is_my_turn = self.color == 'white'
            self.game_started = True
            print(f"Game started! You are playing as {self.color}")
            self.chat_messages.append(f"System: Game started! You are playing as {self.color}")
        elif message['type'] == 'game_state':
            self.board = chess.Board(message['state']['fen'])
            self.is_my_turn = (
                (message['state']['current_player'] == 'white' and self.color == 'white') or
                (message['state']['current_player'] == 'black' and self.color == 'black')
            )
            if message['state']['is_check']:
                print("Check!")
                self.chat_messages.append("System: Check!")
            if message['state']['is_checkmate']:
                print("Checkmate!")
                self.chat_messages.append("System: Checkmate!")
            if message['state']['is_stalemate']:
                print("Stalemate!")
                self.chat_messages.append("System: Stalemate!")
        elif message['type'] == 'chat':
            chat_text = f"{message['sender']}: {message['message']}"
            self.chat_messages.append(chat_text)
            if len(self.chat_messages) > MAX_CHAT_MESSAGES:
                self.chat_messages.pop(0)
        elif message['type'] == 'opponent_disconnected':
            print("Opponent disconnected")
            self.chat_messages.append("System: Opponent disconnected")
        elif message['type'] == 'waiting':
            print("Waiting for opponent...")
            self.chat_messages.append("System: Waiting for opponent...")

    def get_square_from_pos(self, pos):
        x, y = pos
        if x >= WINDOW_SIZE - CHAT_WIDTH:  # Click in chat area
            return None
        file = (x - (WINDOW_SIZE - CHAT_WIDTH - BOARD_SIZE) // 2) // SQUARE_SIZE
        rank = 7 - ((y - (BOARD_SIZE - BOARD_SIZE) // 2) // SQUARE_SIZE)
        if 0 <= file <= 7 and 0 <= rank <= 7:
            return chess.square(file, rank)
        return None

    def draw_chat(self):
        # Draw chat background
        chat_rect = pygame.Rect(WINDOW_SIZE - CHAT_WIDTH, 0, CHAT_WIDTH, CHAT_HEIGHT)
        pygame.draw.rect(self.screen, CHAT_BG, chat_rect)
        
        # Draw chat messages
        y = CHAT_HEIGHT - CHAT_INPUT_HEIGHT - 20
        for message in reversed(self.chat_messages):
            text = self.chat_font.render(message, True, (0,0,0))
            text_rect = text.get_rect(left=WINDOW_SIZE - CHAT_WIDTH + 5, bottom=y)
            self.screen.blit(text, text_rect)
            y -= 20
            if y < 0:
                break

        # Draw chat input box
        input_rect = pygame.Rect(WINDOW_SIZE - CHAT_WIDTH, CHAT_HEIGHT - CHAT_INPUT_HEIGHT,
                               CHAT_WIDTH, CHAT_INPUT_HEIGHT)
        pygame.draw.rect(self.screen, INPUT_BG, input_rect)
        pygame.draw.rect(self.screen, (0,0,0), input_rect, 1)
        
        # Draw chat input text
        if self.chat_input:
            text = self.chat_font.render(self.chat_input, True, (0,0,0))
            self.screen.blit(text, (input_rect.left + 5, input_rect.top + 10))

    def draw_board(self):
        self.screen.fill(GRAY)
        
        # Draw board squares
        board_offset_x = (WINDOW_SIZE - CHAT_WIDTH - BOARD_SIZE) // 2
        board_offset_y = (BOARD_SIZE - BOARD_SIZE) // 2
        for rank in range(8):
            for file in range(8):
                color = LIGHT_SQUARE if (rank + file) % 2 == 0 else DARK_SQUARE
                pygame.draw.rect(self.screen, color,
                               (board_offset_x + file * SQUARE_SIZE,
                                board_offset_y + (7-rank) * SQUARE_SIZE,
                                SQUARE_SIZE, SQUARE_SIZE))

        # Highlight selected square
        if self.selected_square is not None:
            file = chess.square_file(self.selected_square)
            rank = chess.square_rank(self.selected_square)
            pygame.draw.rect(self.screen, HIGHLIGHT,
                           (board_offset_x + file * SQUARE_SIZE,
                            board_offset_y + (7-rank) * SQUARE_SIZE,
                            SQUARE_SIZE, SQUARE_SIZE))

        # Draw pieces
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                file = chess.square_file(square)
                rank = chess.square_rank(square)
                piece_char = self.pieces[piece.symbol()]
                text = self.piece_font.render(piece_char, True, BLACK if piece.color else WHITE)
                text_rect = text.get_rect(center=(
                    board_offset_x + file * SQUARE_SIZE + SQUARE_SIZE // 2,
                    board_offset_y + (7-rank) * SQUARE_SIZE + SQUARE_SIZE // 2
                ))
                self.screen.blit(text, text_rect)

        # Draw game status
        status_text = ""
        if not self.game_started:
            status_text = "Waiting for opponent..."
        elif self.is_my_turn:
            status_text = "Your turn"
        else:
            status_text = "Opponent's turn"
        
        status = self.status_font.render(status_text, True, BLACK)
        self.screen.blit(status, (10, 10))

        # Draw chat panel
        self.draw_chat()

        pygame.display.flip()

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and self.running:
                    x, y = event.pos
                    if x < WINDOW_SIZE - CHAT_WIDTH and self.game_started and self.is_my_turn:
                        square = self.get_square_from_pos(event.pos)
                        if square is not None:
                            if self.selected_square is None:
                                piece = self.board.piece_at(square)
                                if piece and ((piece.color and self.color == 'white') or
                                            (not piece.color and self.color == 'black')):
                                    self.selected_square = square
                            else:
                                move = chess.Move(self.selected_square, square)
                                if move in self.board.legal_moves:
                                    self.send_message({
                                        'type': 'move',
                                        'move': move.uci()
                                    })
                                self.selected_square = None
                elif event.type == pygame.KEYDOWN and self.running:
                    if event.key == pygame.K_RETURN and self.chat_input.strip():
                        self.send_chat(self.chat_input.strip())
                        self.chat_input = ""
                    elif event.key == pygame.K_BACKSPACE:
                        self.chat_input = self.chat_input[:-1]
                    else:
                        if len(self.chat_input) < 50:  # Limit input length
                            self.chat_input += event.unicode

            if self.running:
                self.draw_board()
            
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    client = ChessClient()
    if client.connect():
        client.run()
    else:
        pygame.quit()
        sys.exit()