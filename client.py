import pygame
from pygame import *
import socket
import json
import threading
import time
import math
import random
import os
import colorsys

# --- НАЛАШТУВАННЯ ---
WIDTH, HEIGHT = 900, 700
FPS = 60
SERVER_IP = 'localhost'
SERVER_PORT = 8080

# --- ІНІЦІАЛІЗАЦІЯ ---
pygame.init()
pygame.mixer.init()
flags = HWSURFACE | DOUBLEBUF
screen = display.set_mode((WIDTH, HEIGHT), flags)
display.set_caption("PING-PONG")
clock = pygame.time.Clock() 

# --- КОЛЬОРИ ---
C_BG = (10, 5, 20)           
C_GRID_NEAR = (50, 0, 80)    
C_GRID_FAR = (255, 0, 150)
C_WHITE = (220, 220, 255)
C_CYAN = (0, 255, 255)
C_MAGENTA = (255, 0, 255)
C_GOLD = (255, 200, 50)
C_RED = (255, 50, 50)
C_GREEN = (50, 255, 100)

# --- ЗВУКИ ---
sound_hit = pygame.mixer.Sound('hit.ogg')

# --- ГЕНЕРАТОР СКІНІВ ---
def generate_skins():
    paddle_skins = {}
    ball_skins = {}
    categories = {0: 'BASIC', 1: 'NEON', 2: 'METAL', 3: 'FIRE', 4: 'NATURE', 
                  5: 'COSMOS', 6: 'ICE', 7: 'MAGIC', 8: 'ACID', 9: 'LEGEND'}
    
    for i in range(100):
        cat = i // 10
        hue = (i * 0.13) % 1.0
        sat = 0.9
        val = 1.0
        rgb = colorsys.hsv_to_rgb(hue, sat, val)
        color = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        
        name = f"{categories[cat]} MK-{i%10+1}"
        cost = i * 15 + 50
        
        paddle_skins[f"paddle_{i}"] = {'color': color, 'name': name, 'cost': cost}
        ball_skins[f"ball_{i}"] = {'color': color, 'name': name, 'cost': cost}
    return paddle_skins, ball_skins

PADDLE_SKINS, BALL_SKINS = generate_skins()

# --- ЗБЕРЕЖЕННЯ ДАНИХ ГРАВЦЯ ---
PLAYER_FILE = 'player_save.json'
class PlayerProfile:
    def __init__(self):
        self.coins = 100
        self.paddle_skin = 'paddle_0'
        self.ball_skin = 'ball_0'
        self.owned = {'paddle_0', 'ball_0'}
        self.load()

    def load(self):
        if os.path.exists(PLAYER_FILE):
            try:
                with open(PLAYER_FILE, 'r') as f:
                    d = json.load(f)
                    self.coins = d.get('coins', 100)
                    self.paddle_skin = d.get('paddle_skin', 'paddle_0')
                    self.ball_skin = d.get('ball_skin', 'ball_0')
                    self.owned = set(d.get('owned', [])) | {'paddle_0', 'ball_0'}
            except: pass

    def save(self):
        with open(PLAYER_FILE, 'w') as f:
            json.dump({'coins': self.coins, 'paddle_skin': self.paddle_skin, 
                       'ball_skin': self.ball_skin, 'owned': list(self.owned)}, f)

    def buy(self, type_, id_):
        skins = PADDLE_SKINS if type_ == 'paddle' else BALL_SKINS
        if id_ in skins and self.coins >= skins[id_]['cost']:
            self.coins -= skins[id_]['cost']
            self.owned.add(id_)
            self.save()
            return True
        return False

