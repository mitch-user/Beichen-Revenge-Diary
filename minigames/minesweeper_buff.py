# minigames/minesweeper_buff.py
import sys
import random
from typing import List, Tuple, Optional, Set

import pygame


class MinesweeperBuffGame:
    name = "mg2"

    def run(self, screen: pygame.Surface, clock: pygame.time.Clock, font: pygame.font.Font) -> bool:
        W, H = screen.get_size()
        FPS = 60

        # -------------- config --------------
        COLS, ROWS = 10, 10
        BOMBS_INIT = 20
        LIVES_INIT = 3
        TIME_LIMIT = 150.0

        BUFF_REVEAL_BURIED = 2
        BUFF_BLAST_BURIED = 2

        PRESSURE_INTERVAL = 30.0  # 每 30 秒封鎖 1 格

        # Toast 時間規則
        TOAST_IMPORTANT = 5.0  # 踩雷、封鎖
        TOAST_NORMAL = 3.0     # 爆破 ON/OFF 等一般提示

        # ✅ 尾盤保護：剩下 <= N 個安全格未翻，就不再封鎖（避免死局）
        PRESSURE_DISABLE_SAFE_LEFT = 3

        # -------------- layout --------------
        TOP_UI_H = 110
        MARGIN = 40
        GRID_SIZE = min((W - MARGIN * 2) // COLS, (H - TOP_UI_H - MARGIN) // ROWS)
        board_w = GRID_SIZE * COLS
        board_h = GRID_SIZE * ROWS
        board_x = (W - board_w) // 2
        board_y = TOP_UI_H
        board_rect = pygame.Rect(board_x, board_y, board_w, board_h)

        # colors
        BG = (16, 18, 24)
        UI = (235, 235, 240)
        UI2 = (200, 200, 210)

        TILE_CLOSED = (65, 75, 92)
        TILE_OPEN = (215, 218, 225)
        TILE_FLAG = (245, 198, 75)

        BORDER = (45, 55, 70)
        FLASH = (255, 70, 70)

        LOCK_OVERLAY = (0, 0, 0, 100)
        LOCK_EDGE = (160, 90, 220)

        # fonts
        font_big = pygame.font.SysFont("Microsoft JhengHei", 42, bold=True)
        font_mid = pygame.font.SysFont("Microsoft JhengHei", 24, bold=True)
        font_small = pygame.font.SysFont("Microsoft JhengHei", 20)
        font_num = pygame.font.SysFont("Microsoft JhengHei", 26, bold=True)

        # -------------- helpers --------------
        def in_bounds(c: int, r: int) -> bool:
            return 0 <= c < COLS and 0 <= r < ROWS

        def rect_of(c: int, r: int) -> pygame.Rect:
            return pygame.Rect(board_x + c * GRID_SIZE, board_y + r * GRID_SIZE, GRID_SIZE, GRID_SIZE)

        def neighbors8(c: int, r: int):
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if dc == 0 and dr == 0:
                        continue
                    nc, nr = c + dc, r + dr
                    if in_bounds(nc, nr):
                        yield nc, nr

        def toast(msg: str, seconds: float):
            nonlocal toast_msg, toast_t
            toast_msg = msg
            toast_t = seconds

        def recompute_numbers():
            # 只看目前還存在的炸彈
            for rr in range(ROWS):
                for cc in range(COLS):
                    if (cc, rr) in bombs_current:
                        numbers[rr][cc] = -1
                    else:
                        cnt = 0
                        for nc, nr in neighbors8(cc, rr):
                            if (nc, nr) in bombs_current:
                                cnt += 1
                        numbers[rr][cc] = cnt

        def spawn_bombs(first_click: Optional[Tuple[int, int]] = None):
            forbidden: Set[Tuple[int, int]] = set()
            if first_click is not None:
                fc, fr = first_click
                forbidden.add((fc, fr))
                for nc, nr in neighbors8(fc, fr):
                    forbidden.add((nc, nr))

            pool = [(c, r) for r in range(ROWS) for c in range(COLS) if (c, r) not in forbidden]
            random.shuffle(pool)
            return set(pool[:BOMBS_INIT])

        def pick_buff_cells():
            safe = [(c, r) for r in range(ROWS) for c in range(COLS) if (c, r) not in bombs_current]
            random.shuffle(safe)
            reveal_cells = set(safe[:BUFF_REVEAL_BURIED])
            rest = [x for x in safe if x not in reveal_cells]
            blast_cells = set(rest[:BUFF_BLAST_BURIED])
            return reveal_cells, blast_cells

        def collect_buff(c: int, r: int):
            nonlocal reveal_left, blast_left
            pos = (c, r)

            if pos in buff_reveal_cells:
                buff_reveal_cells.remove(pos)
                reveal_left += 1
                toast("獲得 Buff：透視 +1（自動插旗一顆炸彈）", TOAST_NORMAL)
                use_reveal(auto=True)

            elif pos in buff_blast_cells:
                buff_blast_cells.remove(pos)
                blast_left += 1
                toast("獲得 Buff：爆破 +1（Space 切換爆破模式）", TOAST_NORMAL)

        def flood_open(start_c: int, start_r: int):
            stack = [(start_c, start_r)]
            while stack:
                c, r = stack.pop()
                if opened[r][c]:
                    continue
                if flagged[r][c]:
                    continue
                if locked_cell is not None and (c, r) == locked_cell:
                    continue

                opened[r][c] = True
                collect_buff(c, r)

                if numbers[r][c] == 0:
                    for nc, nr in neighbors8(c, r):
                        if not opened[nr][nc] and not flagged[nr][nc]:
                            if locked_cell is not None and (nc, nr) == locked_cell:
                                continue
                            if (nc, nr) not in bombs_current:
                                stack.append((nc, nr))

        def use_reveal(auto: bool = False):
            nonlocal reveal_left
            if reveal_left <= 0:
                if not auto:
                    toast("沒有透視 Buff", TOAST_NORMAL)
                return

            candidates = [
                p for p in bombs_current
                if not flagged[p[1]][p[0]]
                and not opened[p[1]][p[0]]
                and (locked_cell is None or p != locked_cell)
            ]
            if not candidates:
                return
            c, r = random.choice(candidates)
            flagged[r][c] = True
            reveal_left -= 1
            toast("透視：已自動插旗一顆炸彈", TOAST_NORMAL)

        def blast_cross(center: Tuple[int, int]):
            nonlocal blast_left, flash_t, blast_mode
            if blast_left <= 0:
                toast("沒有爆破 Buff", TOAST_NORMAL)
                return

            c0, r0 = center
            cross = [(c0, r0), (c0 - 1, r0), (c0 + 1, r0), (c0, r0 - 1), (c0, r0 + 1)]
            valid = [(c, r) for (c, r) in cross if in_bounds(c, r)]

            if locked_cell is not None and locked_cell in valid:
                toast("封鎖格無法被爆破！", TOAST_IMPORTANT)
                return

            blast_left -= 1
            blast_mode = False

            removed_any = False
            for c, r in valid:
                if (c, r) in bombs_current:
                    bombs_current.remove((c, r))
                    bombs_defused.add((c, r))
                    removed_any = True
                    opened[r][c] = True
                    flagged[r][c] = False

            if removed_any:
                recompute_numbers()

            for c, r in valid:
                if flagged[r][c]:
                    continue
                if (c, r) in bombs_current:
                    continue
                if not opened[r][c]:
                    if numbers[r][c] == 0:
                        flood_open(c, r)
                    else:
                        opened[r][c] = True
                        collect_buff(c, r)

            toast("爆破：十字展開！（炸彈已拆除不扣命）", TOAST_NORMAL)
            flash_t = max(flash_t, 0.12)

        def opened_safe_count() -> int:
            cnt = 0
            for r in range(ROWS):
                for c in range(COLS):
                    if opened[r][c] and (c, r) not in bombs_current:
                        cnt += 1
            return cnt

        def total_safe_cells() -> int:
            return COLS * ROWS - len(bombs_current)

        def safe_left_unopened() -> int:
            """剩下還沒翻開的安全格數量（用於尾盤不封鎖）"""
            left = 0
            for r in range(ROWS):
                for c in range(COLS):
                    if opened[r][c]:
                        continue
                    if (c, r) in bombs_current:
                        continue
                    left += 1
            return left

        def list_unopened_safe_cells() -> List[Tuple[int, int]]:
            cells = []
            for r in range(ROWS):
                for c in range(COLS):
                    if opened[r][c]:
                        continue
                    if flagged[r][c]:
                        continue
                    if (c, r) in bombs_current:
                        continue
                    cells.append((c, r))
            return cells

        def draw_bomb_icon(rect: pygame.Rect):
            cx, cy = rect.center
            radius = int(min(rect.w, rect.h) * 0.22)
            pygame.draw.circle(screen, (20, 20, 25), (cx, cy + 2), radius)
            pygame.draw.line(screen, (20, 20, 25), (cx + radius - 2, cy - radius + 2), (cx + radius + 10, cy - radius - 10), 3)
            pygame.draw.circle(screen, (255, 120, 120), (cx + radius + 12, cy - radius - 12), 4)

        def draw_lock_icon(rect: pygame.Rect):
            cx, cy = rect.center
            body = pygame.Rect(0, 0, int(rect.w * 0.38), int(rect.h * 0.32))
            body.center = (cx, cy + int(rect.h * 0.06))
            pygame.draw.rect(screen, (235, 235, 245), body, border_radius=6)
            arc = pygame.Rect(0, 0, int(rect.w * 0.34), int(rect.h * 0.34))
            arc.center = (cx, cy - int(rect.h * 0.03))
            pygame.draw.arc(screen, (235, 235, 245), arc, 3.45, 5.97, 4)

        def draw_top_ui(time_left: float):
            top = pygame.Rect(0, 0, W, TOP_UI_H)
            pygame.draw.rect(screen, (20, 22, 30), top)
            pygame.draw.line(screen, (60, 60, 70), (0, TOP_UI_H - 1), (W, TOP_UI_H - 1), 2)

            title = "小遊戲2：顧老爺的挑戰（踩地雷）"
            screen.blit(font_mid.render(title, True, UI), (MARGIN, 16))

            status = (
                f"命：{lives}/{LIVES_INIT}   炸彈剩餘：{len(bombs_current)}   "
                f"已翻：{opened_safe_count()}/{total_safe_cells()}   倒數：{max(0.0, time_left):.1f}s"
            )
            screen.blit(font_small.render(status, True, UI2), (MARGIN, 52))

            buff = f"Buff｜透視：{reveal_left}   爆破：{blast_left}   爆破模式：{'ON' if blast_mode else 'OFF'}（Space）"
            screen.blit(font_small.render(buff, True, UI2), (MARGIN, 76))

            if started:
                next_in = max(0.0, PRESSURE_INTERVAL - (pressure_elapsed % PRESSURE_INTERVAL))
                lock_msg = "封鎖格：無" if locked_cell is None else f"封鎖格：({locked_cell[0]+1},{locked_cell[1]+1})"
                msg = f"顧老爺壓力：{lock_msg}｜下次封鎖：{next_in:.0f}s"
                screen.blit(font_small.render(msg, True, (210, 180, 255)), (W - MARGIN - 420, 52))

            if toast_t > 0 and toast_msg:
                screen.blit(font_small.render(toast_msg, True, (245, 215, 120)), (W - MARGIN - 520, 76))

        def draw_board():
            pygame.draw.rect(screen, BORDER, board_rect, width=3, border_radius=10)

            for r in range(ROWS):
                for c in range(COLS):
                    rect = rect_of(c, r).inflate(-2, -2)

                    if opened[r][c]:
                        pygame.draw.rect(screen, TILE_OPEN, rect, border_radius=6)

                        pos = (c, r)
                        if pos in bombs_all and (pos in bombs_triggered or pos in bombs_defused):
                            draw_bomb_icon(rect)
                        else:
                            n = numbers[r][c]
                            if n > 0:
                                img = font_num.render(str(n), True, (30, 30, 36))
                                screen.blit(img, img.get_rect(center=rect.center))
                    else:
                        pygame.draw.rect(screen, TILE_CLOSED, rect, border_radius=6)
                        if flagged[r][c]:
                            pygame.draw.rect(screen, TILE_FLAG, rect.inflate(-12, -12), border_radius=6)

                    if locked_cell is not None and (c, r) == locked_cell:
                        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                        overlay.fill(LOCK_OVERLAY)
                        screen.blit(overlay, rect.topleft)
                        pygame.draw.rect(screen, LOCK_EDGE, rect, width=3, border_radius=6)
                        draw_lock_icon(rect)

            if flash_t > 0:
                overlay = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
                overlay.fill((FLASH[0], FLASH[1], FLASH[2], 70))
                screen.blit(overlay, (board_x, board_y))

        def countdown(seconds: int = 3) -> bool:
            start = pygame.time.get_ticks()
            total_ms = seconds * 1000
            big = pygame.font.SysFont("Microsoft JhengHei", 110, bold=True)

            while True:
                clock.tick(FPS)
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit(0)

                keys = pygame.key.get_pressed()
                if keys[pygame.K_ESCAPE]:
                    return False

                elapsed = pygame.time.get_ticks() - start
                remain_ms = max(0, total_ms - elapsed)
                remain_s = (remain_ms + 999) // 1000

                screen.fill(BG)
                draw_top_ui(TIME_LIMIT)
                draw_board()

                txt = str(remain_s) if remain_s > 0 else "GO!"
                img = big.render(txt, True, UI)
                screen.blit(img, img.get_rect(center=(W // 2, H // 2)))
                pygame.display.flip()

                if elapsed >= total_ms:
                    return True

        def button(surface, rect: pygame.Rect, text: str, hover: bool):
            pygame.draw.rect(surface, (240, 240, 245) if hover else (220, 220, 228), rect, border_radius=16)
            pygame.draw.rect(surface, (255, 255, 255), rect, width=2, border_radius=16)
            t = font_mid.render(text, True, (25, 25, 30))
            surface.blit(t, t.get_rect(center=rect.center))

        def result_screen(win: bool) -> Optional[str]:
            title = "勝利！顧老爺認可你的實力！" if win else "失敗！你沒能通過考驗！"
            sub = "ESC：離開"

            bw, bh = 320, 62
            b1 = pygame.Rect(0, 0, bw, bh)
            b2 = pygame.Rect(0, 0, bw, bh)

            if win:
                b1.center = (W // 2, H // 2 + 40)
                b2.center = (W // 2, H // 2 + 120)
            else:
                b1.center = (W // 2, H // 2 + 70)
                b2 = None

            while True:
                clock.tick(FPS)
                mx, my = pygame.mouse.get_pos()

                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit(0)
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_ESCAPE:
                            return None
                        if win and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            return "proceed"
                        if e.key == pygame.K_r:
                            return "restart"
                        if (not win) and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            return "restart"
                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        if win:
                            if b1.collidepoint(mx, my):
                                return "proceed"
                            if b2 and b2.collidepoint(mx, my):
                                return "restart"
                        else:
                            if b1.collidepoint(mx, my):
                                return "restart"

                overlay = pygame.Surface((W, H), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                screen.blit(overlay, (0, 0))

                t1 = font_big.render(title, True, UI)
                screen.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 70)))

                t2 = font_small.render(sub, True, (220, 220, 220))
                screen.blit(t2, t2.get_rect(center=(W // 2, H // 2 - 25)))

                if win:
                    hover1 = b1.collidepoint(mx, my)
                    hover2 = b2.collidepoint(mx, my) if b2 else False
                    button(screen, b1, "進入第四章", hover1)
                    if b2:
                        button(screen, b2, "R：重來", hover2)

                    tip = "提示：Enter/Space 也可直接進入第四章"
                    tip_img = font_small.render(tip, True, (210, 210, 220))
                    screen.blit(tip_img, tip_img.get_rect(center=(W // 2, H // 2 + 190)))
                else:
                    hover1 = b1.collidepoint(mx, my)
                    button(screen, b1, "Enter：重來", hover1)

                pygame.display.flip()

        def pos_to_cell(pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
            x, y = pos
            if not board_rect.collidepoint(x, y):
                return None
            c = (x - board_x) // GRID_SIZE
            r = (y - board_y) // GRID_SIZE
            return int(c), int(r)

        # -------------- state --------------
        opened: List[List[bool]] = [[False] * COLS for _ in range(ROWS)]
        flagged: List[List[bool]] = [[False] * COLS for _ in range(ROWS)]
        numbers: List[List[int]] = [[0] * COLS for _ in range(ROWS)]

        bombs_current: Set[Tuple[int, int]] = set()
        bombs_all: Set[Tuple[int, int]] = set()
        bombs_defused: Set[Tuple[int, int]] = set()
        bombs_triggered: Set[Tuple[int, int]] = set()

        buff_reveal_cells: Set[Tuple[int, int]] = set()
        buff_blast_cells: Set[Tuple[int, int]] = set()

        lives = LIVES_INIT
        time_left = TIME_LIMIT
        started = False
        blast_mode = False

        reveal_left = 0
        blast_left = 0

        toast_msg = ""
        toast_t = 0.0
        flash_t = 0.0

        locked_cell: Optional[Tuple[int, int]] = None
        pressure_elapsed = 0.0
        next_pressure_at = PRESSURE_INTERVAL

        def pick_locked_cell():
            """
            ✅ 防死局版本：
            - 基本條件：未翻開、未插旗
            - 不挑：炸彈格
            - 不挑：最後那顆(或少數幾顆)未翻安全格（避免最後被鎖死）
            """
            # 尾盤：剩太少安全格，直接不要封鎖
            if safe_left_unopened() <= PRESSURE_DISABLE_SAFE_LEFT:
                return None

            unopened_safe = list_unopened_safe_cells()
            # 若剛好只剩 1 個安全格，直接不封鎖（保底）
            if len(unopened_safe) <= 1:
                return None

            # 這裡保護「最後一顆安全格」：不列入候選
            protected = set()
            if len(unopened_safe) == 2:
                # 只剩 2 顆時也別陰人：保護其中 1 顆（隨機）
                protected.add(random.choice(unopened_safe))
            else:
                # 一般情況：保護其中 1 顆（避免最後被封）
                protected.add(random.choice(unopened_safe))

            candidates = [
                (c, r)
                for r in range(ROWS)
                for c in range(COLS)
                if not opened[r][c]
                and not flagged[r][c]
                and (c, r) not in bombs_current
                and (locked_cell is None or (c, r) != locked_cell)
                and (c, r) not in protected
            ]
            if not candidates:
                return None
            return random.choice(candidates)

        def reset_all():
            nonlocal opened, flagged, numbers
            nonlocal bombs_current, bombs_all, bombs_defused, bombs_triggered
            nonlocal buff_reveal_cells, buff_blast_cells
            nonlocal lives, time_left, started, blast_mode, reveal_left, blast_left
            nonlocal toast_msg, toast_t, flash_t
            nonlocal locked_cell, pressure_elapsed, next_pressure_at

            opened = [[False] * COLS for _ in range(ROWS)]
            flagged = [[False] * COLS for _ in range(ROWS)]
            numbers = [[0] * COLS for _ in range(ROWS)]

            bombs_current = set()
            bombs_all = set()
            bombs_defused = set()
            bombs_triggered = set()

            buff_reveal_cells = set()
            buff_blast_cells = set()

            lives = LIVES_INIT
            time_left = TIME_LIMIT
            started = False
            blast_mode = False

            reveal_left = 0
            blast_left = 0

            toast_msg = ""
            toast_t = 0.0
            flash_t = 0.0

            locked_cell = None
            pressure_elapsed = 0.0
            next_pressure_at = PRESSURE_INTERVAL

        reset_all()

        if not countdown(3):
            return False

        # -------------- loop --------------
        while True:
            dt = clock.tick(FPS) / 1000.0

            if toast_t > 0:
                toast_t = max(0.0, toast_t - dt)
            if flash_t > 0:
                flash_t = max(0.0, flash_t - dt)

            if started:
                time_left -= dt
                if time_left <= 0:
                    choice = result_screen(False)
                    if choice == "restart":
                        reset_all()
                        if not countdown(3):
                            return False
                        continue
                    return False

                pressure_elapsed += dt
                if pressure_elapsed >= next_pressure_at:
                    next_pressure_at += PRESSURE_INTERVAL
                    new_lock = pick_locked_cell()
                    locked_cell = new_lock
                    if locked_cell is not None:
                        toast(f"顧老爺施壓！封鎖了一格：({locked_cell[0]+1},{locked_cell[1]+1})", TOAST_IMPORTANT)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        return False

                    if e.key == pygame.K_SPACE:
                        if blast_left > 0:
                            blast_mode = not blast_mode
                            toast(f"爆破模式：{'ON' if blast_mode else 'OFF'}", TOAST_NORMAL)
                        else:
                            toast("你沒有爆破 Buff", TOAST_NORMAL)

                    if e.key == pygame.K_r:
                        use_reveal(auto=False)

                if e.type == pygame.MOUSEBUTTONDOWN:
                    cell = pos_to_cell(e.pos)
                    if cell is None:
                        continue
                    c, r = cell

                    if locked_cell is not None and (c, r) == locked_cell:
                        toast("這格被顧老爺封鎖了，不能操作！", TOAST_IMPORTANT)
                        continue

                    if e.button == 3:
                        if not opened[r][c]:
                            flagged[r][c] = not flagged[r][c]
                        continue

                    if e.button == 1:
                        if not started:
                            started = True
                            bombs_current = spawn_bombs(first_click=(c, r))
                            bombs_all = set(bombs_current)
                            recompute_numbers()
                            buff_reveal_cells, buff_blast_cells = pick_buff_cells()

                            locked_cell = None
                            pressure_elapsed = 0.0
                            next_pressure_at = PRESSURE_INTERVAL

                        if opened[r][c] or flagged[r][c]:
                            continue

                        if blast_mode and blast_left > 0:
                            blast_cross((c, r))
                            continue

                        if (c, r) in bombs_current:
                            lives -= 1
                            flash_t = 0.35
                            opened[r][c] = True
                            bombs_triggered.add((c, r))
                            toast(f"踩到炸彈！剩餘命：{lives}", TOAST_IMPORTANT)

                            if lives <= 0:
                                choice = result_screen(False)
                                if choice == "restart":
                                    reset_all()
                                    if not countdown(3):
                                        return False
                                    continue
                                return False
                            continue

                        if numbers[r][c] == 0:
                            flood_open(c, r)
                        else:
                            opened[r][c] = True
                            collect_buff(c, r)

            if started and opened_safe_count() >= total_safe_cells():
                choice = result_screen(True)
                if choice == "restart":
                    reset_all()
                    if not countdown(3):
                        return False
                    continue
                if choice == "proceed":
                    return True
                return False

            screen.fill(BG)
            draw_top_ui(time_left)
            draw_board()
            pygame.display.flip()
