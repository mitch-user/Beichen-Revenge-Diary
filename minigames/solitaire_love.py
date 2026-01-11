# minigames/solitaire_love.py
import sys
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

import pygame


SUITS = ["S", "H", "D", "C"]
SUIT_CHAR = {"S": "♠", "H": "♥", "D": "♦", "C": "♣", "J": "🃏"}
RANK_STR = {1: "A", 11: "J", 12: "Q", 13: "K"}


def is_red(suit: str) -> bool:
    return suit in ("H", "D")


@dataclass
class Card:
    rank: int
    suit: str
    face_up: bool = False

    @property
    def color_red(self) -> bool:
        if self.suit == "J":
            return False
        return is_red(self.suit)

    def label(self) -> str:
        if self.suit == "J":
            return "JOKER"
        return f"{RANK_STR.get(self.rank, str(self.rank))}{SUIT_CHAR[self.suit]}"


class SolitaireLoveGame:
    """
    mg3: 撲克牌接龍（Klondike 簡化版）
    ✅ 已移除 300 秒倒數限制（不會時間到失敗）
    """

    name = "mg3"

    def run(self, screen: pygame.Surface, clock: pygame.time.Clock, font: pygame.font.Font) -> bool:
        W, H = screen.get_size()
        FPS = 60

        # -------------------------
        # Scale: 1/2
        # -------------------------
        SCALE = 0.5
        BASE_CARD_W, BASE_CARD_H = 140, 190
        CARD_W = int(BASE_CARD_W * SCALE)
        CARD_H = int(BASE_CARD_H * SCALE)

        GAP_X = int(26 * SCALE)
        TOP_GAP_Y = int(26 * SCALE)
        TABLEAU_FACEUP_Y = int(40 * SCALE)
        TABLEAU_FACEDOWN_Y = int(22 * SCALE)

        MARGIN = 24
        TOP_UI_H = 92

        # -------------------------
        # Colors
        # -------------------------
        BG = (16, 18, 24)
        PANEL = (20, 22, 30)
        UI = (235, 235, 240)
        UI2 = (200, 200, 210)

        CARD_FACE = (245, 245, 250)
        CARD_BACK = (70, 85, 110)
        CARD_EDGE = (255, 255, 255)
        CARD_EDGE_DIM = (180, 180, 190)

        RED = (215, 65, 65)
        BLACK = (25, 25, 30)

        HINT_SRC = (245, 198, 75)
        HINT_DST = (120, 220, 120)

        BTN_BG = (230, 230, 238)
        BTN_BG_HOVER = (245, 245, 250)
        BTN_TXT = (25, 25, 30)

        # -------------------------
        # Fonts
        # -------------------------
        font_title = pygame.font.SysFont("Microsoft JhengHei", 28, bold=True)
        font_small = pygame.font.SysFont("Microsoft JhengHei", 18)
        font_mid = pygame.font.SysFont("Microsoft JhengHei", 22, bold=True)

        rank_font = pygame.font.SysFont("Microsoft JhengHei", max(16, int(26 * SCALE)), bold=True)
        suit_font = pygame.font.SysFont("Segoe UI Symbol", max(16, int(26 * SCALE)), bold=True)

        # -------------------------
        # Layout
        # -------------------------
        foundation_x = MARGIN
        foundation_y = TOP_UI_H
        foundation_rects = [
            pygame.Rect(foundation_x + i * (CARD_W + GAP_X), foundation_y, CARD_W, CARD_H)
            for i in range(4)
        ]

        tableau_y = TOP_UI_H + CARD_H + TOP_GAP_Y
        tableau_x0 = MARGIN
        tableau_rects = [
            pygame.Rect(tableau_x0 + i * (CARD_W + GAP_X), tableau_y, CARD_W, H - tableau_y - MARGIN)
            for i in range(7)
        ]

        stock_rect = pygame.Rect(W - MARGIN - CARD_W, TOP_UI_H, CARD_W, CARD_H)
        waste_rect = pygame.Rect(W - MARGIN - CARD_W * 2 - GAP_X, TOP_UI_H, CARD_W, CARD_H)

        BW, BH = 220, 52
        btn_joker = pygame.Rect(W - MARGIN - BW, H - MARGIN - BH, BW, BH)
        btn_reveal = pygame.Rect(W - MARGIN - BW, H - MARGIN - BH * 2 - 12, BW, BH)

        # -------------------------
        # Game State
        # -------------------------
        deck: List[Card] = [Card(rank=r, suit=s, face_up=False) for s in SUITS for r in range(1, 14)]
        random.shuffle(deck)

        tableau: List[List[Card]] = [[] for _ in range(7)]
        for i in range(7):
            for j in range(i + 1):
                c = deck.pop()
                c.face_up = (j == i)
                tableau[i].append(c)

        foundation: Dict[str, List[Card]] = {s: [] for s in SUITS}
        stock: List[Card] = deck[:]
        waste: List[Card] = []

        reveal_left = 2
        joker_left = 1
        hand_joker = 0

        selected_from: Optional[Tuple[str, int]] = None
        selected_index: int = -1
        selected_cards: List[Card] = []

        hint_timer = 0.0
        hint_src_rect: Optional[pygame.Rect] = None
        hint_dst_rect: Optional[pygame.Rect] = None
        hint_msg = ""

        toast_msg = ""
        toast_timer = 0.0

        hearts = 0

        # -------------------------
        # Helper
        # -------------------------
        def toast(msg: str, sec: float = 2.0):
            nonlocal toast_msg, toast_timer
            toast_msg = msg
            toast_timer = sec

        def draw_panel():
            top = pygame.Rect(0, 0, W, TOP_UI_H)
            pygame.draw.rect(screen, PANEL, top)
            pygame.draw.line(screen, (60, 60, 70), (0, TOP_UI_H - 1), (W, TOP_UI_H - 1), 2)

            # ✅ 標題也移除倒數字樣
            title = "第三關：追回林溪然（接龍）｜完成基礎牌堆（Foundation）｜ESC 離開"
            screen.blit(font_title.render(title, True, UI), (MARGIN, 14))

            info = f"Stock：{len(stock)}｜Waste：{len(waste)}"
            screen.blit(font_small.render(info, True, UI2), (MARGIN, 52))

            heart_str = "♥" * hearts + "□" * (4 - hearts)
            prog = f"好感度：{heart_str}  ({hearts * 25}%)"
            screen.blit(font_small.render(prog, True, (255, 180, 200)), (W - MARGIN - 260, 52))

            if toast_timer > 0 and toast_msg:
                screen.blit(font_small.render(toast_msg, True, (245, 215, 120)), (W - MARGIN - 520, 18))

        def draw_card(rect: pygame.Rect, card: Optional[Card], face_up: bool, selected: bool = False):
            if card is None:
                pygame.draw.rect(screen, (55, 60, 72), rect, width=2, border_radius=12)
                return

            if face_up:
                pygame.draw.rect(screen, CARD_FACE, rect, border_radius=12)
                pygame.draw.rect(screen, CARD_EDGE, rect, width=2, border_radius=12)

                if card.suit == "J":
                    txt = "J"
                    suit = "🃏"
                    col = (90, 80, 240)
                else:
                    txt = RANK_STR.get(card.rank, str(card.rank))
                    suit = SUIT_CHAR[card.suit]
                    col = RED if card.color_red else BLACK

                img_rank = rank_font.render(txt, True, col)
                img_suit = suit_font.render(suit, True, col)
                screen.blit(img_rank, (rect.x + 6, rect.y + 6))
                screen.blit(img_suit, (rect.x + 6, rect.y + 24))

                center_suit = suit_font.render(suit, True, col)
                screen.blit(center_suit, center_suit.get_rect(center=rect.center))
            else:
                pygame.draw.rect(screen, CARD_BACK, rect, border_radius=12)
                pygame.draw.rect(screen, CARD_EDGE_DIM, rect, width=2, border_radius=12)

            if selected:
                pygame.draw.rect(screen, (245, 198, 75), rect, width=4, border_radius=12)

        def top_foundation_card(suit: str) -> Optional[Card]:
            pile = foundation[suit]
            return pile[-1] if pile else None

        def can_move_to_foundation(card: Card) -> bool:
            if card.suit not in SUITS:
                return False
            pile = foundation[card.suit]
            if not pile:
                return card.rank == 1
            return pile[-1].rank + 1 == card.rank

        def can_place_on_tableau(moving: Card, target: Optional[Card]) -> bool:
            if target is None:
                return moving.rank == 13 or moving.suit == "J"
            if target.suit == "J":
                return True
            if moving.suit == "J":
                return True
            return (target.rank == moving.rank + 1) and (target.color_red != moving.color_red)

        def tableau_top_card(col: int) -> Optional[Card]:
            return tableau[col][-1] if tableau[col] else None

        def get_tableau_card_rect(col: int, idx: int) -> pygame.Rect:
            y = tableau_rects[col].y
            for k in range(idx):
                y += TABLEAU_FACEUP_Y if tableau[col][k].face_up else TABLEAU_FACEDOWN_Y
            return pygame.Rect(tableau_rects[col].x, y, CARD_W, CARD_H)

        def hit_test_tableau(pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
            x, y = pos
            for col in range(7):
                if not tableau_rects[col].collidepoint(x, y):
                    continue
                if not tableau[col]:
                    return (col, -1)
                for idx in range(len(tableau[col]) - 1, -1, -1):
                    r = get_tableau_card_rect(col, idx)
                    if r.collidepoint(x, y):
                        return (col, idx)
                return (col, len(tableau[col]) - 1)
            return None

        def draw_piles():
            for i, suit in enumerate(SUITS):
                rect = foundation_rects[i]
                top = top_foundation_card(suit)
                if top is None:
                    pygame.draw.rect(screen, (55, 60, 72), rect, width=2, border_radius=12)
                    s_img = suit_font.render(SUIT_CHAR[suit], True, (170, 170, 185))
                    screen.blit(s_img, s_img.get_rect(center=rect.center))
                else:
                    draw_card(rect, top, True)

            if stock:
                draw_card(stock_rect, stock[-1], False)
            else:
                pygame.draw.rect(screen, (55, 60, 72), stock_rect, width=2, border_radius=12)

            if waste:
                draw_card(waste_rect, waste[-1], True, selected=(selected_from == ("waste", 0)))
            else:
                pygame.draw.rect(screen, (55, 60, 72), waste_rect, width=2, border_radius=12)

            for col in range(7):
                base = pygame.Rect(tableau_rects[col].x, tableau_rects[col].y, CARD_W, CARD_H)
                pygame.draw.rect(screen, (40, 45, 55), base, width=2, border_radius=12)

                for idx, card in enumerate(tableau[col]):
                    r = get_tableau_card_rect(col, idx)
                    sel = (selected_from == ("tableau", col) and selected_index == idx)
                    draw_card(r, card, card.face_up, selected=sel)

        def draw_buttons():
            mx, my = pygame.mouse.get_pos()

            def btn(rect: pygame.Rect, text: str, enabled: bool):
                hover = rect.collidepoint(mx, my)
                bg = BTN_BG_HOVER if hover else BTN_BG
                if not enabled:
                    bg = (160, 160, 170)
                pygame.draw.rect(screen, bg, rect, border_radius=14)
                pygame.draw.rect(screen, (255, 255, 255), rect, width=2, border_radius=14)
                t = font_mid.render(text, True, BTN_TXT)
                screen.blit(t, t.get_rect(center=rect.center))

            btn(btn_reveal, f"回憶 Reveal x{reveal_left}", reveal_left > 0)
            joker_total = joker_left + hand_joker
            btn(btn_joker, f"勇氣 Joker x{joker_total}", joker_total > 0)

        def clear_selection():
            nonlocal selected_from, selected_index, selected_cards
            selected_from = None
            selected_index = -1
            selected_cards = []

        def flip_top_if_needed(col: int):
            if tableau[col] and not tableau[col][-1].face_up:
                tableau[col][-1].face_up = True

        def move_selected_to_foundation():
            nonlocal hearts
            if not selected_cards or len(selected_cards) != 1:
                return False
            card = selected_cards[0]
            if not can_move_to_foundation(card):
                return False

            if selected_from == ("waste", 0):
                waste.pop()
            elif selected_from and selected_from[0] == "tableau":
                col = selected_from[1]
                tableau[col].pop()
                flip_top_if_needed(col)
            else:
                return False

            foundation[card.suit].append(card)

            if len(foundation[card.suit]) == 13:
                hearts = min(4, hearts + 1)
                toast(f"完成一個花色！好感度 +25%（{hearts*25}%）", 2.5)

            clear_selection()
            return True

        def move_selected_to_tableau(dst_col: int):
            if not selected_cards:
                return False

            dst_top = tableau_top_card(dst_col)
            moving_first = selected_cards[0]
            if not can_place_on_tableau(moving_first, dst_top):
                return False

            if selected_from == ("waste", 0):
                card = waste.pop()
                tableau[dst_col].append(card)
            elif selected_from and selected_from[0] == "tableau":
                src_col = selected_from[1]
                run = tableau[src_col][selected_index:]
                tableau[src_col] = tableau[src_col][:selected_index]
                tableau[dst_col].extend(run)
                flip_top_if_needed(src_col)
            elif selected_from and selected_from[0] == "joker_hand":
                tableau[dst_col].append(Card(rank=0, suit="J", face_up=True))
            else:
                return False

            clear_selection()
            return True

        def click_stock():
            if stock:
                c = stock.pop()
                c.face_up = True
                waste.append(c)
            else:
                if waste:
                    while waste:
                        c = waste.pop()
                        c.face_up = False
                        stock.insert(0, c)
            clear_selection()

        def pick_selection_from_tableau(col: int, idx: int):
            if idx == -1:
                return
            card = tableau[col][idx]
            if not card.face_up:
                if idx == len(tableau[col]) - 1:
                    card.face_up = True
                    toast("翻開了一張牌", 1.2)
                return

            nonlocal selected_from, selected_index, selected_cards
            selected_from = ("tableau", col)
            selected_index = idx
            selected_cards = tableau[col][idx:]

        def use_reveal_hint():
            nonlocal reveal_left, hint_timer, hint_src_rect, hint_dst_rect, hint_msg
            if reveal_left <= 0:
                toast("沒有 Reveal 了", 1.5)
                return
            reveal_left -= 1

            candidates = []

            if waste:
                c = waste[-1]
                if can_move_to_foundation(c):
                    src = waste_rect
                    dst = foundation_rects[SUITS.index(c.suit)]
                    candidates.append((src, dst, "建議：把 Waste 放到 Foundation"))

            for col in range(7):
                if not tableau[col]:
                    continue
                top = tableau[col][-1]
                if top.face_up and can_move_to_foundation(top):
                    src = get_tableau_card_rect(col, len(tableau[col]) - 1)
                    dst = foundation_rects[SUITS.index(top.suit)]
                    candidates.append((src, dst, "建議：把 Tableau 放到 Foundation"))

            if waste:
                moving = waste[-1]
                for dst_col in range(7):
                    top = tableau_top_card(dst_col)
                    if can_place_on_tableau(moving, top):
                        src = waste_rect
                        dst = tableau_rects[dst_col].copy()
                        dst.height = CARD_H
                        candidates.append((src, dst, "建議：把 Waste 放到 Tableau"))
                        break

            for src_col in range(7):
                if not tableau[src_col]:
                    continue
                top = tableau[src_col][-1]
                if not top.face_up:
                    continue
                for dst_col in range(7):
                    if dst_col == src_col:
                        continue
                    dst_top = tableau_top_card(dst_col)
                    if can_place_on_tableau(top, dst_top):
                        src = get_tableau_card_rect(src_col, len(tableau[src_col]) - 1)
                        dst = tableau_rects[dst_col].copy()
                        dst.height = CARD_H
                        candidates.append((src, dst, "建議：移動一張牌到另一列"))
                        break
                if candidates:
                    break

            if candidates:
                src_r, dst_r, msg = candidates[0]
                hint_timer = 3.0
                hint_src_rect = src_r
                hint_dst_rect = dst_r
                hint_msg = msg
                toast("Reveal：已給出提示（看黃框/綠框）", 2.0)
            else:
                toast("Reveal：暫時找不到可行步", 2.0)

        def use_joker():
            nonlocal joker_left, hand_joker
            total = joker_left + hand_joker
            if total <= 0:
                toast("沒有 Joker 了", 1.5)
                return
            if joker_left > 0:
                joker_left -= 1
                hand_joker += 1
            toast("獲得 Joker：請點選任一列 Tableau 放置", 2.2)

        def try_place_joker_on_tableau(dst_col: int) -> bool:
            nonlocal hand_joker, selected_from, selected_cards, selected_index
            if hand_joker <= 0:
                return False
            hand_joker -= 1
            selected_from = ("joker_hand", 0)
            selected_cards = [Card(rank=0, suit="J", face_up=True)]
            selected_index = 0
            ok = move_selected_to_tableau(dst_col)
            if ok:
                toast("Joker 已放置！（任何牌都可接在 Joker 上）", 2.0)
            else:
                hand_joker += 1
                clear_selection()
            return ok

        def check_win() -> bool:
            return all(len(foundation[s]) == 13 for s in SUITS)

        def draw_hint():
            if hint_timer > 0 and hint_src_rect:
                pygame.draw.rect(screen, HINT_SRC, hint_src_rect.inflate(6, 6), width=4, border_radius=14)
            if hint_timer > 0 and hint_dst_rect:
                pygame.draw.rect(screen, HINT_DST, hint_dst_rect.inflate(6, 6), width=4, border_radius=14)
            if hint_timer > 0 and hint_msg:
                img = font_small.render(hint_msg, True, (245, 215, 120))
                screen.blit(img, (MARGIN, H - MARGIN - 24))

        def result_overlay() -> Optional[bool]:
            big = pygame.font.SysFont("Microsoft JhengHei", 52, bold=True)
            mid = pygame.font.SysFont("Microsoft JhengHei", 24, bold=True)
            small = pygame.font.SysFont("Microsoft JhengHei", 20)

            title = "成功！你追回了林溪然的心！"
            sub = "ESC：離開｜R：重來"

            bw, bh = 360, 64
            btn_proceed = pygame.Rect(0, 0, bw, bh)
            btn_restart = pygame.Rect(0, 0, bw, bh)
            btn_proceed.center = (W // 2, H // 2 + 60)
            btn_restart.center = (W // 2, H // 2 + 140)

            while True:
                clock.tick(FPS)
                mx, my = pygame.mouse.get_pos()

                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit(0)
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_ESCAPE:
                            return False
                        if e.key == pygame.K_r:
                            return None
                        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            return True
                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        if btn_proceed.collidepoint(mx, my):
                            return True
                        if btn_restart.collidepoint(mx, my):
                            return None

                overlay = pygame.Surface((W, H), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 165))
                screen.blit(overlay, (0, 0))

                t1 = big.render(title, True, UI)
                screen.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 80)))

                t2 = small.render(sub, True, (220, 220, 220))
                screen.blit(t2, t2.get_rect(center=(W // 2, H // 2 - 30)))

                def draw_btn(rect: pygame.Rect, text: str):
                    hover = rect.collidepoint(mx, my)
                    bg = (245, 245, 250) if hover else (230, 230, 238)
                    pygame.draw.rect(screen, bg, rect, border_radius=18)
                    pygame.draw.rect(screen, (255, 255, 255), rect, width=2, border_radius=18)
                    img = mid.render(text, True, (25, 25, 30))
                    screen.blit(img, img.get_rect(center=rect.center))

                draw_btn(btn_proceed, "進入第五章（Enter/Space）")
                draw_btn(btn_restart, "重新挑戰（R 或點擊）")

                pygame.display.flip()

        def reset_game():
            nonlocal deck, tableau, foundation, stock, waste
            nonlocal reveal_left, joker_left, hand_joker
            nonlocal selected_from, selected_index, selected_cards
            nonlocal hint_timer, hint_src_rect, hint_dst_rect, hint_msg
            nonlocal toast_msg, toast_timer
            nonlocal hearts

            deck = [Card(rank=r, suit=s, face_up=False) for s in SUITS for r in range(1, 14)]
            random.shuffle(deck)

            tableau = [[] for _ in range(7)]
            for i in range(7):
                for j in range(i + 1):
                    c = deck.pop()
                    c.face_up = (j == i)
                    tableau[i].append(c)

            foundation = {s: [] for s in SUITS}
            stock = deck[:]
            waste = []

            reveal_left = 2
            joker_left = 1
            hand_joker = 0

            selected_from = None
            selected_index = -1
            selected_cards = []

            hint_timer = 0.0
            hint_src_rect = None
            hint_dst_rect = None
            hint_msg = ""

            toast_msg = ""
            toast_timer = 0.0

            hearts = 0

        # -------------------------
        # Main loop
        # -------------------------
        while True:
            dt = clock.tick(FPS) / 1000.0
            if toast_timer > 0:
                toast_timer = max(0.0, toast_timer - dt)
            if hint_timer > 0:
                hint_timer = max(0.0, hint_timer - dt)
                if hint_timer <= 0:
                    hint_src_rect = None
                    hint_dst_rect = None
                    hint_msg = ""

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return False
                    if e.key == pygame.K_r:
                        reset_game()
                    if e.key == pygame.K_h:
                        use_reveal_hint()
                    if e.key == pygame.K_j:
                        use_joker()

                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    mx, my = e.pos

                    if btn_reveal.collidepoint(mx, my):
                        use_reveal_hint()
                        continue
                    if btn_joker.collidepoint(mx, my):
                        use_joker()
                        continue

                    if stock_rect.collidepoint(mx, my):
                        click_stock()
                        continue

                    for i, suit in enumerate(SUITS):
                        if foundation_rects[i].collidepoint(mx, my):
                            if selected_cards:
                                moved = move_selected_to_foundation()
                                if moved:
                                    toast("已放入 Foundation", 1.2)
                            clear_selection()
                            break
                    else:
                        if waste_rect.collidepoint(mx, my):
                            if waste:
                                selected_from = ("waste", 0)
                                selected_index = len(waste) - 1
                                selected_cards = [waste[-1]]
                            else:
                                clear_selection()
                            continue

                        hit = hit_test_tableau((mx, my))
                        if hit is None:
                            clear_selection()
                            continue

                        col, idx = hit

                        if hand_joker > 0:
                            if tableau_rects[col].collidepoint(mx, my):
                                try_place_joker_on_tableau(col)
                                continue

                        if selected_cards:
                            ok = move_selected_to_tableau(col)
                            if ok:
                                toast("移動成功", 1.0)
                            else:
                                clear_selection()
                                pick_selection_from_tableau(col, idx)
                            continue

                        pick_selection_from_tableau(col, idx)

            if check_win():
                res = result_overlay()
                if res is None:
                    reset_game()
                    continue
                return True if res else False

            screen.fill(BG)
            draw_panel()
            draw_piles()
            draw_hint()
            draw_buttons()
            pygame.display.flip()