# --- СИСТЕМА ЕФЕКТІВ ---
class VFXManager:
    def __init__(self):
        self.shake_timer = 0
        self.shake_amount = 0
        self.flash_alpha = 0
        self.particles = []

    def shake(self, amount, duration):
        self.shake_amount = amount
        self.shake_timer = duration

    def flash(self, intensity=100):
        self.flash_alpha = intensity

    def spawn_particles(self, x, y, color, count=15, speed_mult=1.0):
        for _ in range(count):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(2, 6) * speed_mult
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.randint(20, 50)
            size = random.randint(2, 5)
            self.particles.append([x, y, vx, vy, life, life, color, size])

    def update(self):
        if self.shake_timer > 0: self.shake_timer -= 1
        if self.flash_alpha > 0: self.flash_alpha = max(0, self.flash_alpha - 5)
        
        for p in self.particles[:]:
            p[0] += p[2]
            p[1] += p[3]
            p[2] *= 0.92
            p[3] *= 0.92
            p[4] -= 1
            if p[4] <= 0: self.particles.remove(p)

    def get_shake_offset(self):
        if self.shake_timer > 0:
            return random.randint(-self.shake_amount, self.shake_amount), random.randint(-self.shake_amount, self.shake_amount)
        return 0, 0

    def draw(self, surf):
        for p in self.particles:
            x, y, _, _, life, max_life, color, size = p
            alpha = int(255 * (life / max_life))
            
            s = Surface((size*4, size*4), SRCALPHA)
            pygame.draw.circle(s, (*color, alpha), (size*2, size*2), size)

            surf.blit(s, (x-size*2, y-size*2), special_flags=BLEND_ADD)

        if self.flash_alpha > 0:
            flash_surf = Surface((WIDTH, HEIGHT), SRCALPHA)
            flash_surf.fill((255, 255, 255, int(self.flash_alpha)))
            surf.blit(flash_surf, (0, 0), special_flags=BLEND_ADD)

