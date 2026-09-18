"""touhou-arrow game 开始界面与基础窗口模块。

本文件负责：
1. 创建 800x600 的游戏窗口，并支持窗口/全屏模式切换。
2. 显示带图标的主菜单（开始游戏、设置、离开游戏）。
3. 提供设置界面，用开关切换窗口模式和全屏模式。
4. 以 60FPS 运行完整主循环。
"""

import math
import sys

import pygame


class Game:
    """游戏主类，封装窗口、场景切换、事件处理与主循环。"""

    # 窗口模式下的显示尺寸
    WINDOW_SIZE = (800, 600)
    # 游戏窗口标题
    TITLE = "touhou-arrow game"
    # 目标帧率
    FPS = 60

    # 界面配色
    BG_COLOR = (24, 24, 36)
    TITLE_COLOR = (255, 255, 255)
    TEXT_COLOR = (220, 220, 220)
    MUTED_COLOR = (150, 150, 165)
    BUTTON_COLOR = (42, 48, 66)
    BUTTON_HOVER_COLOR = (58, 68, 92)
    BUTTON_BORDER_COLOR = (100, 110, 140)
    BUTTON_TEXT_COLOR = (235, 235, 240)
    ICON_TRIANGLE_COLOR = (90, 210, 255)
    ICON_GEAR_COLOR = (255, 210, 90)
    ICON_X_COLOR = (255, 110, 110)
    SWITCH_ON_COLOR = (90, 200, 120)
    SWITCH_OFF_COLOR = (90, 95, 115)
    SWITCH_KNOB_COLOR = (245, 245, 245)

    def __init__(self):
        """初始化 Pygame、字体、时钟与初始窗口。"""
        pygame.init()

        self.clock = pygame.time.Clock()
        self.running = True

        # True 表示全屏，False 表示窗口模式
        self.is_fullscreen = False
        # 当前界面：menu 为主菜单，settings 为设置界面
        self.scene = "menu"

        self.screen = pygame.display.set_mode(self.WINDOW_SIZE)
        pygame.display.set_caption(self.TITLE)

        # 优先使用系统中常见的中文字体，避免按钮文字显示为方框
        self.title_font = self._load_font(52)
        self.subtitle_font = self._load_font(24)
        self.button_font = self._load_font(28)
        self.setting_font = self._load_font(30)

    @staticmethod
    def _load_font(size):
        """创建指定大小的中文字体对象。"""
        font_names = ["microsoftyahei", "msyh", "simhei", "simsun"]
        return pygame.font.SysFont(font_names, size)

    # ------------------------------------------------------------------
    # 显示模式
    # ------------------------------------------------------------------
    def toggle_fullscreen(self):
        """在窗口模式和全屏模式之间切换。"""
        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            # 传入 (0, 0) 并使用 FULLSCREEN 标志，可自动使用当前屏幕尺寸
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.WINDOW_SIZE)

        # 切换后重新设置标题，避免部分系统丢失窗口标题
        pygame.display.set_caption(self.TITLE)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def handle_events(self):
        """分发当前场景的 Pygame 事件。"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif self.scene == "menu":
                self.handle_menu_events(event)
            elif self.scene == "settings":
                self.handle_settings_events(event)

    def handle_menu_events(self, event):
        """处理主菜单按钮点击。"""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        mouse_pos = event.pos
        for button in self.build_menu_buttons():
            if button["rect"].collidepoint(mouse_pos):
                button["action"]()
                break

    def handle_settings_events(self, event):
        """处理设置界面中的开关和返回按钮点击。"""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        mouse_pos = event.pos

        # 点击开关区域时切换显示模式
        switch_rect = self.get_switch_rect()
        if switch_rect.collidepoint(mouse_pos):
            self.toggle_fullscreen()
            return

        # 点击“返回主菜单”按钮
        back_rect = self.get_back_button_rect()
        if back_rect.collidepoint(mouse_pos):
            self.scene = "menu"

    # ------------------------------------------------------------------
    # 主菜单按钮
    # ------------------------------------------------------------------
    def build_menu_buttons(self):
        """根据当前屏幕尺寸创建主菜单按钮列表。"""
        button_width = 320
        button_height = 68
        gap = 24

        # 按钮列整体居中，并在垂直方向上稍微偏下，为标题留出空间
        total_height = button_height * 3 + gap * 2
        start_y = self.screen.get_height() // 2 - total_height // 2 + 50
        center_x = self.screen.get_width() // 2

        buttons = []
        for index, item in enumerate(
            (
                {"label": "开始游戏", "icon": "triangle", "action": self.action_start_game},
                {"label": "设置", "icon": "gear", "action": self.action_open_settings},
                {"label": "离开游戏", "icon": "x", "action": self.action_quit_game},
            )
        ):
            y = start_y + index * (button_height + gap)
            rect = pygame.Rect(0, 0, button_width, button_height)
            rect.center = (center_x, y + button_height // 2)
            buttons.append({"rect": rect, **item})

        return buttons

    def action_start_game(self):
        """“开始游戏”按钮的回调。

        当前阶段暂未安排功能，因此点击后保持停留在主菜单。
        """
        # 后续接入关卡或角色选择界面时，可以在这里修改 self.scene。
        pass

    def action_open_settings(self):
        """“设置”按钮的回调，进入设置界面。"""
        self.scene = "settings"

    def action_quit_game(self):
        """“离开游戏”按钮的回调，退出主循环。"""
        self.running = False

    # ------------------------------------------------------------------
    # 设置界面控件
    # ------------------------------------------------------------------
    def get_switch_rect(self):
        """返回设置界面中显示模式开关的可点击区域。"""
        width, height = 160, 64
        center_x = self.screen.get_width() // 2
        center_y = self.screen.get_height() // 2
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (center_x, center_y)
        return rect

    def get_back_button_rect(self):
        """返回设置界面中“返回主菜单”按钮的区域。"""
        width, height = 220, 56
        center_x = self.screen.get_width() // 2
        center_y = self.screen.get_height() // 2 + 120
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (center_x, center_y)
        return rect

    # ------------------------------------------------------------------
    # 绘制辅助函数
    # ------------------------------------------------------------------
    @staticmethod
    def draw_text(surface, font, text, color, center):
        """在指定中心位置绘制文本，并返回文本矩形。"""
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=center)
        surface.blit(text_surface, text_rect)
        return text_rect

    @staticmethod
    def draw_triangle_icon(surface, center, size, color):
        """绘制开始按钮前的向右三角形图标。"""
        half = size // 2
        points = (
            (center[0] - half, center[1] - half),
            (center[0] - half, center[1] + half),
            (center[0] + half, center[1]),
        )
        pygame.draw.polygon(surface, color, points)

    @staticmethod
    def draw_gear_icon(surface, center, radius, color):
        """使用多边形和圆形绘制设置按钮前的齿轮图标。"""
        tooth_count = 8
        inner_radius = radius * 0.65

        # 先绘制一圈齿轮齿
        for index in range(tooth_count):
            angle = math.pi * 2 * index / tooth_count + math.pi / tooth_count
            inner_x = center[0] + math.cos(angle) * inner_radius
            inner_y = center[1] + math.sin(angle) * inner_radius
            outer_x = center[0] + math.cos(angle) * radius
            outer_y = center[1] + math.sin(angle) * radius
            pygame.draw.line(surface, color, (inner_x, inner_y), (outer_x, outer_y), 4)

        # 绘制齿轮主体圆环和中心孔
        pygame.draw.circle(surface, color, center, int(inner_radius), 4)
        pygame.draw.circle(surface, color, center, int(radius * 0.28), 0)

    @staticmethod
    def draw_x_icon(surface, center, size, color):
        """绘制离开游戏按钮前的 X 图标。"""
        half = size // 2
        pygame.draw.line(
            surface,
            color,
            (center[0] - half, center[1] - half),
            (center[0] + half, center[1] + half),
            5,
        )
        pygame.draw.line(
            surface,
            color,
            (center[0] + half, center[1] - half),
            (center[0] - half, center[1] + half),
            5,
        )

    def draw_button(self, button):
        """绘制单个主菜单按钮，包含图标、文字和悬停效果。"""
        rect = button["rect"]
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)

        background = self.BUTTON_HOVER_COLOR if hovered else self.BUTTON_COLOR
        pygame.draw.rect(self.screen, background, rect, border_radius=14)
        pygame.draw.rect(self.screen, self.BUTTON_BORDER_COLOR, rect, width=2, border_radius=14)

        label_surface = self.button_font.render(button["label"], True, self.BUTTON_TEXT_COLOR)
        label_rect = label_surface.get_rect()

        icon_size = 28
        gap = 12
        # 图标和文字作为一个整体居中，图标位于文字左侧
        group_width = icon_size + gap + label_rect.width
        group_left = rect.centerx - group_width // 2

        icon_center = (group_left + icon_size // 2, rect.centery)
        label_center = (group_left + icon_size + gap + label_rect.width // 2, rect.centery)

        if button["icon"] == "triangle":
            self.draw_triangle_icon(self.screen, icon_center, icon_size, self.ICON_TRIANGLE_COLOR)
        elif button["icon"] == "gear":
            self.draw_gear_icon(self.screen, icon_center, icon_size // 2, self.ICON_GEAR_COLOR)
        elif button["icon"] == "x":
            self.draw_x_icon(self.screen, icon_center, icon_size, self.ICON_X_COLOR)

        label_rect.center = label_center
        self.screen.blit(label_surface, label_rect)

    def draw_switch(self, rect):
        """绘制设置界面中的显示模式开关。"""
        # 开关轨道
        track_color = self.SWITCH_ON_COLOR if self.is_fullscreen else self.SWITCH_OFF_COLOR
        pygame.draw.rect(self.screen, track_color, rect, border_radius=rect.height // 2)

        # 根据当前模式决定滑块位于轨道左侧还是右侧
        knob_radius = rect.height // 2 - 8
        if self.is_fullscreen:
            knob_x = rect.right - knob_radius - 8
        else:
            knob_x = rect.left + knob_radius + 8
        knob_center = (knob_x, rect.centery)
        pygame.draw.circle(self.screen, self.SWITCH_KNOB_COLOR, knob_center, knob_radius)

    # ------------------------------------------------------------------
    # 场景绘制
    # ------------------------------------------------------------------
    def draw_menu(self):
        """绘制主菜单场景。"""
        self.screen.fill(self.BG_COLOR)

        # 顶部标题
        title_center = (self.screen.get_width() // 2, 130)
        self.draw_text(self.screen, self.title_font, self.TITLE, self.TITLE_COLOR, title_center)

        subtitle_center = (self.screen.get_width() // 2, 188)
        self.draw_text(self.screen, self.subtitle_font, "请选择一个选项", self.MUTED_COLOR, subtitle_center)

        # 三个菜单按钮
        for button in self.build_menu_buttons():
            self.draw_button(button)

    def draw_settings(self):
        """绘制设置界面场景。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 120)
        self.draw_text(self.screen, self.title_font, "设置", self.TITLE_COLOR, title_center)

        # 显示当前模式说明
        mode_text = "当前模式：全屏" if self.is_fullscreen else "当前模式：窗口"
        mode_center = (self.screen.get_width() // 2, 210)
        self.draw_text(self.screen, self.setting_font, mode_text, self.TEXT_COLOR, mode_center)

        switch_rect = self.get_switch_rect()
        self.draw_switch(switch_rect)

        # 返回主菜单按钮
        back_rect = self.get_back_button_rect()
        mouse_pos = pygame.mouse.get_pos()
        hovered = back_rect.collidepoint(mouse_pos)
        back_color = self.BUTTON_HOVER_COLOR if hovered else self.BUTTON_COLOR
        pygame.draw.rect(self.screen, back_color, back_rect, border_radius=12)
        pygame.draw.rect(self.screen, self.BUTTON_BORDER_COLOR, back_rect, width=2, border_radius=12)
        self.draw_text(self.screen, self.button_font, "返回主菜单", self.BUTTON_TEXT_COLOR, back_rect.center)

    def draw(self):
        """根据当前场景绘制整个画面。"""
        if self.scene == "menu":
            self.draw_menu()
        elif self.scene == "settings":
            self.draw_settings()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # 更新与主循环
    # ------------------------------------------------------------------
    def update(self):
        """更新游戏逻辑。当前基础界面暂无逐帧更新内容。"""
        pass

    def run(self):
        """运行游戏主循环，直到收到退出请求。"""
        while self.running:
            # 限制帧率，使游戏稳定运行在 60FPS
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
