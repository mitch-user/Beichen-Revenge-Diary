# minigames/snake_duel.py
import sys
import random
from typing import List, Tuple, Optional

import pygame

Vec = Tuple[int, int]


class SnakeDuelGame:
    """
    mg1: 貪食蛇對決（主角 vs 兩條敵蛇）
    - 倒數時可看到後面蛇/果實位置
    - 全部速度放慢
    - 主角蛇凸顯：金色身體+白頭+皇冠+YOU 標
    - 倒數結束後 1 秒無敵緩衝（避免一開始就死）
    - ESC 離開（回傳 False）
    - 勝利/失敗畫面：Enter 重來（KEYDOWN + get_pressed 雙保險）
    - ✅【新增】勝利畫面：按鈕「進入第三章」（點了才回傳 True）
    """

    name = "mg1"

    def run(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        font: pygame.font.Font,
        goal_fruits: int = 15,
    ) -> bool:
        W, H = screen.get_size()
        FPS = 60

        GRID = 24
        BOARD_TOP = 90
        BOARD_MARGIN = 40

        # ✅ 再放慢（你可以再改更慢）
        STEP_PLAYER = 0.18
        STEP_ENEMY = 0.75

        # UI / colors
        BG = (16, 18, 24)
        UI = (235, 235, 240)
        PANEL = (20, 22, 30)

        # ✅ 主角蛇：金色系 + 白頭
        PLAYER_BODY = (245, 198, 75)
        PLAYER_HEAD = (255, 255, 255)
        PLAYER_ACCENT = (255, 235, 170)

        ENEMY1_BODY = (235, 120, 120)
        ENEMY1_HEAD = (255, 170, 170)

        ENEMY2_BODY = (120, 170, 245)
        ENEMY2_HEAD = (170, 210, 255)

        FRUIT = (120, 220, 120)

        board_w = (W - BOARD_MARGIN * 2) // GRID * GRID
        board_h = (H - BOARD_TOP - BOARD_MARGIN) // GRID * GRID
        board_x = (W - board_w) // 2
        board_y = BOARD_TOP
        board_rect = pygame.Rect(board_x, board_y, board_w, board_h)

        cols = board_w // GRID
        rows = board_h // GRID

        # ---------------- helpers ----------------
        def cell_to_px(c: Vec) -> pygame.Rect:
            x = board_x + c[0] * GRID
            y = board_y + c[1] * GRID
            return pygame.Rect(x, y, GRID, GRID)

        def inside(c: Vec) -> bool:
            return 0 <= c[0] < cols and 0 <= c[1] < rows

        UP: Vec = (0, -1)
        DOWN: Vec = (0, 1)
        LEFT: Vec = (-1, 0)
        RIGHT: Vec = (1, 0)

        def is_reverse(a: Vec, b: Vec) -> bool:
            return a[0] + b[0] == 0 and a[1] + b[1] == 0

        def spawn_snake(center: Vec, length: int, direction: Vec) -> List[Vec]:
            body = [center]
            for i in range(1, length):
                body.append((center[0] - direction[0] * i, center[1] - direction[1] * i))
            return body

        def draw_ui(text_top: str, text_sub: str):
            top_rect = pygame.Rect(0, 0, W, BOARD_TOP)
            pygame.draw.rect(screen, PANEL, top_rect)
            pygame.draw.line(screen, (60, 60, 70), (0, BOARD_TOP - 1), (W, BOARD_TOP - 1), 2)

            t1 = font.render(text_top, True, UI)
            screen.blit(t1, (BOARD_MARGIN, 18))
            t2 = font.render(text_sub, True, (200, 200, 210))
            screen.blit(t2, (BOARD_MARGIN, 52))

        def draw_crown_marker(head_rect: pygame.Rect):
            # 皇冠小三角（很醒目）
            cx, cy = head_rect.centerx, head_rect.top - 2
            pts = [
                (cx - 14, cy + 12),
                (cx - 8, cy),
                (cx - 2, cy + 10),
                (cx + 4, cy - 2),
                (cx + 10, cy + 10),
                (cx + 16, cy + 2),
                (cx + 18, cy + 12),
            ]
            pygame.draw.polygon(screen, PLAYER_ACCENT, pts)

        def draw_you_label(head_rect: pygame.Rect):
            small = pygame.font.SysFont("Microsoft JhengHei", 18, bold=True)
            img = small.render("YOU", True, (20, 20, 20))
            bg = pygame.Surface((img.get_width() + 10, img.get_height() + 6), pygame.SRCALPHA)
            bg.fill((255, 255, 255, 210))
            screen.blit(bg, (head_rect.centerx - bg.get_width() // 2, head_rect.top - 36))
            screen.blit(img, (head_rect.centerx - img.get_width() // 2, head_rect.top - 33))

        def draw_snake(snake: List[Vec], body_col, head_col, is_player=False):
            # body
            for c in reversed(snake):
                r = cell_to_px(c).inflate(-3, -3)
                pygame.draw.rect(screen, body_col, r, border_radius=6)

            # head
            head = snake[0]
            hr = cell_to_px(head).inflate(-1, -1)
            pygame.draw.rect(screen, head_col, hr, border_radius=8)

            # eyes direction
            if len(snake) >= 2:
                neck = snake[1]
                dx = head[0] - neck[0]
                dy = head[1] - neck[1]
                d = (max(-1, min(1, dx)), max(-1, min(1, dy)))
            else:
                d = RIGHT

            ex, ey = hr.center
            offset = GRID // 5
            side = GRID // 6

            if d == UP:
                e1 = (ex - offset, ey - offset)
                e2 = (ex + offset, ey - offset)
            elif d == DOWN:
                e1 = (ex - offset, ey + offset)
                e2 = (ex + offset, ey + offset)
            elif d == LEFT:
                e1 = (ex - offset, ey - offset)
                e2 = (ex - offset, ey + offset)
            else:
                e1 = (ex + offset, ey - offset)
                e2 = (ex + offset, ey + offset)

            pygame.draw.circle(screen, (10, 10, 10), e1, side)
            pygame.draw.circle(screen, (10, 10, 10), e2, side)

            if is_player:
                draw_crown_marker(hr)
                draw_you_label(hr)

        def move_snake(snake: List[Vec], direction: Vec, grow: bool) -> List[Vec]:
            head = snake[0]
            nh = (head[0] + direction[0], head[1] + direction[1])
            new_body = [nh] + snake[:-1]
            if grow:
                new_body.append(snake[-1])
            return new_body

        # ---------------- state ----------------
        player: List[Vec] = []
        enemy1: List[Vec] = []
        enemy2: List[Vec] = []
        dir_player: Vec = RIGHT
        dir_enemy1: Vec = RIGHT
        dir_enemy2: Vec = LEFT
        fruit: Vec = (0, 0)
        eaten = 0
        acc_p = 0.0
        acc_e = 0.0

        invincible_timer = 0.0  # ✅ 開場緩衝
        enter_cooldown = 0.0    # ✅ 避免 Enter 被吃事件

        def all_occupied() -> set:
            occ = set(player)
            occ |= set(enemy1)
            occ |= set(enemy2)
            return occ

        def spawn_fruit() -> Vec:
            occ = all_occupied()
            while True:
                c = (random.randint(0, cols - 1), random.randint(0, rows - 1))
                if c not in occ:
                    return c

        def reset():
            nonlocal player, enemy1, enemy2, dir_player, dir_enemy1, dir_enemy2, fruit, eaten, acc_p, acc_e
            nonlocal invincible_timer, enter_cooldown

            # ✅ 初始位置拉開距離（避免一開就被黏死）
            player = spawn_snake((cols // 2, rows // 2 + 4), 4, RIGHT)
            dir_player = RIGHT

            enemy1 = spawn_snake((cols // 2 - 9, rows // 2 - 5), 4, RIGHT)
            dir_enemy1 = RIGHT

            enemy2 = spawn_snake((cols // 2 + 9, rows // 2 - 1), 4, LEFT)
            dir_enemy2 = LEFT

            fruit = spawn_fruit()
            eaten = 0
            acc_p = 0.0
            acc_e = 0.0

            invincible_timer = 1.0     # ✅ 倒數完後 1 秒無敵
            enter_cooldown = 0.5       # ✅ 防連點

        def ai_next_dir(head: Vec, cur_dir: Vec) -> Vec:
            # 很簡單的追果 AI，但會避免撞到任何蛇
            dirs = [UP, DOWN, LEFT, RIGHT]
            dirs = [d for d in dirs if not is_reverse(cur_dir, d)]
            random.shuffle(dirs)

            occ = all_occupied()

            best = cur_dir
            best_score = 10**9

            for d in dirs:
                nh = (head[0] + d[0], head[1] + d[1])
                if not inside(nh):
                    continue
                if nh in occ:
                    continue
                score = abs(nh[0] - fruit[0]) + abs(nh[1] - fruit[1])
                if score < best_score:
                    best_score = score
                    best = d

            nh = (head[0] + best[0], head[1] + best[1])
            if inside(nh) and nh not in occ:
                return best

            for d in dirs:
                nh = (head[0] + d[0], head[1] + d[1])
                if inside(nh) and nh not in occ:
                    return d

            return cur_dir

        def draw_world(text_top: str, text_sub: str):
            screen.fill(BG)
            pygame.draw.rect(screen, (40, 45, 55), board_rect, width=3, border_radius=10)

            # fruit
            fr = cell_to_px(fruit).inflate(-6, -6)
            pygame.draw.rect(screen, FRUIT, fr, border_radius=8)

            # snakes
            draw_snake(enemy1, ENEMY1_BODY, ENEMY1_HEAD, is_player=False)
            draw_snake(enemy2, ENEMY2_BODY, ENEMY2_HEAD, is_player=False)
            draw_snake(player, PLAYER_BODY, PLAYER_HEAD, is_player=True)

            draw_ui(text_top, text_sub)

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

                # ✅ 倒數時也畫出「世界」
                draw_world(
                    "小遊戲1：貪食蛇對決｜吃到 15 顆過關｜WASD/方向鍵移動",
                    "倒數開始中…（ESC 離開）",
                )

                txt = str(remain_s) if remain_s > 0 else "GO!"
                num = big.render(txt, True, UI)
                screen.blit(num, num.get_rect(center=(W // 2, H // 2)))
                pygame.display.flip()

                if elapsed >= total_ms:
                    return True

        # ✅【改】這裡改成回傳字串： "restart" / "exit" / "next"
        def result_screen(win: bool) -> Optional[str]:
            nonlocal enter_cooldown
            big = pygame.font.SysFont("Microsoft JhengHei", 52, bold=True)
            mid = pygame.font.SysFont("Microsoft JhengHei", 28, bold=True)

            title = "勝利！你搶先吃到 15 顆果實！" if win else "失敗！你被撞到了！"
            sub = "Enter 重來｜ESC 離開" if not win else "Enter 重來｜ESC 離開｜或點按鈕進入第三章"

            # ✅【新增】勝利按鈕
            btn_next = pygame.Rect(W // 2 - 190, H // 2 + 80, 380, 56)

            while True:
                dt = clock.tick(FPS) / 1000.0
                enter_cooldown = max(0.0, enter_cooldown - dt)

                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit(0)
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_ESCAPE:
                            return "exit"
                        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            if enter_cooldown <= 0:
                                return "restart"
                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        if win and btn_next.collidepoint(e.pos):
                            return "next"

                keys = pygame.key.get_pressed()
                if keys[pygame.K_ESCAPE]:
                    return "exit"
                if (keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER]) and enter_cooldown <= 0:
                    return "restart"

                # 背景維持最後畫面
                overlay = pygame.Surface((W, H), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                screen.blit(overlay, (0, 0))

                t1 = big.render(title, True, UI)
                t2 = font.render(sub, True, (220, 220, 220))
                screen.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 50)))
                screen.blit(t2, t2.get_rect(center=(W // 2, H // 2 + 8)))

                # ✅【新增】勝利才顯示按鈕
                if win:
                    pygame.draw.rect(screen, (240, 240, 240), btn_next, border_radius=14)
                    pygame.draw.rect(screen, (255, 255, 255), btn_next, width=2, border_radius=14)
                    btxt = mid.render("進入第三章", True, (20, 20, 20))
                    screen.blit(btxt, btxt.get_rect(center=btn_next.center))

                pygame.display.flip()

        # ---------------- start ----------------
        reset()
        if not countdown(3):
            return False

        while True:
            dt = clock.tick(FPS) / 1000.0
            acc_p += dt
            acc_e += dt
            invincible_timer = max(0.0, invincible_timer - dt)

            # 讓視窗事件不卡住
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

            keys = pygame.key.get_pressed()
            if keys[pygame.K_ESCAPE]:
                return False

            # ✅ WASD / 方向鍵（get_pressed 版本最穩）
            if (keys[pygame.K_UP] or keys[pygame.K_w]) and not is_reverse(dir_player, UP):
                dir_player = UP
            elif (keys[pygame.K_DOWN] or keys[pygame.K_s]) and not is_reverse(dir_player, DOWN):
                dir_player = DOWN
            elif (keys[pygame.K_LEFT] or keys[pygame.K_a]) and not is_reverse(dir_player, LEFT):
                dir_player = LEFT
            elif (keys[pygame.K_RIGHT] or keys[pygame.K_d]) and not is_reverse(dir_player, RIGHT):
                dir_player = RIGHT

            # --- player step ---
            if acc_p >= STEP_PLAYER:
                acc_p = 0.0
                nh = (player[0][0] + dir_player[0], player[0][1] + dir_player[1])

                if not inside(nh):
                    if invincible_timer <= 0:
                        # ✅【改】依 result_screen 回傳處理
                        action = result_screen(False)
                        if action == "restart":
                            reset()
                            if not countdown(3):
                                return False
                            continue
                        return False
                    else:
                        # 無敵期：撞牆就不動
                        nh = player[0]

                if invincible_timer <= 0 and (nh in set(player) or nh in set(enemy1) or nh in set(enemy2)):
                    # ✅【改】依 result_screen 回傳處理
                    action = result_screen(False)
                    if action == "restart":
                        reset()
                        if not countdown(3):
                            return False
                        continue
                    return False

                grow = (nh == fruit)
                if nh != player[0]:
                    player = move_snake(player, dir_player, grow)

                if grow:
                    eaten += 1
                    fruit = spawn_fruit()
                    if eaten >= goal_fruits:
                        # ✅【改】勝利：要點「進入第三章」才 return True
                        action = result_screen(True)
                        if action == "restart":
                            reset()
                            if not countdown(3):
                                return False
                            continue
                        if action == "next":
                            return True
                        return False

            # --- enemies step (slower) ---
            if acc_e >= STEP_ENEMY:
                acc_e = 0.0

                dir_enemy1 = ai_next_dir(enemy1[0], dir_enemy1)
                nh1 = (enemy1[0][0] + dir_enemy1[0], enemy1[0][1] + dir_enemy1[1])
                if inside(nh1) and nh1 not in all_occupied():
                    enemy1 = move_snake(enemy1, dir_enemy1, nh1 == fruit)
                    if nh1 == fruit:
                        fruit = spawn_fruit()

                dir_enemy2 = ai_next_dir(enemy2[0], dir_enemy2)
                nh2 = (enemy2[0][0] + dir_enemy2[0], dir_enemy2[1] + enemy2[0][1])
                nh2 = (enemy2[0][0] + dir_enemy2[0], enemy2[0][1] + dir_enemy2[1])
                if inside(nh2) and nh2 not in all_occupied():
                    enemy2 = move_snake(enemy2, dir_enemy2, nh2 == fruit)
                    if nh2 == fruit:
                        fruit = spawn_fruit()

            # draw
            draw_world(
                f"小遊戲1：貪食蛇對決｜目標 {goal_fruits} 顆",
                f"你已吃到：{eaten}/{goal_fruits}｜ESC 離開｜（主角：金色有皇冠）",
            )
            pygame.display.flip()
