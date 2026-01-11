import pygame

class MiniGameBase:
    name = "minigame"

    def run(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        font: pygame.font.Font,
    ) -> bool:
        """
        回傳：
        True  = 過關
        False = 失敗 / 放棄
        """
        raise NotImplementedError