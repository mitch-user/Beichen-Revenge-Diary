# main.py (完整可覆蓋版本)
import os
import sys
import math
from typing import Any, Dict, List, Optional, Tuple

import pygame
import yaml

from minigames import MINIGAMES

# -------------------------
# PyInstaller / 資源路徑
# -------------------------
def resource_path(relative_path: str) -> str:
    """取得資源的絕對路徑（同時支援：原始碼執行 & PyInstaller 打包後執行）"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -------------------------
# 基本設定
# -------------------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# UI layout
DIALOGUE_H = int(SCREEN_H * 0.28)
DIALOGUE_RECT = pygame.Rect(50, SCREEN_H - DIALOGUE_H - 35, SCREEN_W - 100, DIALOGUE_H)
NAME_RECT = pygame.Rect(DIALOGUE_RECT.x, DIALOGUE_RECT.y - 45, 260, 40)
CHOICE_ITEM_H = 54

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (0, 0, 0, 160)

# 角色立繪顯示比例
CHAR_HEIGHT_RATIO = 0.82
CHAR_BOTTOM_PAD = 12

# 打字機效果
TYPE_SPEED_CHARS_PER_SEC = 40

# 角色跳動效果
BOUNCE_DURATION = 0.22
BOUNCE_HEIGHT = 14

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

    paragraphs = text.split("\n")
    for p_i, para in enumerate(paragraphs):
        if y > rect.y + max_h - font.get_height():
            break

        line = ""
        for ch in para:
            test = line + ch
            if font.size(test)[0] <= max_w:
                line = test
            else:
                img = font.render(line, True, color)
                surface.blit(img, (x, y))
                y += line_h
                if y > rect.y + max_h - font.get_height():
                    return
                line = ch

        if line:
            img = font.render(line, True, color)
            surface.blit(img, (x, y))
            y += line_h

        if p_i != len(paragraphs) - 1:
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
# BGM：只找 main_bgm（不管副檔名）
# -------------------------
def find_bgm_file(name_no_ext: str) -> Optional[str]:
    """
    會在以下位置找：
      - assets/bgm/main_bgm.(mp3/ogg/wav)
      - assets/audio/main_bgm.(mp3/ogg/wav)
    ※ 使用 resource_path 兼容打包
    """
    folders = [
        resource_path(os.path.join("assets", "bgm")),
        resource_path(os.path.join("assets", "audio")),
    ]
    exts = [".mp3", ".ogg", ".wav"]

    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for ext in exts:
            p = os.path.join(folder, name_no_ext + ext)
            if os.path.exists(p):
                return p
    return None

def try_start_bgm(volume: float) -> None:
    """
    封面開始播，進遊戲不換，循環播放
    """
    bgm_path = find_bgm_file("main_bgm")
    if not bgm_path:
        print("[提示] 找不到 BGM 檔案。請放在以下任一位置：")
        print(" -", resource_path(os.path.join("assets", "bgm", "main_bgm.mp3")))
        print(" -", resource_path(os.path.join("assets", "bgm", "main_bgm.ogg")))
        print(" -", resource_path(os.path.join("assets", "audio", "main_bgm.mp3")))
        print(" -", resource_path(os.path.join("assets", "audio", "main_bgm.ogg")))
        return

    try:
        pygame.mixer.music.load(bgm_path)
        pygame.mixer.music.set_volume(clamp(volume, 0.0, 1.0))
        pygame.mixer.music.play(-1)  # loop
        print("[BGM] 播放：", bgm_path)
    except Exception as e:
        print("[提示] BGM 播放失敗：", e)

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

        full = resource_path(os.path.join("assets", key))
        if not os.path.exists(full):
            raise FileNotFoundError(f"找不到圖片：{full}")

        img = pygame.image.load(full).convert_alpha()
        self._img[key] = img
        return img

    def image_fit_screen(self, rel_path: str) -> pygame.Surface:
        img = self.image(rel_path)
        return pygame.transform.smoothscale(img, (SCREEN_W, SCREEN_H))

# -------------------------
# 劇本
# -------------------------
class Script:
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
        if self.start_id not in self.nodes:
            raise ValueError(f"start id 不存在：{self.start_id}")

# -------------------------
# VN 引擎
# -------------------------
class VNEngine:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, assets: AssetManager, script: Script):
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

        self.current_chars: List[Dict[str, Any]] = []

        # typing
        self._full_text = ""
        self._shown_len = 0
        self._typing = False
        self._type_acc = 0.0

        # bounce
        self._bounce_name: Optional[str] = None
        self._bounce_t = 0.0

        # choice
        self.choice_active = False
        self.choice_prompt = ""
        self.choice_options: List[Dict[str, Any]] = []
        self.choice_hover = -1

        # missing warn
        self._missing_sprite_warn: Optional[str] = None
        self._missing_sprite_warn_t = 0.0

        # fade
        self.FADE_OUT_SEC = 0.28
        self.FADE_IN_SEC = 0.28

        # volume (0~1)
        self.master_volume = 0.5

    def _set_missing_warn(self, msg: str):
        self._missing_sprite_warn = msg
        self._missing_sprite_warn_t = 2.0

    # -------------------------
    # 封面 + 音量設定
    # -------------------------
    def _draw_button(self, rect: pygame.Rect, text: str, hover: bool):
        pygame.draw.rect(self.screen, (245, 245, 245) if hover else (220, 220, 228), rect, border_radius=16)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, width=2, border_radius=16)
        f = pygame.font.SysFont("Microsoft JhengHei", 22, bold=True)
        img = f.render(text, True, (25, 25, 30))
        self.screen.blit(img, img.get_rect(center=rect.center))

    def show_volume_screen(self) -> bool:
        """
        音量設定頁：調整 master_volume，立即套用到 pygame.mixer.music
        ESC / 返回 按鈕：回封面
        """
        W, H = self.screen.get_size()
        font_title = pygame.font.SysFont("Microsoft JhengHei", 40, bold=True)
        font_tip = pygame.font.SysFont("Microsoft JhengHei", 20)

        back_img = self.assets.image_fit_screen("bg/cover_main.png")

        panel = pygame.Rect(0, 0, 760, 360)
        panel.center = (W // 2, H // 2)

        # slider
        bar = pygame.Rect(0, 0, 520, 10)
        bar.center = (panel.centerx, panel.centery + 20)
        knob_r = 14

        btn_back = pygame.Rect(0, 0, 220, 52)
        btn_back.center = (panel.centerx, panel.bottom - 60)

        dragging = False

        def set_vol_from_mouse(mx: int):
            x = clamp(mx, bar.left, bar.right)
            t = (x - bar.left) / bar.width
            self.master_volume = float(clamp(t, 0.0, 1.0))
            pygame.mixer.music.set_volume(self.master_volume)

        while True:
            self.clock.tick(FPS)
            mx, my = pygame.mouse.get_pos()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return True
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if btn_back.collidepoint(mx, my):
                        return True
                    # knob hit
                    knob_x = int(bar.left + self.master_volume * bar.width)
                    if pygame.Rect(knob_x - knob_r, bar.centery - knob_r, knob_r * 2, knob_r * 2).collidepoint(mx, my):
                        dragging = True
                    elif bar.collidepoint(mx, my):
                        dragging = True
                        set_vol_from_mouse(mx)
                if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    dragging = False
                if e.type == pygame.MOUSEMOTION and dragging:
                    set_vol_from_mouse(mx)

            # draw
            self.screen.blit(back_img, (0, 0))
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 80))
            self.screen.blit(overlay, (0, 0))

            pygame.draw.rect(self.screen, (20, 20, 26), panel, border_radius=18)
            pygame.draw.rect(self.screen, (255, 255, 255), panel, width=2, border_radius=18)

            title = font_title.render("音量設定", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 70)))

            # bar
            pygame.draw.rect(self.screen, (255, 255, 255), bar, border_radius=8)
            fill = pygame.Rect(bar.left, bar.top, int(bar.width * self.master_volume), bar.height)
            pygame.draw.rect(self.screen, (245, 198, 75), fill, border_radius=8)

            knob_x = int(bar.left + self.master_volume * bar.width)
            pygame.draw.circle(self.screen, (245, 245, 245), (knob_x, bar.centery), knob_r)
            pygame.draw.circle(self.screen, (40, 40, 50), (knob_x, bar.centery), knob_r, 2)

            vol_text = font_tip.render(f"音量：{int(self.master_volume * 100)}%", True, (230, 230, 235))
            self.screen.blit(vol_text, vol_text.get_rect(center=(panel.centerx, bar.bottom + 35)))

            hover_back = btn_back.collidepoint(mx, my)
            self._draw_button(btn_back, "返回封面", hover_back)

            tip = font_tip.render("拖曳圓點或點擊白色音量條調整｜ESC 返回", True, (235, 235, 240))
            self.screen.blit(tip, tip.get_rect(center=(panel.centerx, panel.bottom - 20)))

            pygame.display.flip()

    def show_cover_screen(self) -> bool:
        """
        封面：兩顆按鈕
        - 開始遊戲
        - 音量設定
        需求調整：
        ✅ 兩個按鈕更近
        ✅ 整體往上移 0.2（螢幕高度 20%）
        """
        W, H = self.screen.get_size()
        cover_img = self.assets.image_fit_screen("bg/cover_main.png")
        tip_font = pygame.font.SysFont("Microsoft JhengHei", 16)

        # 按鈕：更小
        bw, bh = 240, 40
        btn_start = pygame.Rect(0, 0, bw, bh)
        btn_volume = pygame.Rect(0, 0, bw, bh)

        # ✅ 原本大概在 0.90H，現在「整體往上移 0.2H」
        base_y = int(H * 0.90) - int(H * 0.05)  # 往上移 20% 螢幕高度

        # ✅ 兩顆按鈕更近（間距縮小）
        gap = 5
        btn_start.center = (W // 2, base_y)
        btn_volume.center = (W // 2, base_y + bh + gap)

        while True:
            self.clock.tick(FPS)
            mx, my = pygame.mouse.get_pos()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return False
                    if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return True
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if btn_start.collidepoint(mx, my):
                        return True
                    if btn_volume.collidepoint(mx, my):
                        ok = self.show_volume_screen()
                        if not ok:
                            return False

            self.screen.blit(cover_img, (0, 0))
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 45))
            self.screen.blit(overlay, (0, 0))

            self._draw_button(btn_start, "點擊後進入遊戲", btn_start.collidepoint(mx, my))
            self._draw_button(btn_volume, "音量設定", btn_volume.collidepoint(mx, my))

            tip = tip_font.render("Enter / Space 也可開始｜ESC 離開", True, (235, 235, 240))
            self.screen.blit(tip, tip.get_rect(center=(W // 2, btn_volume.bottom + 20)))

            pygame.display.flip()

    # -------------------------
    # END 容錯
    # -------------------------
    def _set_virtual_end(self, text: str):
        self.script.nodes["__END__"] = {"id": "__END__", "type": "end", "text": text}

    def _resolve_bg_path_from_node(self, node: Dict[str, Any]) -> Optional[str]:
        bg_key = node.get("bg")
        if not bg_key:
            return None
        bg_key = str(bg_key)
        if "/" in bg_key or bg_key.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return bg_key.replace("\\", "/")
        return f"bg/{bg_key}.png"

    # -------------------------
    # 黑幕轉場
    # -------------------------
    def _fade_to_black(self, seconds: float) -> bool:
        t = 0.0
        while t < seconds:
            dt = self.clock.tick(FPS) / 1000.0
            t += dt

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return False

            self.draw()
            a = int(255 * min(1.0, t / seconds))
            overlay = pygame.Surface((SCREEN_W, SCREEN_H))
            overlay.fill((0, 0, 0))
            overlay.set_alpha(a)
            self.screen.blit(overlay, (0, 0))
            pygame.display.flip()
        return True

    def _fade_from_black(self, seconds: float) -> bool:
        t = 0.0
        while t < seconds:
            dt = self.clock.tick(FPS) / 1000.0
            t += dt

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return False

            self.draw()
            a = int(255 * max(0.0, 1.0 - (t / seconds)))
            overlay = pygame.Surface((SCREEN_W, SCREEN_H))
            overlay.fill((0, 0, 0))
            overlay.set_alpha(a)
            self.screen.blit(overlay, (0, 0))
            pygame.display.flip()
        return True

    def _go_to_node(self, node_id: str):
        if node_id not in self.script.nodes:
            if str(node_id).strip().upper() == "END":
                self._set_virtual_end("THE END（按 ESC 離開）")
                node_id = "__END__"
            else:
                raise KeyError(f"找不到節點：{node_id}")
        self.goto(node_id)
        self.next_step()

    def _transition_to_node(self, node_id: str, force: bool = False) -> bool:
        """
        - force=True：無論背景是否相同，都做轉場（進/出小遊戲用）
        - force=False：只有背景不同才做轉場（一般對話/場景切換）
        """
        target_id = node_id
        if target_id not in self.script.nodes:
            if str(target_id).strip().upper() == "END":
                self._set_virtual_end("THE END（按 ESC 離開）")
                target_id = "__END__"
            else:
                raise KeyError(f"找不到節點：{target_id}")

        cur_node = self.script.nodes[self.node_id]
        next_node = self.script.nodes[target_id]
        cur_bg = self._resolve_bg_path_from_node(cur_node)
        next_bg = self._resolve_bg_path_from_node(next_node)

        do_fade = force or (cur_bg != next_bg)
        if not do_fade:
            self._go_to_node(target_id)
            return True

        if not self._fade_to_black(self.FADE_OUT_SEC):
            return False
        self._go_to_node(target_id)
        if not self._fade_from_black(self.FADE_IN_SEC):
            return False
        return True

    # -------------------------
    # 狀態控制
    # -------------------------
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

        self._full_text = ""
        self._shown_len = 0
        self._typing = False
        self._type_acc = 0.0

        self._bounce_name = None
        self._bounce_t = 0.0

    def _start_typing(self, full_text: str):
        self._full_text = full_text
        self._shown_len = 0
        self._typing = True
        self._type_acc = 0.0
        self.current_text = ""

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

        self.current_chars = node.get("ch", []) or []

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

        # 小遊戲插入：進/出都做轉場
        if node.get("goto_minigame") is not None:
            if not self._fade_to_black(self.FADE_OUT_SEC):
                pygame.quit()
                sys.exit(0)

            mg_map = {1: "mg1", 2: "mg2", 3: "mg3"}
            mg_id = mg_map.get(int(node["goto_minigame"]))
            if not mg_id:
                raise ValueError(f"未知 goto_minigame：{node['goto_minigame']}（只支援 1/2/3）")

            # (小遊戲本身會處理 return True/False)
            _passed = MINIGAMES[mg_id].run(self.screen, self.clock, self.font_small)

            nxt = node.get("next")
            if nxt:
                ok = self._transition_to_node(str(nxt), force=True)
                if not ok:
                    pygame.quit()
                    sys.exit(0)
            else:
                self._fade_from_black(self.FADE_IN_SEC)
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
            self._start_typing("")
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
                ok = self._transition_to_node(str(jump), force=False)
                if not ok:
                    pygame.quit()
                    sys.exit(0)
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
        phase = (t / BOUNCE_DURATION) * math.pi
        return int(-math.sin(phase) * BOUNCE_HEIGHT)

    def draw(self):
        # background
        if self.bg_path:
            bg = self.assets.image_fit_screen(self.bg_path)
            self.screen.blit(bg, (0, 0))
        else:
            self.screen.fill((16, 18, 22))

        # characters
        for c in self.current_chars:
            try:
                name = str(c.get("name", "")).strip()
                if not name:
                    continue
                pos = str(c.get("pos", "center")).strip()
                exp = str(c.get("expression", "normal")).strip()

                sprite = self._draw_char_sprite(name, exp)

                target_h = int(SCREEN_H * CHAR_HEIGHT_RATIO)
                scale = target_h / sprite.get_height()
                target_w = int(sprite.get_width() * scale)
                sprite_s = pygame.transform.smoothscale(sprite, (target_w, target_h))

                x = self._char_pos_x(pos, target_w)
                y = SCREEN_H - target_h - CHAR_BOTTOM_PAD
                y += self._bounce_offset(name)

                self.screen.blit(sprite_s, (x, y))
            except FileNotFoundError as e:
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

        # missing warning
        if self._missing_sprite_warn and self._missing_sprite_warn_t > 0:
            warn_rect = pygame.Rect(16, 12, SCREEN_W - 32, 30)
            draw_text(
                self.screen,
                self.font_small,
                f"[缺立繪] {self._missing_sprite_warn}",
                (255, 140, 140),
                warn_rect,
                wrap=False,
            )

    def _advance(self) -> bool:
        if self._typing:
            self._finish_typing()
            return True

        cur = self.script.nodes[self.node_id]
        nxt = cur.get("next")
        if nxt:
            return self._transition_to_node(str(nxt), force=False)
        self.next_step()
        return True

    def run(self):
        print(">>> VNEngine.run start")

        # 封面（這裡已經在 main() 開始 BGM 了，所以封面會播）
        if not self.show_cover_screen():
            pygame.quit()
            return

        self.next_step()

        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

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
                        if not self._advance():
                            running = False
                elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.choice_active:
                        pass
                    else:
                        if not self._advance():
                            running = False

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

    # mixer
    try:
        pygame.mixer.init()
    except Exception as e:
        print("[提示] pygame.mixer.init 失敗：", e)

    pygame.display.set_caption("多媒體期末｜主遊戲（VN + 3 MiniGames）")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    # load script
    script_path = resource_path(os.path.join("story", "script_draft.yaml"))
    print(">>> loading yaml:", script_path)
    raw = load_yaml(script_path)
    script = Script(raw)
    print(">>> script loaded, nodes =", len(script.nodes), "start =", script.start_id)

    assets = AssetManager()
    engine = VNEngine(screen, clock, assets, script)

    # ✅ BGM：封面就播放，進遊戲不換，循環播放
    try_start_bgm(engine.master_volume)

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
