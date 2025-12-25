import socket
import json
import threading
import time
import random

WIDTH, HEIGHT = 900, 700
BALL_SPEED = 6
PADDLE_SPEED = 15
COUNTDOWN_START = 3
TARGET_SCORE = 10

class GameServer:
    def __init__(self, host='localhost', port=8080):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(2)
        print(f"Сервер запущено на {host}:{port}")

        self.clients = {0: None, 1: None}
        self.connected = {0: False, 1: False}
        self.ready = {0: False, 1: False}
        self.lock = threading.Lock()
        self.reset_game_state()

    def reset_game_state(self):
        self.paddles = {0: 300, 1: 300}
        self.scores = [0, 0]
        self.ball = {
            "x": WIDTH // 2,
            "y": HEIGHT // 2,
            "vx": BALL_SPEED * random.choice([-1, 1]),
            "vy": BALL_SPEED * random.choice([-1, 1])
        }
        self.countdown = COUNTDOWN_START
        self.game_over = False
        self.winner = None
        self.ready = {0: False, 1: False}

    def handle_client(self, pid):
        print(f"[Гравець {pid}] Підключено")
        conn = self.clients[pid]
        conn.setblocking(False)
        
        while not self.game_over and self.connected[pid]:
            try:
                data = conn.recv(64).decode().strip()
                if not data:
                    time.sleep(0.01)
                    continue
                    
                with self.lock:
                    if data == "UP":
                        self.paddles[pid] = max(0, self.paddles[pid] - PADDLE_SPEED)
                    elif data == "DOWN":
                        self.paddles[pid] = min(HEIGHT - 100, self.paddles[pid] + PADDLE_SPEED)
                    elif data == "READY":
                        self.ready[pid] = True
                        print(f"[Гравець {pid}] Готовий!")
                        
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                print(f"[Гравець {pid}] Помилка: {e}")
                break
        
        with self.lock:
            self.connected[pid] = False
        print(f"[Гравець {pid}] Від'єднано")

    def broadcast_state(self):
        state = json.dumps({
            "paddles": self.paddles,
            "ball": self.ball,
            "scores": self.scores,
            "countdown": max(self.countdown, 0),
            "winner": self.winner if self.game_over else None
        }) + "\n"
        
        for pid, conn in self.clients.items():
            if conn and self.connected[pid]:
                try:
                    conn.sendall(state.encode())
                except Exception as e:
                    print(f"[Broadcast] Помилка надсилання гравцю {pid}: {e}")
                    self.connected[pid] = False

    def reset_ball(self):
        angle = random.uniform(-0.5, 0.5)
        direction = random.choice([-1, 1])
        
        self.ball = {
            "x": WIDTH // 2,
            "y": HEIGHT // 2,
            "vx": BALL_SPEED * direction,
            "vy": BALL_SPEED * angle
        }

    def ball_logic(self):
        while not (self.ready[0] and self.ready[1]):
            time.sleep(0.1)
            if not self.connected[0] or not self.connected[1]:
                print("[Сервер] Один з гравців відключився до початку гри")
                return
        
        print("[Сервер] Обидва гравці готові! Починаємо гру...")
        
        while self.countdown > 0:
            time.sleep(1)
            with self.lock:
                self.countdown -= 1
                self.broadcast_state()
        
        while not self.game_over:
            with self.lock:
                self.ball['x'] += self.ball['vx']
                self.ball['y'] += self.ball['vy']

                if self.ball['y'] <= 10 or self.ball['y'] >= HEIGHT - 10:
                    self.ball['vy'] *= -1
                    self.ball['y'] = max(10, min(HEIGHT - 10, self.ball['y']))

                if (20 <= self.ball['x'] <= 50 and 
                    self.paddles[0] - 10 <= self.ball['y'] <= self.paddles[0] + 110):
                    self.ball['vx'] = abs(self.ball['vx'])

                    relative_y = (self.ball['y'] - self.paddles[0] - 50) / 50
                    self.ball['vy'] += relative_y * 2
                    self.ball['x'] = 50

                if (WIDTH - 50 <= self.ball['x'] <= WIDTH - 20 and 
                    self.paddles[1] - 10 <= self.ball['y'] <= self.paddles[1] + 110):
                    self.ball['vx'] = -abs(self.ball['vx'])
                    relative_y = (self.ball['y'] - self.paddles[1] - 50) / 50
                    self.ball['vy'] += relative_y * 2
                    self.ball['x'] = WIDTH - 50

                if self.ball['x'] < 0:
                    self.scores[1] += 1
                    self.reset_ball()
                    time.sleep(0.5)
                    
                elif self.ball['x'] > WIDTH:
                    self.scores[0] += 1
                    self.reset_ball()
                    time.sleep(0.5)

                if self.scores[0] >= TARGET_SCORE:
                    self.game_over = True
                    self.winner = 0
                    print(f"Гравець 0 переміг з рахунком {self.scores[0]}:{self.scores[1]}")
                    
                elif self.scores[1] >= TARGET_SCORE:
                    self.game_over = True
                    self.winner = 1
                    print(f"Гравець 1 переміг з рахунком {self.scores[0]}:{self.scores[1]}")

                self.broadcast_state()
                
            time.sleep(0.016)

    def accept_players(self):
        for pid in [0, 1]:
            print(f"Очікуємо гравця {pid}...")
            conn, addr = self.server.accept()
            self.clients[pid] = conn
            
            conn.sendall(f"{pid}\n".encode())
            self.connected[pid] = True
            
            print(f"Гравець {pid} під'єднався з {addr}")
            
            threading.Thread(target=self.handle_client, args=(pid,), daemon=True).start()

    def run(self):
        while True:
            print("\n" + "="*50)
            print("Очікуємо гравців для нової гри...")
            print("="*50)
            
            self.accept_players()
            
            ball_thread = threading.Thread(target=self.ball_logic, daemon=True)
            ball_thread.start()
            
            while not self.game_over:
                time.sleep(0.1)
                if not self.connected[0] and not self.connected[1]:
                    self.game_over = True
                    if self.winner is None:
                        self.winner = 0 if self.scores[0] > self.scores[1] else 1
                    break
            
            print(f"\n Гра завершена! Переможець: Гравець {self.winner}")
            print(f"Рахунок: {self.scores[0]} : {self.scores[1]}")
            
            for _ in range(3):
                time.sleep(1)
                self.broadcast_state()
            
            for pid in [0, 1]:
                if self.clients[pid]:
                    try:
                        self.clients[pid].close()
                    except:
                        pass
                    self.clients[pid] = None
                    self.connected[pid] = False

if __name__ == "__main__":
    GameServer().run()