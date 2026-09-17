"""touhou-arrow game 基础窗口模块。

本文件负责创建游戏窗口、处理基础事件（关闭窗口、切换显示模式），
并以固定帧率运行主循环，作为后续游戏功能的入口。
"""

import sys

import pygame


class Game:
    """游戏主类，封装窗口创建、事件处理与主循环。"""

    # 窗口模式下的显示尺寸
    WINDOW_SIZE = (800, 600)
    # 游戏窗口标题
    TITLE = "touhou-arrow game"
    # 目标帧率
    FPS = 60
    # 切换窗口/全屏模式的按键
    TOGGLE_FULLSCREEN_KEY = pygame.K_F11

    def __init__(self):
        """初始化 Pygame、时钟和初始窗口。"""
        pygame.init()

        self.clock = pygame.time.Clock()
        self.running = True
        # True 表示全屏，False 表示窗口模式
        self.is_fullscreen = False
        # 创建初始窗口（窗口模式，800x600）
        self.screen = pygame.display.set_mode(self.WINDOW_SIZE)
        pygame.display.set_caption(self.TITLE)

    def toggle_fullscreen(self):
        """在窗口模式和全屏模式之间切换。"""
        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            # 全屏模式使用当前屏幕的完整尺寸
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            # 切回固定大小的窗口模式
            self.screen = pygame.display.set_mode(self.WINDOW_SIZE)

        # 切换模式后重新设置标题，避免部分系统丢失窗口标题
        pygame.display.set_caption(self.TITLE)

    def handle_events(self):
        """处理 Pygame 事件，包括退出和显示模式切换。"""
        for event in pygame.event.get():
            # 点击窗口关闭按钮，退出主循环
            if event.type == pygame.QUIT:
                self.running = False
            # 按下按键时判断是否需要切换显示模式
            elif event.type == pygame.KEYDOWN:
                if event.key == self.TOGGLE_FULLSCREEN_KEY:
                    self.toggle_fullscreen()
                # 在窗口模式下按 ESC 也可以直接退出，方便测试
                elif event.key == pygame.K_ESCAPE and not self.is_fullscreen:
                    self.running = False

    def update(self):
        """更新游戏逻辑。目前为基础窗口，暂无额外更新内容。"""
        # 后续游戏逻辑可以在这里扩展。
        pass

    def draw(self):
        """绘制当前帧。"""
        # 使用深色背景填充，便于观察窗口是否正常显示
        self.screen.fill((24, 24, 36))
        pygame.display.flip()

    def run(self):
        """运行游戏主循环，直到收到退出请求。"""
        while self.running:
            # 限制每秒最多执行 60 次循环
            self.clock.tick(self.FPS)
            self.handle_events()
            self.update()
            self.draw()

        pygame.quit()
        sys.exit()


def main():
    """程序入口：创建游戏实例并启动主循环。"""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
