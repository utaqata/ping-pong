# -*- coding: utf-8 -*-
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

# --- SETTINGS ---
WIDTH, HEIGHT = 900, 700
FPS = 60
SERVER_IP = 'localhost'
SERVER_PORT = 8080

# --- EASING FUNCTIONS ---
def ease_out_cubic(t): return 1 - pow(1 - t, 3)
def ease_out_back(t): c1 = 1.70158; c3 = c1 + 1; return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
def ease_in_out_sin(t): return -(math.cos(math.pi * t) - 1) / 2
def ease_out_expo(t): return 1 if t == 1 else 1 - pow(2, -10 * t)
def ease_in_out_cubic(t): return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2

# --- INITIALIZATION ---
pygame.init()
pygame.mixer.init()
flags = HWSURFACE | DOUBLEBUF
screen = display.set_mode((WIDTH, HEIGHT), flags)
display.set_caption("PING-PONG PREMIUM")
clock = pygame.time.Clock() 

# --- COLORS ---
C_BG = (10, 5, 20)           
C_WHITE = (220, 220, 255)
C_CYAN = (0, 255, 255)
C_MAGENTA = (255, 0, 255)
C_GOLD = (255, 200, 50)
C_RED = (255, 50, 50)
C_GREEN = (50, 255, 100)
C_PURPLE = (180, 50, 255)
C_ORANGE = (255, 150, 50)

# --- SOUNDS ---
try:
    sound_hit = pygame.mixer.Sound('hit.ogg')
    sound_select = pygame.mixer.Sound('select.ogg')
except:
    class DummySound:
        def play(self): pass
    sound_hit = DummySound()
    sound_select = DummySound()

# --- SKIN GENERATOR ---
def generate_skins():
    paddle_skins = {}
    ball_skins = {}
    categories = {0: 'BASIC', 1: 'NEON', 2: 'METAL', 3: 'FIRE', 4: 'NATURE', 
                  5: 'COSMOS', 6: 'ICE', 7: 'MAGIC', 8: 'ACID', 9: 'LEGEND'}
    for i in range(100):
        cat = i // 10
        hue = (i * 0.13) % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
        color = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        name = f"{categories[cat]} MK-{i%10+1}"
        cost = i * 25 + 50
        paddle_skins[f"paddle_{i}"] = {'color': color, 'name': name, 'cost': cost}
        ball_skins[f"ball_{i}"] = {'color': color, 'name': name, 'cost': cost}
    return paddle_skins, ball_skins

PADDLE_SKINS, BALL_SKINS = generate_skins()

# --- PLAYER PROFILE ---
PLAYER_FILE = 'player_save.json'
class PlayerProfile:
    def __init__(self):
        self.coins = 200
        self.paddle_skin = 'paddle_0'
        self.ball_skin = 'ball_0'
        self.owned = {'paddle_0', 'ball_0'}
        self.load()
    def load(self):
        if os.path.exists(PLAYER_FILE):
            try:
                with open(PLAYER_FILE, 'r') as f:
                    d = json.load(f)
                    self.coins = d.get('coins', 200)
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

