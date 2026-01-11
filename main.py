import os
import sys
import math
import random
from typing import Any, Dict, List, Optional, Tuple

import pygame
import yaml

from minigames import MINIGAMES

# -------------------------
# 基本設定
# -------------------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STORY_PATH = os.path.join(BASE_DIR, "story", "script_draft.yaml")

# UI layout
DIALOGUE_H = int(SCREEN_H * 0.28)
DIALOGUE_RECT = pygame.Rect(50, SCREEN_H - DIALOGUE_H - 35, SCREEN_W - 100, DIALOGUE_H)
NAME_RECT = pygame.Rect(DIALOGUE_RECT.x, DIALOGUE_RECT.y - 45, 260, 40)

CHOICE_ITEM_H = 54

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (0, 0, 0, 160)

# 角色立繪顯示比例（高度佔螢幕）
CHAR_HEIGHT_RATIO = 0.82
CHAR_BOTTOM_PAD = 12

# 打字機效果
TYPE_SPEED_CHARS_PER_SEC = 40  # 每秒顯示幾個字（可調快/慢）

# 角色跳動效果
BOUNCE_DURATION = 0.22  # 秒
BOUNCE_HEIGHT = 14      # 像素


# -------------------------
# 工具
# -------------------------
def clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))

def draw_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: Tuple[int, int, int],
    rect: pygame.Rect,
    wrap: bool = True,
    line_spacing: int = 4,
):
    """中英混排可用的自動換行（以字元為主），支援 \\n，不會畫出 rect 外"""
    if not wrap:
        img = font.render(text, True, color)
        surface.blit(img, (rect.x, rect.y))
        return

    x, y = rect.x, rect.y
    max_w = rect.w
    max_h = rect.h
    line_h = font.get_height() + line_spacing

    # 先用 \n 切段（保留手動換行）
    paragraphs = text.split("\n")

    for p_i, para in enumerate(paragraphs):
        if y > rect.y + max_h - font.get_height():
            break

        # 逐字組行（中文也 OK）
        line = ""
        for ch in para:
            test = line + ch
            if font.size(test)[0] <= max_w:
                line = test
            else:
                # 先畫目前這行
                img = font.render(line, True, color)
                surface.blit(img, (x, y))
                y += line_h
                if y > rect.y + max_h - font.get_height():
                    return
                line = ch

        # 段落最後一行
        if line:
            img = font.render(line, True, color)
            surface.blit(img, (x, y))
            y += line_h

        # 段落之間（原本的 \n）也算一個空行距
        if p_i != len(paragraphs) - 1:
            # 讓手動換行看起來有間距
            y += int(line_spacing * 0.5)



