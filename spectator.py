import socket
import json
import threading
import pygame
import chess
import uuid
import time

# Initialize Pygame
pygame.init()

# Constants
WINDOW_SIZE = 800
BOARD_SIZE = 600
SQUARE_SIZE = BOARD_SIZE // 8
PIECE_SIZE = SQUARE_SIZE - 10

# Colors
WHITE = (0, 0, 0)
BLACK = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_SQUARE = (118, 150, 86)
LIGHT_SQUARE = (238, 238, 210)

class SpectatorClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.client_id = str(uuid.uuid4())
        self.board = chess.Board()
        self.chat_messages = []
        self.last_state = None
        self.lock = threading.Lock()
        self.connected = False
        self.error_message = None
        
        # Initialize Pygame window
        self.screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
        pygame.display.set_caption("Chess Spectator")
        
        # Initialize font
        self.font = pygame.font.SysFont('Arial', PIECE_SIZE)
        self.status_font = pygame.font.SysFont('Arial', 24)
        
        # Simple letters for pieces
        self.pieces = {
            'P': 'P', 'R': 'R', 'N': 'H', 'B': 'B', 'Q': 'Q', 'K': 'K',
            'p': 'p', 'r': 'r', 'n': 'h', 'b': 'b', 'q': 'q', 'k': 'k'
        }

    def connect(self, game_id):
        try:
            print(f"\nAttempting to connect to server at {self.host}:{self.port}")
            self.client.connect((self.host, self.port))
            print("Connected to server")
            
            # Send initial handshake
            handshake = {
                'type': 'spectator',
                'client_id': self.client_id,
                'game_id': game_id
            }
            print(f"Sending handshake: {handshake}")
            self.send_message(handshake)
            
            # Start receiving messages in a separate thread
            self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receiver_thread.start()
            
            # Wait briefly to check if connection is successful
            time.sleep(1)
            return self.connected
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            return False

    def send_message(self, message):
        try:
            data = json.dumps(message).encode()
            self.client.send(data)
            print(f"Sent message: {message}")
        except Exception as e:
            print(f"Failed to send message: {str(e)}")

    def receive_messages(self):
        while True:
            try:
                data = self.client.recv(1024).decode()
                if not data:
                    print("Server closed connection")
                    break
                    
                message = json.loads(data)
                print(f"Received message: {message}")
                
                if message['type'] == 'error':
                    self.error_message = message['message']
                    break
                    
                self.handle_message(message)
                self.connected = True
                
            except Exception as e:
                print(f"Error receiving message: {str(e)}")
                break
                
        print("Receiver thread ending")
        self.connected = False

    def handle_message(self, message):
        with self.lock:
            try:
                if message['type'] == 'game_state':
                    new_state = message['state']['fen']
                    print(f"Received new game state: {new_state}")
                    if new_state != self.last_state:
                        self.board = chess.Board(new_state)
                        self.last_state = new_state
                        print("Board updated")
            except Exception as e:
                print(f"Error handling message: {str(e)}")

    def draw_board(self):
        with self.lock:
            self.screen.fill(GRAY)
            
            if not self.connected:
                # Show error message or connection status
                msg = self.error_message if self.error_message else "Connecting to game..."
                text = self.status_font.render(msg, True, BLACK)
                text_rect = text.get_rect(center=(WINDOW_SIZE//2, WINDOW_SIZE//2))
                self.screen.blit(text, text_rect)
                pygame.display.flip()
                return
            
            # Draw board squares
            board_offset = (WINDOW_SIZE - BOARD_SIZE) // 2
            for rank in range(8):
                for file in range(8):
                    color = LIGHT_SQUARE if (rank + file) % 2 == 0 else DARK_SQUARE
                    pygame.draw.rect(self.screen, color,
                                   (board_offset + file * SQUARE_SIZE,
                                    board_offset + (7-rank) * SQUARE_SIZE,
                                    SQUARE_SIZE, SQUARE_SIZE))

            # Draw pieces
            for square in chess.SQUARES:
                piece = self.board.piece_at(square)
                if piece:
                    file = chess.square_file(square)
                    rank = chess.square_rank(square)
                    piece_char = self.pieces[piece.symbol()]
                    text = self.font.render(piece_char, True, BLACK if piece.color else WHITE)
                    text_rect = text.get_rect(center=(
                        board_offset + file * SQUARE_SIZE + SQUARE_SIZE // 2,
                        board_offset + (7-rank) * SQUARE_SIZE + SQUARE_SIZE // 2
                    ))
                    self.screen.blit(text, text_rect)

            # Add status text
            spectator_text = self.status_font.render("Spectator Mode", True, BLACK)
            turn_text = self.status_font.render(
                "Current Turn: White" if self.board.turn else "Current Turn: Black", 
                True, BLACK
            )
            self.screen.blit(spectator_text, (10, 10))
            self.screen.blit(turn_text, (10, 40))

            pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            self.draw_board()
            clock.tick(30)
            
        pygame.quit()

if __name__ == "__main__":
    print("\n=== Chess Game Spectator ===")
    game_id = input("Enter the game ID to spectate: ").strip()
    spectator = SpectatorClient()
    
    if spectator.connect(game_id):
        print("Successfully connected as spectator")
        spectator.run()
    else:
        print("Failed to connect to the game")