# --- РЕНДЕРЕР ---
class NeonRenderer:
    def __init__(self):
        self.main_surf = Surface((WIDTH, HEIGHT))
        self.bloom_surf = Surface((WIDTH // 4, HEIGHT // 4))
        
        self.font_huge = font.Font(None, 100)
        self.font_big = font.Font(None, 60)
        self.font_med = font.Font(None, 36)
        self.font_small = font.Font(None, 24)

    def draw_retro_grid(self, surf, t):
        horizon_y = HEIGHT * 0.6
        cx = WIDTH // 2
        
        for i in range(-20, 21):
            offset_x = i * 60
            top_x = cx + offset_x * 0.1
            bottom_x = cx + offset_x * 3
            pygame.draw.line(surf, C_GRID_NEAR, (top_x, horizon_y), (bottom_x, HEIGHT), 1)

        speed_offset = (t * 100) % 40
        for i in range(20):
            y_base = horizon_y + (i * 20) + speed_offset
            prog = (i + (speed_offset/40)) / 20 
            y_pos = horizon_y + (HEIGHT - horizon_y) * (prog**2)
            
            if y_pos > HEIGHT: continue
            
            alpha = int(255 * prog)
            col = (C_GRID_FAR[0], C_GRID_FAR[1], C_GRID_FAR[2])
            pygame.draw.line(surf, col, (0, y_pos), (WIDTH, y_pos), 1)
        
        pygame.draw.circle(surf, (255, 100, 50), (cx, int(horizon_y) - 40), 60)
        for i in range(6):
            y_bar = int(horizon_y) - 80 + i * 12
            if y_bar > int(horizon_y) - 40 + 60: break
            h = 4 + i
            if y_bar > int(horizon_y) - 100:
                pygame.draw.rect(surf, C_BG, (cx - 70, y_bar, 140, h))

    def render_frame(self, screen, game_client, vfx, frame_time):
        self.main_surf.fill(C_BG)
        self.draw_retro_grid(self.main_surf, frame_time)

        if game_client.state_type == 'MENU':
            self.draw_menu(self.main_surf, game_client)
        elif game_client.state_type == 'SHOP':
            self.draw_shop(self.main_surf, game_client)
        elif game_client.state_type == 'GAME':
            self.draw_game(self.main_surf, game_client)

        vfx.draw(self.main_surf)

        pygame.transform.smoothscale(self.main_surf, (WIDTH // 4, HEIGHT // 4), self.bloom_surf)
        bloom_upscaled = pygame.transform.smoothscale(self.bloom_surf, (WIDTH, HEIGHT))
        
        shake_x, shake_y = vfx.get_shake_offset()
        
        screen.blit(self.main_surf, (shake_x, shake_y))
        bloom_upscaled.set_alpha(180)
        screen.blit(bloom_upscaled, (shake_x, shake_y), special_flags=BLEND_ADD)

        for y in range(0, HEIGHT, 4):
            pygame.draw.line(screen, (0, 0, 0), (0, y), (WIDTH, y), 1)

    # --- UI ---
    def draw_text(self, surf, text, pos, font, color, center=True, glow=True):
        txt_s = font.render(text, True, color)
        rect = txt_s.get_rect()
        if center: rect.center = pos
        else: rect.topleft = pos
        
        if glow:
            glow_s = font.render(text, True, (color[0]//3, color[1]//3, color[2]//3))
            surf.blit(glow_s, (rect.x + 3, rect.y + 3))
        surf.blit(txt_s, rect)
        return rect

    def draw_menu(self, surf, client):
        off_x = random.randint(-3, 3)
        self.draw_text(surf, "- PING-PONG -", (WIDTH//2 + off_x, 150), self.font_huge, C_MAGENTA)
        
        status = "SERVER: CONNECTED" if client.connected else "SERVER: SEARCHING..."
        col = C_GREEN if client.connected else C_RED
        self.draw_text(surf, status, (WIDTH//2, 220), self.font_small, col)

        opts = ["START GAME", "SHOP", "EXIT"]
        for i, opt in enumerate(opts):
            color = C_GOLD if i == client.menu_idx else (100, 100, 150)
            prefix = ">> " if i == client.menu_idx else ""
            txt = f"{prefix}{opt}"
            rect = self.draw_text(surf, txt, (WIDTH//2, 350 + i * 70), self.font_big, color)
            
            if i == client.menu_idx:
                glow_rect = rect.inflate(40, 20)
                pygame.draw.rect(surf, color, glow_rect, 2)

        self.draw_text(surf, f"CREDITS: {client.profile.coins}", (WIDTH-100, HEIGHT-50), self.font_med, C_GOLD)

    def draw_shop(self, surf, client):
        self.draw_text(surf, "ARMORY", (WIDTH//2, 60), self.font_big, C_CYAN)
        
        mode_txt = f"< {client.shop_tab.upper()}S >"
        self.draw_text(surf, mode_txt, (WIDTH//2, 120), self.font_med, C_WHITE)

        skins = PADDLE_SKINS if client.shop_tab == 'paddle' else BALL_SKINS
        keys = list(skins.keys())
        
        start = client.shop_scroll
        for i in range(start, min(start + 5, len(keys))):
            key = keys[i]
            item = skins[key]
            y = 180 + (i - start) * 80
            
            is_sel = (i == client.shop_idx)
            
            row_rect = Rect(100, y, WIDTH-200, 70)
            bg_col = (40, 40, 60) if is_sel else (20, 20, 30)
            pygame.draw.rect(surf, bg_col, row_rect)
            if is_sel: pygame.draw.rect(surf, C_GOLD, row_rect, 2)

            pygame.draw.circle(surf, item['color'], (150, y + 35), 20)
            
            self.draw_text(surf, item['name'], (200, y+20), self.font_med, C_WHITE, center=False)
            
            if (client.shop_tab == 'paddle' and client.profile.paddle_skin == key) or \
               (client.shop_tab == 'ball' and client.profile.ball_skin == key):
                state_txt = "EQUIPPED"
                scol = C_CYAN
            elif key in client.profile.owned:
                state_txt = "OWNED"
                scol = C_GREEN
            else:
                state_txt = f"{item['cost']} CR"
                scol = C_GOLD if client.profile.coins >= item['cost'] else C_RED
            
            self.draw_text(surf, state_txt, (WIDTH-250, y+25), self.font_med, scol, center=False)

        self.draw_text(surf, "ARROWS: Select | ENTER: Buy/Equip | ESC: Back", (WIDTH//2, HEIGHT-40), self.font_small, (150, 150, 150))

    def draw_game(self, surf, client):
        if not client.game_data:
            self.draw_text(surf, "WAITING FOR OPPONENT...", (WIDTH//2, HEIGHT//2), self.font_med, C_WHITE)
            return

        scores = client.game_data.get('scores', [0, 0])
        score_str = f"{scores[0]} : {scores[1]}"
        self.draw_text(surf, score_str, (WIDTH//2, 60), self.font_huge, C_WHITE)

        paddles = client.game_data.get('paddles', {})
        my_skin_key = client.profile.paddle_skin
        my_color = PADDLE_SKINS[my_skin_key]['color']
        
        r1 = Rect(20, paddles.get('0', 300), 20, 100)
        c1 = my_color if client.pid == 0 else (100, 100, 100)
        pygame.draw.rect(surf, c1, r1)
        pygame.draw.rect(surf, C_WHITE, r1, 3)

        r2 = Rect(WIDTH-40, paddles.get('1', 300), 20, 100)
        c2 = my_color if client.pid == 1 else (100, 100, 100)
        pygame.draw.rect(surf, c2, r2)
        pygame.draw.rect(surf, C_WHITE, r2, 3)

        ball = client.game_data.get('ball', {})
        bx, by = ball.get('x', WIDTH//2), ball.get('y', HEIGHT//2)
        
        if hasattr(client, 'last_ball'):
            lx, ly = client.last_ball
            pygame.draw.line(surf, C_CYAN, (lx, ly), (bx, by), 5)
        
        ball_skin_key = client.profile.ball_skin
        b_col = BALL_SKINS[ball_skin_key]['color'] if client.pid == 0 else C_WHITE
        
        pygame.draw.circle(surf, b_col, (int(bx), int(by)), 12)
        pygame.draw.circle(surf, C_WHITE, (int(bx), int(by)), 6)

        cd = client.game_data.get('countdown', 0)
        if cd > 0:
            self.draw_text(surf, str(cd), (WIDTH//2, HEIGHT//2), self.font_huge, C_GOLD)
        
        winner = client.game_data.get('winner')
        if winner is not None:
            txt = "VICTORY" if winner == client.pid else "DEFEAT"
            col = C_GOLD if winner == client.pid else C_RED
            self.draw_text(surf, txt, (WIDTH//2, HEIGHT//2), self.font_huge, col)
            self.draw_text(surf, "PRESS SPACE TO RETURN", (WIDTH//2, HEIGHT//2 + 80), self.font_small, C_WHITE)


# --- ЛОГІКА КЛІЄНТА ---
class GameClient:
    def __init__(self):
        self.running = True
        self.state_type = 'MENU'
        
        self.renderer = NeonRenderer()
        self.vfx = VFXManager()
        self.profile = PlayerProfile()
        
        self.sock = None
        self.connected = False
        self.pid = -1
        self.game_data = {}
        
        self.menu_idx = 0
        self.shop_tab = 'paddle'
        self.shop_idx = 0
        self.shop_scroll = 0
        
        self.last_ball = (WIDTH//2, HEIGHT//2)
        
        threading.Thread(target=self.net_worker, daemon=True).start()

    def net_worker(self):
        while self.running:
            if not self.connected:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(2)
                    self.sock.connect((SERVER_IP, SERVER_PORT))
                    self.pid = int(self.sock.recv(16).decode().strip())
                    self.sock.setblocking(False)
                    self.connected = True
                except:
                    time.sleep(1)
            else:
                try:
                    data = self.sock.recv(4096).decode()
                    if not data:
                        self.connected = False
                        self.sock.close()
                        continue
                    
                    lines = data.split('\n')
                    for line in lines:
                        if not line: continue
                        try:
                            new_state = json.loads(line)
                            self.process_state(new_state)
                            self.game_data = new_state
                        except: pass
                except BlockingIOError:
                    time.sleep(0.01)
                except:
                    self.connected = False

    def process_state(self, new_state):
        if 'ball' not in new_state: return
        
        nx, ny = new_state['ball']['x'], new_state['ball']['y']
        
        if 'ball' in self.game_data:
            ovx = self.game_data['ball'].get('vx', 0)
            nvx = new_state['ball'].get('vx', 0)
            
            if ovx != nvx:
                self.vfx.shake(10, 10)
                self.vfx.spawn_particles(nx, ny, C_WHITE, 20, 2.0)
                
            ovy = self.game_data['ball'].get('vy', 0)
            nvy = new_state['ball'].get('vy', 0)
            if ovy != nvy:
                self.vfx.spawn_particles(nx, ny, C_CYAN, 10, 1.0)
        
        oscores = self.game_data.get('scores', [0,0])
        nscores = new_state.get('scores', [0,0])
        if nscores != oscores:
             self.vfx.flash(150)
             self.vfx.shake(20, 20)
             if self.pid != -1 and nscores[self.pid] > oscores[self.pid]:
                 self.profile.coins += 10
                 self.profile.save()

        if new_state.get('sound_event'):
            if new_state['sound_event'] == 'wall_hit':
                sound_hit.play()
            elif new_state['sound_event'] == 'platform_hit':
                sound_hit.play()

        self.last_ball = (nx, ny)

    def send_cmd(self, cmd):
        if self.connected and self.sock:
            try: self.sock.send(cmd.encode())
            except: self.connected = False

    def handle_input(self):
        keys = key.get_pressed()

        for e in event.get():
            if e.type == QUIT: self.running = False
            
            if e.type == KEYDOWN:
                # --- КЕРУВАННЯ МЕНЮ ---
                if self.state_type == 'MENU':
                    if e.key == K_UP: self.menu_idx = (self.menu_idx - 1) % 3
                    if e.key == K_DOWN: self.menu_idx = (self.menu_idx + 1) % 3
                    if e.key == K_RETURN:
                        if self.menu_idx == 0:
                            if self.connected:
                                self.state_type = 'GAME'
                                self.send_cmd("READY")
                        elif self.menu_idx == 1: self.state_type = 'SHOP'
                        elif self.menu_idx == 2: self.running = False
                
                # --- КЕРУВАННЯ МАГАЗИНОМ ---
                elif self.state_type == 'SHOP':
                    if e.key == K_ESCAPE: self.state_type = 'MENU'
                    elif e.key == K_LEFT or e.key == K_RIGHT:
                        self.shop_tab = 'ball' if self.shop_tab == 'paddle' else 'paddle'
                        self.shop_idx = 0
                        self.shop_scroll = 0
                    elif e.key == K_UP:
                        if self.shop_idx > 0: self.shop_idx -= 1
                        if self.shop_idx < self.shop_scroll: self.shop_scroll = self.shop_idx
                    elif e.key == K_DOWN:
                        limit = len(PADDLE_SKINS) if self.shop_tab == 'paddle' else len(BALL_SKINS)
                        if self.shop_idx < limit - 1: self.shop_idx += 1
                        if self.shop_idx >= self.shop_scroll + 5: self.shop_scroll += 1
                    elif e.key == K_RETURN:
                        skins = PADDLE_SKINS if self.shop_tab == 'paddle' else BALL_SKINS
                        key_id = list(skins.keys())[self.shop_idx]
                        if key_id in self.profile.owned:
                            if self.shop_tab == 'paddle': self.profile.paddle_skin = key_id
                            else: self.profile.ball_skin = key_id
                            self.profile.save()
                            self.vfx.flash(50)
                        else:
                            if self.profile.buy(self.shop_tab, key_id):
                                self.vfx.flash(100)
                                self.vfx.spawn_particles(WIDTH//2, HEIGHT//2, C_GOLD, 50)

                # --- УПРАВЛІННЯ ГРОЮ ---
                elif self.state_type == 'GAME':
                    if e.key == K_SPACE and self.game_data.get('winner') is not None:
                        self.state_type = 'MENU'
                        self.game_data = {}

        if self.state_type == 'GAME' and self.connected:
            if keys[K_w] or keys[K_UP]: self.send_cmd("UP")
            if keys[K_s] or keys[K_DOWN]: self.send_cmd("DOWN")

    def run(self):
        start_t = time.time()
        while self.running:
            self.handle_input()
            self.vfx.update()
            
            t = time.time() - start_t
            self.renderer.render_frame(screen, self, self.vfx, t)
            
            display.flip()
            clock.tick(FPS)
        
        if self.sock: self.sock.close()
        pygame.quit()

if __name__ == "__main__":
    GameClient().run()