def load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到劇本檔：{path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError("YAML 最上層必須是 dict（例如 meta/nodes）")
    return raw


def safe_join(base: str, rel: str) -> str:
    rel = rel.replace("\\", "/").lstrip("/")
    return os.path.join(base, rel)

# -------------------------
# 資源管理（圖片快取）
# -------------------------
class AssetManager:
    def __init__(self):
        self._img: Dict[str, pygame.Surface] = {}

    def image(self, rel_path: str) -> pygame.Surface:
        """rel_path: 相對於 assets/ 的路徑，如 bg/room.png"""
        key = rel_path.replace("\\", "/")
        if key in self._img:
            return self._img[key]

        full = safe_join(ASSETS_DIR, key)
        if not os.path.exists(full):
            raise FileNotFoundError(f"找不到圖片：{full}")

        img = pygame.image.load(full).convert_alpha()
        self._img[key] = img
        return img

    def image_fit_screen(self, rel_path: str) -> pygame.Surface:
        img = self.image(rel_path)
        return pygame.transform.smoothscale(img, (SCREEN_W, SCREEN_H))

# -------------------------
# 劇本（nodes 格式）
# -------------------------
class Script:
    """
    YAML 格式：
    meta:
      start: CH1_001
    nodes:
      - id: CH1_001
        type: dialogue|choice|end
        bg: bedroom_bg
        speaker: NARRATOR
        text: "..."
        next: CH1_002
        choices:
          - text: "..."
            goto: CH2_001
        goto_minigame: 1|2|3
        ch:
          - name: 顧北辰
            pos: left|center|right
            expression: normal
    """

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.meta = raw.get("meta", {})
        nodes = raw.get("nodes")

        if not isinstance(nodes, list):
            raise ValueError("script_draft.yaml 必須有 nodes: 且為 list")

        self.nodes: Dict[str, Dict[str, Any]] = {}
        for n in nodes:
            if not isinstance(n, dict) or "id" not in n:
                raise ValueError(f"nodes 裡有項目缺少 id：{n}")
            self.nodes[str(n["id"])] = n

        self.start_id = str(self.meta.get("start") or (nodes[0].get("id") if nodes else ""))
        self.start_scene = self.start_id  # 相容舊名稱
        if self.start_id not in self.nodes:
            raise ValueError(f"start id 不存在：{self.start_id}")


# -------------------------
# 小遊戲（3 個）
# -------------------------
class MiniGameBase:
    name = "minigame"

    def run(self, screen: pygame.Surface, clock: pygame.time.Clock, font: pygame.font.Font) -> bool:
        raise NotImplementedError


class MiniGame1_ClickInTime(MiniGameBase):
    name = "mg1"

    def run(self, screen, clock, font):
        success = 0
        t = 0.0
        zone = pygame.Rect(SCREEN_W // 2 - 120, SCREEN_H // 2 - 14, 240, 28)
        bar = pygame.Rect(0, 0, 18, 60)
        bar.centery = zone.centery

        while True:
            dt = clock.tick(FPS) / 1000.0
            t += dt

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return False
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    if zone.left <= bar.centerx <= zone.right:
                        success += 1
                    else:
                        success = max(0, success - 1)
                    if success >= 3:
                        return True

            x = (math.sin(t * 2.2) * 0.45 + 0.5) * (SCREEN_W - 100) + 50
            bar.centerx = int(x)

            screen.fill((22, 22, 26))
            pygame.draw.rect(screen, (60, 60, 70), zone, border_radius=12)
            pygame.draw.rect(screen, (120, 220, 120), zone.inflate(-120, -6), border_radius=10)
            pygame.draw.rect(screen, (240, 240, 240), bar, border_radius=10)

            draw_text(
                screen,
                font,
                "小遊戲1：SPACE 在綠色區域｜成功 3 次過關｜ESC 放棄",
                WHITE,
                pygame.Rect(50, 60, SCREEN_W - 100, 40),
                wrap=False,
            )
            draw_text(
                screen,
                font,
                f"成功次數：{success}/3",
                WHITE,
                pygame.Rect(50, 110, SCREEN_W - 100, 40),
                wrap=False,
            )

            pygame.display.flip()


class MiniGame2_MemoryPairs(MiniGameBase):
    name = "mg2"

    def run(self, screen, clock, font):
        cols, rows = 4, 3
        total = cols * rows
        values = list(range(total // 2)) * 2
        random.shuffle(values)

        revealed = [False] * total
        matched = [False] * total
        first = None
        lock = 0.0
        pending_hide: Optional[Tuple[int, int]] = None

        pad = 16
        card_w = 150
        card_h = 110
        grid_w = cols * card_w + (cols - 1) * pad
        grid_h = rows * card_h + (rows - 1) * pad
        start_x = (SCREEN_W - grid_w) // 2
        start_y = (SCREEN_H - grid_h) // 2 + 40

        def idx_at(pos):
            mx, my = pos
            for r in range(rows):
                for c in range(cols):
                    x = start_x + c * (card_w + pad)
                    y = start_y + r * (card_h + pad)
                    rect = pygame.Rect(x, y, card_w, card_h)
                    if rect.collidepoint(mx, my):
                        return r * cols + c
            return None

        while True:
            dt = clock.tick(FPS) / 1000.0
            lock = max(0.0, lock - dt)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return False
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and lock <= 0:
                    i = idx_at(e.pos)
                    if i is None or matched[i] or revealed[i]:
                        continue
                    revealed[i] = True
                    if first is None:
                        first = i
                    else:
                        a, b = first, i
                        first = None
                        if values[a] == values[b]:
                            matched[a] = matched[b] = True
                        else:
                            lock = 0.7
                            pending_hide = (a, b)

            if pending_hide is not None and lock <= 0:
                a, b = pending_hide
                if not matched[a]:
                    revealed[a] = False
                if not matched[b]:
                    revealed[b] = False
                pending_hide = None

            if all(matched):
                return True

            screen.fill((18, 20, 26))
            draw_text(
                screen,
                font,
                "小遊戲2：翻牌配對｜全部完成過關｜ESC 放棄",
                WHITE,
                pygame.Rect(50, 60, SCREEN_W - 100, 40),
                wrap=False,
            )

            for r in range(rows):
                for c in range(cols):
                    i = r * cols + c
                    x = start_x + c * (card_w + pad)
                    y = start_y + r * (card_h + pad)
                    rect = pygame.Rect(x, y, card_w, card_h)

                    if matched[i]:
                        pygame.draw.rect(screen, (90, 170, 110), rect, border_radius=14)
                        draw_text(screen, font, f"✓{values[i]}", BLACK, rect.inflate(-16, -16))
                    elif revealed[i]:
                        pygame.draw.rect(screen, (230, 230, 240), rect, border_radius=14)
                        draw_text(screen, font, f"{values[i]}", BLACK, rect.inflate(-16, -16))
                    else:
                        pygame.draw.rect(screen, (70, 80, 95), rect, border_radius=14)

            pygame.display.flip()


class MiniGame3_Dodge(MiniGameBase):
    name = "mg3"

    def run(self, screen, clock, font):
        player = pygame.Rect(SCREEN_W // 2 - 18, SCREEN_H // 2 - 18, 36, 36)
        speed = 320
        enemies: List[pygame.Rect] = []
        enemy_speed = 240
        spawn_t = 0.0
        survive = 0.0
        target = 20.0

        while True:
            dt = clock.tick(FPS) / 1000.0
            survive += dt
            spawn_t += dt

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return False

            keys = pygame.key.get_pressed()
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            if dx and dy:
                norm = 1 / math.sqrt(2)
                dx *= norm
                dy *= norm
            player.x += int(dx * speed * dt)
            player.y += int(dy * speed * dt)
            player.x = int(clamp(player.x, 20, SCREEN_W - player.w - 20))
            player.y = int(clamp(player.y, 120, SCREEN_H - player.h - 20))

            if spawn_t >= 0.9:
                spawn_t = 0.0
                side = random.choice(["l", "r", "t", "b"])
                if side == "l":
                    rect = pygame.Rect(-40, random.randint(120, SCREEN_H - 40), 30, 30)
                elif side == "r":
                    rect = pygame.Rect(SCREEN_W + 10, random.randint(120, SCREEN_H - 40), 30, 30)
                elif side == "t":
                    rect = pygame.Rect(random.randint(0, SCREEN_W - 40), 80, 30, 30)
                else:
                    rect = pygame.Rect(random.randint(0, SCREEN_W - 40), SCREEN_H + 10, 30, 30)
                enemies.append(rect)

            for rect in enemies:
                vx = player.centerx - rect.centerx
                vy = player.centery - rect.centery
                dist = max(1.0, math.hypot(vx, vy))
                rect.x += int((vx / dist) * enemy_speed * dt)
                rect.y += int((vy / dist) * enemy_speed * dt)

            if any(player.colliderect(e) for e in enemies):
                return False

            if survive >= target:
                return True

            screen.fill((14, 18, 24))
            draw_text(
                screen,
                font,
                "小遊戲3：閃避生存｜撐到 20 秒過關｜ESC 放棄",
                WHITE,
                pygame.Rect(50, 60, SCREEN_W - 100, 40),
                wrap=False,
            )
            draw_text(
                screen,
                font,
                f"剩餘：{max(0.0, target - survive):.1f}s",
                WHITE,
                pygame.Rect(50, 100, SCREEN_W - 100, 40),
                wrap=False,
            )

            pygame.draw.rect(screen, (240, 240, 240), player, border_radius=10)
            for rect in enemies:
                pygame.draw.rect(screen, (220, 90, 90), rect, border_radius=8)

            pygame.display.flip()

# -------------------------
# VN 引擎
# -------------------------
class VNEngine:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, assets: "AssetManager", script: Script):
        self.screen = screen
        self.clock = clock
        self.assets = assets
        self.script = script

        self.font = pygame.font.SysFont("Microsoft JhengHei", 26)
        self.font_small = pygame.font.SysFont("Microsoft JhengHei", 22)
        self.font_name = pygame.font.SysFont("Microsoft JhengHei", 24, bold=True)

        self.node_id = script.start_id
        self.bg_path: Optional[str] = None

        self.current_name = ""
        self.current_text = ""
        self.waiting_input = False

        # 角色清單（從 YAML 的 ch: 取得）
        self.current_chars: List[Dict[str, Any]] = []

        # 打字機狀態
        self._full_text = ""
        self._shown_len = 0
        self._typing = False
        self._type_acc = 0.0  # time accumulator

        # 說話者跳動
        self._bounce_name: Optional[str] = None
        self._bounce_t = 0.0

        self.choice_active = False
        self.choice_prompt = ""
        self.choice_options: List[Dict[str, Any]] = []
        self.choice_hover = -1

        # 缺圖提示
        self._missing_sprite_warn: Optional[str] = None
        self._missing_sprite_warn_t = 0.0

    def _set_missing_warn(self, msg: str):
        self._missing_sprite_warn = msg
        self._missing_sprite_warn_t = 2.0  # 顯示 2 秒

    def goto(self, node_id: str):
        if node_id not in self.script.nodes:
            raise KeyError(f"找不到節點：{node_id}")
        self.node_id = node_id
        self.current_name = ""
        self.current_text = ""
        self.waiting_input = False
        self.choice_active = False
        self.choice_prompt = ""
        self.choice_options = []
        self.choice_hover = -1
        self.current_chars = []

        # reset typing
        self._full_text = ""
        self._shown_len = 0
        self._typing = False
        self._type_acc = 0.0

        # reset bounce
        self._bounce_name = None
        self._bounce_t = 0.0

    def _start_typing(self, full_text: str):
        self._full_text = full_text
        self._shown_len = 0
        self._typing = True
        self._type_acc = 0.0
        self.current_text = ""  # 畫面顯示用

    def _finish_typing(self):
        self._typing = False
        self._shown_len = len(self._full_text)
        self.current_text = self._full_text

    def _update_typing(self, dt: float):
        if not self._typing:
            return
        self._type_acc += dt
        add = int(self._type_acc * TYPE_SPEED_CHARS_PER_SEC)
        if add > 0:
            self._type_acc -= add / TYPE_SPEED_CHARS_PER_SEC
            self._shown_len = min(len(self._full_text), self._shown_len + add)
            self.current_text = self._full_text[: self._shown_len]
            if self._shown_len >= len(self._full_text):
                self._typing = False

    def _start_bounce_if_needed(self):
        """
        如果 speaker 在 current_chars 之中，觸發那個角色跳一下。
        """
        spk = (self.current_name or "").strip()
        if not spk or spk.upper() == "NARRATOR":
            self._bounce_name = None
            self._bounce_t = 0.0
            return

        for c in self.current_chars:
            if str(c.get("name", "")).strip() == spk:
                self._bounce_name = spk
                self._bounce_t = 0.0
                return

        self._bounce_name = None
        self._bounce_t = 0.0

    def next_step(self):
        node = self.script.nodes[self.node_id]
        t = str(node.get("type", "dialogue"))

        # 讀入角色列表
        self.current_chars = node.get("ch", []) or []

        # bg: bedroom_bg -> assets/bg/bedroom_bg.png
        bg_key = node.get("bg")
        if bg_key:
            bg_key = str(bg_key)
            if "/" in bg_key or bg_key.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                self.bg_path = bg_key
            else:
                self.bg_path = f"bg/{bg_key}.png"

        if t == "end":
            self.current_name = ""
            self._start_typing(str(node.get("text", "THE END（按 ESC 離開）")))
            self.waiting_input = True
            self.choice_active = False
            self._start_bounce_if_needed()
            return

        # 小遊戲插入（你的 goto_minigame: 1/2/3）
        if node.get("goto_minigame") is not None:
            mg_map = {1: "mg1", 2: "mg2", 3: "mg3"}
            mg_id = mg_map.get(int(node["goto_minigame"]))
            if not mg_id:
                raise ValueError(f"未知 goto_minigame：{node['goto_minigame']}（只支援 1/2/3）")

            _passed = MINIGAMES[mg_id].run(self.screen, self.clock, self.font_small)

            nxt = node.get("next")
            if nxt:
                self.goto(str(nxt))
                self.next_step()
            return

        if t == "dialogue":
            self.current_name = str(node.get("speaker", ""))
            self._start_typing(str(node.get("text", "")))
            self.waiting_input = True
            self.choice_active = False
            self._start_bounce_if_needed()
            return

        if t == "choice":
            self.current_name = str(node.get("speaker", ""))
            self.choice_prompt = str(node.get("text", "請選擇："))
            self.choice_options = node.get("choices", [])

            if not isinstance(self.choice_options, list) or len(self.choice_options) == 0:
                raise ValueError(f"choice 節點 {self.node_id} choices 必須是 list 且不可為空")

            for opt in self.choice_options:
                if "jump" not in opt and "goto" in opt:
                    opt["jump"] = opt["goto"]

            self.choice_active = True
            self.waiting_input = True

            # choice 也可以顯示提示文字（打字機）
            self._start_typing("")  # 不顯示對話文字，只留面板
            self._start_bounce_if_needed()
            return

        raise ValueError(f"不支援的節點 type：{t}（node id={self.node_id}）")

    def _choice_item_rects(self) -> List[pygame.Rect]:
        base_x = DIALOGUE_RECT.x
        base_y = DIALOGUE_RECT.y - (CHOICE_ITEM_H + 10) * len(self.choice_options) - 18
        return [
            pygame.Rect(base_x, base_y + i * (CHOICE_ITEM_H + 10), DIALOGUE_RECT.w, CHOICE_ITEM_H)
            for i in range(len(self.choice_options))
        ]

    def handle_choice_click(self, pos: Tuple[int, int]):
        if not self.choice_active:
            return
        for idx, rect in enumerate(self._choice_item_rects()):
            if rect.collidepoint(pos):
                jump = self.choice_options[idx].get("jump")
                if not jump:
                    raise ValueError("choice option 缺少 goto/jump")
                self.choice_active = False
                self.goto(str(jump))
                self.next_step()
                return

    def update_hover(self, pos: Tuple[int, int]):
        self.choice_hover = -1
        if not self.choice_active:
            return
        for i, rect in enumerate(self._choice_item_rects()):
            if rect.collidepoint(pos):
                self.choice_hover = i
                return

    def _draw_char_sprite(self, name: str, expression: str) -> pygame.Surface:
        # 圖片路徑：assets/ch/<name>/<expression>.png
        rel = f"ch/{name}/{expression}.png"
        return self.assets.image(rel)

    def _char_pos_x(self, pos: str, w: int) -> int:
        pos = (pos or "center").lower()
        if pos == "left":
            return int(SCREEN_W * 0.23 - w / 2)
        if pos == "right":
            return int(SCREEN_W * 0.77 - w / 2)
        return int(SCREEN_W * 0.50 - w / 2)

    def _bounce_offset(self, char_name: str) -> int:
        if not self._bounce_name or self._bounce_name != char_name:
            return 0
        t = self._bounce_t
        if t < 0 or t > BOUNCE_DURATION:
            return 0
        # 使用 sin 做「上去再回來」
        phase = (t / BOUNCE_DURATION) * math.pi
        return int(-math.sin(phase) * BOUNCE_HEIGHT)

    def draw(self):
        # background
        if self.bg_path:
            bg = self.assets.image_fit_screen(self.bg_path)
            self.screen.blit(bg, (0, 0))
        else:
            self.screen.fill((16, 18, 22))

        # 先畫角色（在 UI 之前）
        for c in self.current_chars:
            try:
                name = str(c.get("name", "")).strip()
                if not name:
                    continue
                pos = str(c.get("pos", "center")).strip()
                exp = str(c.get("expression", "normal")).strip()

                sprite = self._draw_char_sprite(name, exp)

                # scale to target height
                target_h = int(SCREEN_H * CHAR_HEIGHT_RATIO)
                scale = target_h / sprite.get_height()
                target_w = int(sprite.get_width() * scale)
                sprite_s = pygame.transform.smoothscale(sprite, (target_w, target_h))

                x = self._char_pos_x(pos, target_w)
                y = SCREEN_H - target_h - CHAR_BOTTOM_PAD

                # bounce if speaking
                y += self._bounce_offset(name)

                self.screen.blit(sprite_s, (x, y))

            except FileNotFoundError as e:
                # 顯示缺圖提示，不讓遊戲 crash
                self._set_missing_warn(str(e))

        # choice overlay
        if self.choice_active:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill(DIM)
            self.screen.blit(overlay, (0, 0))

            prompt_rect = pygame.Rect(
                DIALOGUE_RECT.x,
                DIALOGUE_RECT.y - 40 - (CHOICE_ITEM_H + 10) * len(self.choice_options) - 16,
                DIALOGUE_RECT.w,
                40,
            )
            draw_text(self.screen, self.font_name, self.choice_prompt, WHITE, prompt_rect, wrap=False)

            for i, rect in enumerate(self._choice_item_rects()):
                is_hover = (i == self.choice_hover)
                pygame.draw.rect(
                    self.screen,
                    (245, 245, 245) if is_hover else (220, 220, 225),
                    rect,
                    border_radius=14,
                )
                txt = str(self.choice_options[i].get("text", f"選項 {i+1}"))
                draw_text(self.screen, self.font, txt, BLACK, rect.inflate(-18, -12), wrap=False)

        # dialogue panel
        if self.waiting_input:
            panel = pygame.Surface((DIALOGUE_RECT.w, DIALOGUE_RECT.h), pygame.SRCALPHA)
            panel.fill((20, 20, 26, 190))
            self.screen.blit(panel, (DIALOGUE_RECT.x, DIALOGUE_RECT.y))
            pygame.draw.rect(self.screen, (255, 255, 255), DIALOGUE_RECT, width=2, border_radius=18)

            if self.current_name:
                name_panel = pygame.Surface((NAME_RECT.w, NAME_RECT.h), pygame.SRCALPHA)
                name_panel.fill((30, 30, 36, 210))
                self.screen.blit(name_panel, (NAME_RECT.x, NAME_RECT.y))
                pygame.draw.rect(self.screen, (255, 255, 255), NAME_RECT, width=2, border_radius=12)
                draw_text(self.screen, self.font_name, self.current_name, WHITE, NAME_RECT.inflate(-14, -10), wrap=False)

            text_rect = DIALOGUE_RECT.inflate(-20, -20)
            draw_text(self.screen, self.font, self.current_text, WHITE, text_rect, wrap=True)

            hint = "（左鍵 / Enter：若還在打字→直接顯示全文；否則→下一句｜ESC 離開）"
            draw_text(
                self.screen,
                self.font_small,
                hint,
                (200, 200, 200),
                pygame.Rect(DIALOGUE_RECT.x, DIALOGUE_RECT.bottom - 28, DIALOGUE_RECT.w, 24),
                wrap=False,
            )

        # 缺圖警告
        if self._missing_sprite_warn and self._missing_sprite_warn_t > 0:
            warn_rect = pygame.Rect(16, 12, SCREEN_W - 32, 30)
            draw_text(self.screen, self.font_small, f"[缺立繪] {self._missing_sprite_warn}", (255, 140, 140), warn_rect, wrap=False)

    def _advance(self):
        """
        推進：
        - 若還在打字：先把全文顯示
        - 否則：走 next
        """
        if self._typing:
            self._finish_typing()
            return

        cur = self.script.nodes[self.node_id]
        nxt = cur.get("next")
        if nxt:
            self.goto(str(nxt))
        self.next_step()

    def run(self):
        print(">>> VNEngine.run start")
        self.next_step()

        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            # update typing and bounce and warning timer
            self._update_typing(dt)
            if self._bounce_name:
                self._bounce_t += dt
                if self._bounce_t > BOUNCE_DURATION:
                    self._bounce_name = None
                    self._bounce_t = 0.0
            if self._missing_sprite_warn_t > 0:
                self._missing_sprite_warn_t = max(0.0, self._missing_sprite_warn_t - dt)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False
                elif e.type == pygame.MOUSEMOTION:
                    self.update_hover(e.pos)
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.choice_active:
                        self.handle_choice_click(e.pos)
                    else:
                        self._advance()
                elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.choice_active:
                        # choice 狀態下 Enter/Space 不做事，避免誤按
                        pass
                    else:
                        self._advance()

            self.draw()
            pygame.display.flip()

        pygame.quit()


# -------------------------
# main
# -------------------------
def main():
    print(">>> main() start")
    pygame.init()
    print(">>> pygame.init ok")

    pygame.display.set_caption("多媒體期末｜主遊戲（VN + 3 MiniGames）")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    print(">>> loading yaml:", STORY_PATH)
    raw = load_yaml(STORY_PATH)
    script = Script(raw)
    print(">>> script loaded, nodes =", len(script.nodes), "start =", script.start_id)

    assets = AssetManager()
    engine = VNEngine(screen, clock, assets, script)
    engine.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[錯誤] 程式執行失敗：")
        print(e)
        print("\n提示：")
        print("1) 確認 story/script_draft.yaml 是 meta + nodes 格式")
        print("2) 背景：bg: bedroom_bg → assets/bg/bedroom_bg.png（大小寫要一致）")
        print("3) 角色：ch/<角色>/<表情>.png（例如 ch/顧北辰/normal.png）")
        print("4) 如果看到 [缺立繪]，代表那張檔名或資料夾名稱不一致")
        raise