# --- VFX SYSTEM ---
class VFXManager:
    def __init__(self):
        self.shake_timer = 0
        self.shake_amount = 0
        self.flash_alpha = 0
        self.particles = []
        self.ambient_particles = []
        self.trail_particles = []
        
        for _ in range(30):
            x = random.uniform(0, WIDTH)
            y = random.uniform(0, HEIGHT)
            vx = random.uniform(-0.3, 0.3)
            vy = random.uniform(-0.5, -0.2)
            color = random.choice([C_CYAN, C_MAGENTA, C_PURPLE])
            size = random.uniform(1, 3)
            self.ambient_particles.append([x, y, vx, vy, color, size, random.uniform(0, 6.28)])

    def shake(self, amount, duration):
        self.shake_amount = amount
        self.shake_timer = duration
    
    def flash(self, intensity=100):
        self.flash_alpha = intensity
    
    def spawn_particles(self, x, y, color, count=15, speed_mult=1.0):
        for _ in range(count):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(2.0, 8.0) * speed_mult
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.randint(30, 60)
            size = random.uniform(3, 7)
            self.particles.append([x, y, vx, vy, life, life, color, size])
    
    def spawn_trail(self, x, y, color):
        self.trail_particles.append([x, y, 20, 20, color, random.uniform(2, 4)])

    def update(self):
        if self.shake_timer > 0: self.shake_timer -= 1
        if self.flash_alpha > 0: self.flash_alpha = max(0, self.flash_alpha - 4)
        
        for p in self.particles[:]:
            p[0] += p[2]; p[1] += p[3]
            p[2] *= 0.92; p[3] *= 0.92
            p[4] -= 1; p[7] *= 0.96
            if p[4] <= 0: self.particles.remove(p)
        
        for p in self.ambient_particles:
            p[0] += p[2]
            p[1] += p[3]
            p[6] += 0.05
            p[0] += math.sin(p[6]) * 0.5
            
            if p[0] < -10: p[0] = WIDTH + 10
            if p[0] > WIDTH + 10: p[0] = -10
            if p[1] < -10: p[1] = HEIGHT + 10
        
        for p in self.trail_particles[:]:
            p[2] -= 1
            p[3] -= 1
            if p[2] <= 0: self.trail_particles.remove(p)

    def get_shake_offset(self):
        if self.shake_timer > 0:
            s = self.shake_amount * (self.shake_timer / 10) * ease_out_cubic(self.shake_timer/20)
            return random.uniform(-s, s), random.uniform(-s, s)
        return 0, 0

    def draw_particles(self, surf):
        for p in self.ambient_particles:
            x, y, _, _, color, size, _ = p
            alpha = int(100 + 50 * math.sin(p[6]))
            s = Surface((int(size*6), int(size*6)), SRCALPHA)
            glow_col = (*color, alpha)
            pygame.draw.circle(s, glow_col, (int(size*3), int(size*3)), int(size*3))
            surf.blit(s, (int(x - size*3), int(y - size*3)), special_flags=BLEND_ADD)
        
        for p in self.trail_particles:
            x, y, life, max_life, color, size = p
            alpha = int(150 * (life / max_life))
            s = Surface((int(size*4), int(size*4)), SRCALPHA)
            pygame.draw.circle(s, (*color, alpha), (int(size*2), int(size*2)), int(size*2))
            surf.blit(s, (int(x - size*2), int(y - size*2)), special_flags=BLEND_ADD)
        
        for p in self.particles:
            x, y, _, _, life, max_life, color, size = p
            alpha = int(255 * (life / max_life) * ease_out_cubic(life/max_life))
            if alpha < 5: continue
            
            pygame.draw.circle(surf, color, (int(x), int(y)), int(size/2))
            
            for i in range(3):
                s = Surface((int(size*(4+i)), int(size*(4+i))), SRCALPHA)
                glow_col = (*color, alpha//(3+i*2))
                radius = int(size*(1.5+i*0.5))
                pygame.draw.circle(s, glow_col, (radius, radius), radius)
                surf.blit(s, (int(x - radius), int(y - radius)), special_flags=BLEND_ADD)

    def draw_post_processing(self, surf):
        for y in range(0, HEIGHT, 3):
            pygame.draw.line(surf, (0, 0, 0, 40), (0, y), (WIDTH, y), 1)
        
        if self.flash_alpha > 0:
            flash = Surface((WIDTH, HEIGHT), SRCALPHA)
            flash.fill((255, 255, 255, int(self.flash_alpha)))
            surf.blit(flash, (0, 0), special_flags=BLEND_ADD)

# --- RENDERER ---
class NeonRenderer:
    def __init__(self):
        self.main_surf = Surface((WIDTH, HEIGHT))
        self.bloom_surf = Surface((WIDTH // 5, HEIGHT // 5), SRCALPHA)

        pygame.font.init()
        try:
            self.font_huge = pygame.font.SysFont('arial', 80, bold=True)
            self.font_big = pygame.font.SysFont('arial', 50, bold=True)
            self.font_med = pygame.font.SysFont('arial', 32)
            self.font_small = pygame.font.SysFont('arial', 22)
        except:
            self.font_huge = font.Font(None, 80)
            self.font_big = font.Font(None, 50)
            self.font_med = font.Font(None, 32)
            self.font_small = font.Font(None, 22)

        self.bg_offset = 0
        self.pulse = 0

    def draw_retro_grid(self, surf, t):
        surf.fill((12, 6, 24))
        self.bg_offset = (self.bg_offset + 0.5) % 60
        self.pulse = (self.pulse + 0.02) % (2 * math.pi)
        horizon = HEIGHT * 0.58
        cx = WIDTH // 2
        
        sun_pulse = ease_in_out_sin(math.sin(self.pulse)*0.5+0.5) * 15
        sun_size = 90 + sun_pulse
        pygame.draw.circle(surf, (255, 70, 120), (cx, int(horizon - 40)), int(sun_size))
        pygame.draw.circle(surf, (255, 150, 180), (cx, int(horizon - 40)), int(sun_size * 0.6))
        
        for i in range(-18, 19):
            x1 = cx + i * 30
            x2 = cx + i * 180
            pygame.draw.line(surf, (50, 0, 90), (x1, int(horizon)), (x2, HEIGHT), 1)
        
        for i in range(20):
            y = horizon + (i * 25 + self.bg_offset) * (i * 0.08 + 0.05)
            if y > HEIGHT: continue
            pygame.draw.line(surf, (80, 0, 140), (0, int(y)), (WIDTH, int(y)), 2)

    def draw_text(self, surf, text, x, y, font_obj, color, center=True, shadow=True):
        text = str(text)
        
        try:
            txt_surf = font_obj.render(text, True, color)
        except:
            txt_surf = pygame.font.Font(None, 40).render(text, True, color)
            
        rect = txt_surf.get_rect()
        if center: 
            rect.center = (int(x), int(y))
        else: 
            rect.topleft = (int(x), int(y))
        
        if shadow:
            try:
                shadow_surf = font_obj.render(text, True, (0, 0, 0))
                shadow_surf.set_alpha(150)
                surf.blit(shadow_surf, (rect.x + 2, rect.y + 2))
            except:
                pass
        
        surf.blit(txt_surf, rect)

    def render_frame(self, screen, client, vfx, t):
        self.draw_retro_grid(self.main_surf, t)
        
        trans_alpha = client.trans_anim
        
        if client.state_type == 'MENU':
            self.draw_menu(self.main_surf, client, trans_alpha, t)
        elif client.state_type == 'SHOP':
            self.draw_shop(self.main_surf, client, trans_alpha, t)
        elif client.state_type == 'GAME':
            self.draw_game(self.main_surf, client, trans_alpha, t)
            
        vfx.draw_particles(self.main_surf)

        scaled = pygame.transform.smoothscale(self.main_surf, (WIDTH // 5, HEIGHT // 5))
        bloom = pygame.transform.smoothscale(scaled, (WIDTH, HEIGHT))
        bloom.set_alpha(100)

        shake_x, shake_y = vfx.get_shake_offset()
        screen.blit(self.main_surf, (int(shake_x), int(shake_y)))
        screen.blit(bloom, (int(shake_x), int(shake_y)), special_flags=BLEND_ADD)
        vfx.draw_post_processing(screen)

    def draw_ui_box(self, surf, rect, color_bg, color_border, scale=1.0, glow_intensity=1.0):
        if scale <= 0: return
        
        w = int(rect.width * scale)
        h = int(rect.height * scale)
        cx, cy = rect.center
        scaled_rect = Rect(cx - w//2, cy - h//2, w, h)
        
        s_bg = Surface((w, h), SRCALPHA)
        bg_col = (*color_bg, 200)
        pygame.draw.rect(s_bg, bg_col, s_bg.get_rect(), border_radius=12)
        surf.blit(s_bg, scaled_rect.topleft)
        
        if color_border:
            pygame.draw.rect(surf, color_border, scaled_rect, 3, border_radius=12)
            
            for i in range(3):
                s_glow = Surface((w+20+i*10, h+20+i*10), SRCALPHA)
                glow_alpha = int(40 * glow_intensity / (i+1))
                glow_col = (*color_border, glow_alpha)
                pygame.draw.rect(s_glow, glow_col, Rect(10+i*5, 10+i*5, w, h), 3, border_radius=12)
                surf.blit(s_glow, (scaled_rect.x-10-i*5, scaled_rect.y-10-i*5), special_flags=BLEND_ADD)

    def draw_menu(self, surf, client, alpha, t):
        title_offset = ease_out_expo(alpha)
        title_y = 120 - int((1 - title_offset) * 100)
        
        if alpha < 1.0 and random.random() < 0.3:
            px = WIDTH//2 + random.uniform(-200, 200)
            py = title_y + random.uniform(-40, 40)
            client.vfx.spawn_particles(px, py, C_MAGENTA, 2, 0.5)
        
        title_rect = Rect(WIDTH//2-250, title_y-50, 500, 100)
        title_scale = ease_out_back(alpha)
        if title_scale > 0:
            w = int(title_rect.width * title_scale)
            h = int(title_rect.height * title_scale)
            cx, cy = title_rect.center
            scaled_title = Rect(cx - w//2, cy - h//2, w, h)
            
            s_bg = Surface((w, h), SRCALPHA)
            pygame.draw.rect(s_bg, (0, 0, 0, 200), s_bg.get_rect(), border_radius=12)
            surf.blit(s_bg, scaled_title.topleft)
            
            pygame.draw.rect(surf, C_MAGENTA, scaled_title, 3, border_radius=12)
            glow_pulse = 0.7 + 0.3 * math.sin(t * 2)
            for i in range(3):
                s_glow = Surface((w+30+i*10, h+30+i*10), SRCALPHA)
                glow_alpha = int(60 * glow_pulse / (i+1))
                pygame.draw.rect(s_glow, (*C_MAGENTA, glow_alpha), Rect(15+i*5, 15+i*5, w, h), 3, border_radius=12)
                surf.blit(s_glow, (scaled_title.x-15-i*5, scaled_title.y-15-i*5), special_flags=BLEND_ADD)
        
        self.draw_text(surf, "PING-PONG", WIDTH//2, title_y, self.font_huge, C_MAGENTA)
        
        status = "SERVER: CONNECTED" if client.connected else "SERVER: SEARCHING..."
        col = C_GREEN if client.connected else C_RED
        self.draw_text(surf, status, WIDTH//2, 200, self.font_small, col)
        
        if client.connected and random.random() < 0.1:
            client.vfx.spawn_particles(WIDTH//2, 200, C_GREEN, 1, 0.3)

        opts = ["START GAME", "ARMORY", "EXIT"]
        
        for i, txt in enumerate(opts):
            btn_anim = ease_out_back(min(1.0, max(0.0, alpha * 1.5 - i * 0.2)))
            y = 300 + i * 80
            is_sel = (i == client.menu_idx)
            
            scale = client.menu_anim_sizes[i] * btn_anim
            col_bg = (40, 20, 60) if is_sel else (20, 10, 30)
            col_border = C_CYAN if is_sel else (60, 30, 80)
            
            glow = 1.5 if is_sel else 1.0
            self.draw_ui_box(surf, Rect(WIDTH//2-200, y-35, 400, 70), col_bg, col_border, scale=scale, glow_intensity=glow)
            
            if is_sel and random.random() < 0.15:
                px = WIDTH//2 + random.uniform(-180, 180)
                py = y + random.uniform(-25, 25)
                client.vfx.spawn_trail(px, py, C_CYAN)
        
        for i, txt in enumerate(opts):
            btn_anim = ease_out_back(min(1.0, max(0.0, alpha * 1.5 - i * 0.2)))
            y = 300 + i * 80
            is_sel = (i == client.menu_idx)
            txt_col = C_WHITE if is_sel else (150, 150, 170)
            prefix = "> " if is_sel else ""
            suffix = " <" if is_sel else ""
            if btn_anim > 0:
                self.draw_text(surf, prefix + txt + suffix, WIDTH//2, y, self.font_big, txt_col)

        self.draw_text(surf, f"CREDITS: {client.profile.coins}", WIDTH-130, HEIGHT-30, self.font_med, C_GOLD)

    def draw_shop(self, surf, client, alpha, t):
        # 1. СТАТИЧНИЙ ТЕМНИЙ ФОН без анімації альфи (білий спалах виправлено!)
        overlay = Surface((WIDTH, HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(200)  # Тепер не залежить від alpha
        surf.blit(overlay, (0, 0))

        # Заголовок з плавною анімацією
        top_offset = ease_out_expo(alpha)
        top_y = 50 - int((1 - top_offset) * 50)
        
        self.draw_text(surf, "ARMORY", WIDTH//2, top_y, self.font_huge, C_CYAN)
        
        # Анімація переключення вкладок
        tab_anim = client.shop_tab_anim
        
        # Позиції для вкладок
        paddle_x = WIDTH//2 - 150
        ball_x = WIDTH//2 + 150
        
        # Інтерполяція між позиціями
        if client.shop_tab == 'paddle':
            current_x = paddle_x + (ball_x - paddle_x) * (1 - tab_anim)
        else:
            current_x = ball_x + (paddle_x - ball_x) * (1 - tab_anim)
        
        # Малюємо обидві вкладки
        paddle_alpha = tab_anim if client.shop_tab == 'paddle' else (1 - tab_anim)
        ball_alpha = tab_anim if client.shop_tab == 'ball' else (1 - tab_anim)
        
        paddle_scale = 1.0 + 0.2 * paddle_alpha
        ball_scale = 1.0 + 0.2 * ball_alpha
        
        # Фон для вкладок з анімацією
        tab_bg_rect = Rect(WIDTH//2 - 250, top_y + 40, 500, 50)
        s_tab_bg = Surface((500, 50), SRCALPHA)
        pygame.draw.rect(s_tab_bg, (20, 10, 40, 180), s_tab_bg.get_rect(), border_radius=8)
        surf.blit(s_tab_bg, tab_bg_rect.topleft)
        
        # Індикатор активної вкладки з плавним переміщенням
        indicator_width = 200
        indicator_x = current_x - indicator_width//2
        indicator_rect = Rect(int(indicator_x), top_y + 45, indicator_width, 40)
        
        # Gradient indicator з glow ефектом
        s_indicator = Surface((indicator_width, 40), SRCALPHA)
        pygame.draw.rect(s_indicator, (80, 40, 120, 220), s_indicator.get_rect(), border_radius=8)
        surf.blit(s_indicator, indicator_rect.topleft)
        
        # Додатковий glow для індикатора
        for i in range(2):
            s_glow = Surface((indicator_width + 20 + i*10, 40 + 20 + i*10), SRCALPHA)
            active_color = C_CYAN if client.shop_tab == 'paddle' else C_MAGENTA
            glow_alpha = int(80 / (i+1) * tab_anim)
            pygame.draw.rect(s_glow, (*active_color, glow_alpha), Rect(10+i*5, 10+i*5, indicator_width, 40), 3, border_radius=8)
            surf.blit(s_glow, (indicator_rect.x-10-i*5, indicator_rect.y-10-i*5), special_flags=BLEND_ADD)
        
        # Текст вкладок з масштабуванням
        paddle_font = self.font_med
        ball_font = self.font_med
        
        paddle_col = tuple(int(c * (0.5 + 0.5 * paddle_alpha)) for c in C_CYAN)
        ball_col = tuple(int(c * (0.5 + 0.5 * ball_alpha)) for c in C_MAGENTA)
        
        # Малюємо текст вкладок
        paddle_text = paddle_font.render("PADDLES", True, paddle_col)
        ball_text = ball_font.render("BALLS", True, ball_col)
        
        paddle_rect = paddle_text.get_rect(center=(paddle_x, top_y + 65))
        ball_rect = ball_text.get_rect(center=(ball_x, top_y + 65))
        
        surf.blit(paddle_text, paddle_rect)
        surf.blit(ball_text, ball_rect)

        # Список предметів з СИМЕТРИЧНОЮ анімацією
        skins = PADDLE_SKINS if client.shop_tab == 'paddle' else BALL_SKINS
        keys = list(skins.keys())
        start = int(client.shop_scroll)
        
        list_anim = client.shop_list_anim
        
        # 2. СИМЕТРИЧНА анімація карток — без позиційної затримки
        for i in range(start, min(start + 6, len(keys))):
            card_anim = ease_out_back(alpha)  # ПРОСТО альфа, без (i-start) * 0.15
            
            y = 180 + (i - start) * 70
            is_sel = (i == client.shop_idx)
            
            scale = client.shop_anim_sizes[min(i - start, 5)] * card_anim * list_anim
            
            col_bg = (50, 30, 70) if is_sel else (30, 20, 40)
            col_border = C_CYAN if is_sel else (70, 40, 90)
            
            rect = Rect(60, y, WIDTH-120, 60)
            self.draw_ui_box(surf, rect, col_bg, col_border, scale=scale)
        
        # Малюємо вміст карток
        for i in range(start, min(start + 6, len(keys))):
            card_anim = ease_out_back(alpha)  # ТЕПЕР СИМЕТРИЧНО!
            
            key = keys[i]
            item = skins[key]
            y = 180 + (i - start) * 70
            is_sel = (i == client.shop_idx)
            scale = client.shop_anim_sizes[min(i - start, 5)] * card_anim * list_anim
            
            if card_anim > 0 and list_anim > 0.1:
                # Прев'ю кольору
                preview_x = 100
                preview_y = y + 30
                pygame.draw.circle(surf, item['color'], (preview_x, preview_y), int(18 * scale))
                pygame.draw.circle(surf, C_WHITE, (preview_x, preview_y), int(18 * scale), 2)
                
                # Назва
                name_alpha = int(255 * list_anim)
                name_surf = self.font_small.render(item['name'], True, C_WHITE)
                name_surf.set_alpha(name_alpha)
                surf.blit(name_surf, (150, y + 20))
                
                # Статус
                if (client.shop_tab == 'paddle' and client.profile.paddle_skin == key) or \
                   (client.shop_tab == 'ball' and client.profile.ball_skin == key):
                    state = "EQUIPPED"
                    c = C_CYAN
                elif key in client.profile.owned:
                    state = "OWNED"
                    c = C_GREEN
                else:
                    state = f"{item['cost']} CR"
                    c = C_GOLD if client.profile.coins >= item['cost'] else C_RED
                
                status_surf = self.font_small.render(state, True, c)
                status_surf.set_alpha(name_alpha)
                status_rect = status_surf.get_rect()
                status_rect.right = WIDTH - 80
                status_rect.centery = y + 30
                surf.blit(status_surf, status_rect)

    def draw_game(self, surf, client, alpha, t):
        scores = client.game_data.get('scores', [0, 0])
        self.draw_text(surf, f"{scores[0]} : {scores[1]}", WIDTH//2, 50, self.font_big, C_WHITE)
        
        paddles = client.game_data.get('paddles', {})
        for i, pid in enumerate(['0', '1']):
            y = paddles.get(pid, 300)
            skin = client.profile.paddle_skin if i == client.pid else 'paddle_0'
            col = PADDLE_SKINS.get(skin, {'color': C_WHITE})['color']
            
            x = 20 if i == 0 else WIDTH - 40
            rect = Rect(x, y, 20, 100)
            pygame.draw.rect(surf, col, rect, border_radius=6)
            
            s = Surface((40, 120), SRCALPHA)
            glow_col = (*col, 100)
            pygame.draw.rect(s, glow_col, (0,0,40,120), border_radius=15)
            surf.blit(s, (rect.x-10, rect.y-10), special_flags=BLEND_ADD)

        ball = client.game_data.get('ball', {})
        bx, by = ball.get('x', WIDTH//2), ball.get('y', HEIGHT//2)
        
        if hasattr(client, 'last_ball'):
            lx, ly = client.last_ball
            for i in range(5):
                t_factor = 1 - i/5
                px = lx + (bx-lx)*t_factor
                py = ly + (by-ly)*t_factor
                trail_col = (*C_CYAN, int(100*t_factor))
                s = Surface((20, 20), SRCALPHA)
                pygame.draw.circle(s, trail_col, (10, 10), int(8*t_factor))
                surf.blit(s, (int(px-10), int(py-10)), special_flags=BLEND_ADD)

        skin = client.profile.ball_skin if client.pid == 0 else 'ball_0'
        b_col = BALL_SKINS.get(skin, {'color': C_CYAN})['color']
        pygame.draw.circle(surf, b_col, (int(bx), int(by)), 12)
        pygame.draw.circle(surf, C_WHITE, (int(bx), int(by)), 6)
        
        cd = client.game_data.get('countdown', 0)
        if cd > 0:
            self.draw_text(surf, str(int(cd)), WIDTH//2, HEIGHT//2, self.font_huge, C_GOLD)

        winner = client.game_data.get('winner')
        if winner is not None:
            end_overlay = Surface((WIDTH, HEIGHT))
            end_overlay.fill((0, 0, 0))
            end_overlay.set_alpha(180)
            surf.blit(end_overlay, (0, 0))
            
            txt = "VICTORY" if winner == client.pid else "DEFEAT"
            col = C_GOLD if winner == client.pid else C_RED
            self.draw_text(surf, txt, WIDTH//2, HEIGHT//2 - 40, self.font_huge, col)
            self.draw_text(surf, "PRESS SPACE", WIDTH//2, HEIGHT//2 + 60, self.font_small, C_WHITE)

# --- CLIENT ---
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
        self.menu_anim_sizes = [1.0, 1.0, 1.0]
        self.shop_tab = 'paddle'
        self.shop_idx = 0
        self.shop_scroll = 0
        self.shop_anim_sizes = [1.0]*6
        
        # Анімації для магазину
        self.shop_tab_anim = 1.0  # Анімація переключення вкладок (0->1)
        self.shop_list_anim = 1.0  # Анімація списку при зміні вкладки (0->1)
        self.shop_tab_target = 1.0
        self.shop_list_target = 1.0
        
        self.trans_anim = 1.0
        self.target_state = None

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
                    for line in data.split('\n'):
                        if line:
                            try:
                                ns = json.loads(line)
                                self.process_state(ns)
                                self.game_data = ns
                            except:
                                pass
                except BlockingIOError:
                    time.sleep(0.01)
                except:
                    self.connected = False

    def process_state(self, ns):
        if 'ball' in ns:
            nx, ny = ns['ball']['x'], ns['ball']['y']
            if ns.get('sound_event'):
                sound_hit.play()
                self.vfx.spawn_particles(nx, ny, C_CYAN, 15, 1.5)
                self.vfx.shake(8, 8)
            self.last_ball = (nx, ny)
        nsc = ns.get('scores', [0,0])
        osc = self.game_data.get('scores', [0,0])
        if nsc != osc:
            self.vfx.flash(100)
            self.vfx.shake(25, 20)
            if self.pid != -1 and nsc[self.pid] > osc[self.pid]:
                self.profile.coins += 20
                self.profile.save()

    def send_cmd(self, cmd):
        if self.connected and self.sock:
            try:
                self.sock.send(cmd.encode())
            except:
                self.connected = False

    def change_state(self, new_state):
        self.target_state = new_state
        
    def handle_input(self):
        keys = key.get_pressed()
        for e in event.get():
            if e.type == QUIT:
                self.running = False
            if e.type == KEYDOWN and self.trans_anim >= 0.95:
                if self.state_type == 'MENU':
                    if e.key in [K_UP, K_DOWN]:
                        old_idx = self.menu_idx
                        self.menu_idx = (self.menu_idx + (-1 if e.key==K_UP else 1)) % 3
                        sound_select.play()
                        y = 300 + self.menu_idx * 80
                        self.vfx.spawn_particles(WIDTH//2, y, C_CYAN, 20, 1.5)
                    if e.key == K_RETURN:
                        y = 300 + self.menu_idx * 80
                        self.vfx.spawn_particles(WIDTH//2, y, C_MAGENTA, 40, 2.5)
                        self.vfx.shake(8, 10)
                        self.vfx.flash(80)
                        if self.menu_idx == 0 and self.connected:
                            self.send_cmd("READY")
                            self.change_state('GAME')
                        elif self.menu_idx == 1:
                            self.change_state('SHOP')
                        elif self.menu_idx == 2:
                            self.running = False
                elif self.state_type == 'SHOP':
                    if e.key == K_ESCAPE:
                        self.vfx.spawn_particles(WIDTH//2, 100, C_CYAN, 30, 2.0)
                        self.change_state('MENU')
                    elif e.key in [K_LEFT, K_RIGHT]:
                        # Запускаємо анімацію переключення
                        old_tab = self.shop_tab
                        self.shop_tab = 'ball' if self.shop_tab == 'paddle' else 'paddle'
                        self.shop_idx = 0
                        self.shop_scroll = 0
                        
                        # Скидаємо анімації
                        self.shop_tab_target = 0.0
                        self.shop_list_target = 0.0
                        
                        sound_select.play()
                        self.vfx.spawn_particles(WIDTH//2, 110, random.choice([C_CYAN, C_MAGENTA]), 40, 2.5)
                        self.vfx.flash(60)
                        self.vfx.shake(6, 8)
                    elif e.key in [K_UP, K_DOWN]:
                        limit = len(PADDLE_SKINS) if self.shop_tab == 'paddle' else len(BALL_SKINS)
                        old_idx = self.shop_idx
                        self.shop_idx = max(0, min(limit-1, self.shop_idx + (-1 if e.key==K_UP else 1)))
                        if self.shop_idx < self.shop_scroll:
                            self.shop_scroll = self.shop_idx
                        if self.shop_idx >= self.shop_scroll + 6:
                            self.shop_scroll += 1
                        sound_select.play()
                        if old_idx != self.shop_idx:
                            y = 180 + (self.shop_idx - self.shop_scroll) * 70 + 30
                            self.vfx.spawn_particles(100, y, C_CYAN, 15, 1.0)
                    elif e.key == K_RETURN:
                        skins = PADDLE_SKINS if self.shop_tab == 'paddle' else BALL_SKINS
                        key_id = list(skins.keys())[self.shop_idx]
                        y = 180 + (self.shop_idx - self.shop_scroll) * 70 + 30
                        if key_id in self.profile.owned:
                            if self.shop_tab == 'paddle':
                                self.profile.paddle_skin = key_id
                            else:
                                self.profile.ball_skin = key_id
                            self.profile.save()
                            self.vfx.shake(5, 5)
                            self.vfx.spawn_particles(WIDTH//2, y, C_CYAN, 30, 2.0)
                        elif self.profile.buy(self.shop_tab, key_id):
                            self.vfx.flash(120)
                            self.vfx.shake(15, 15)
                            self.vfx.spawn_particles(WIDTH//2, HEIGHT//2, C_GOLD, 80, 4.0)
                            self.vfx.spawn_particles(WIDTH-130, HEIGHT-30, C_GOLD, 40, 3.0)
                elif self.state_type == 'GAME':
                    if e.key == K_SPACE and self.game_data.get('winner') is not None:
                        self.change_state('MENU')
                        self.game_data = {}
        
        if self.state_type == 'GAME' and self.connected:
            if keys[K_w] or keys[K_UP]:
                self.send_cmd("UP")
            if keys[K_s] or keys[K_DOWN]:
                self.send_cmd("DOWN")

    def update(self):
        if self.target_state:
            self.trans_anim -= 0.08
            if self.trans_anim <= 0:
                self.state_type = self.target_state
                self.target_state = None
                self.menu_anim_sizes = [0.8]*3
                self.shop_anim_sizes = [0.8]*6
        else:
            self.trans_anim = min(1.0, self.trans_anim + 0.08)

        # Анімація меню
        for i in range(3):
            target = 1.1 if i == self.menu_idx else 1.0
            self.menu_anim_sizes[i] += (target - self.menu_anim_sizes[i]) * 0.2
        
        # Анімація магазину
        for i in range(6):
            target = 1.05 if i == (self.shop_idx - self.shop_scroll) else 1.0
            self.shop_anim_sizes[i] += (target - self.shop_anim_sizes[i]) * 0.2
        
        # Плавна анімація переключення вкладок
        self.shop_tab_anim += (self.shop_tab_target - self.shop_tab_anim) * 0.15
        self.shop_list_anim += (self.shop_list_target - self.shop_list_anim) * 0.12
        
        # Коли анімація зникнення завершена, запускаємо анімацію появи
        if self.shop_list_anim < 0.05 and self.shop_list_target < 0.5:
            self.shop_list_target = 1.0
            self.shop_tab_target = 1.0

    def run(self):
        start_t = time.time()
        while self.running:
            self.handle_input()
            self.update()
            self.vfx.update()
            self.renderer.render_frame(screen, self, self.vfx, time.time() - start_t)
            display.flip()
            clock.tick(FPS)
        if self.sock:
            self.sock.close()
        pygame.quit()

if __name__ == "__main__":
    GameClient().run()