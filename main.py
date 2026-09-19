"""touhou-arrow game 开始界面与基础窗口模块。

本文件负责：
1. 创建 800x600 的游戏窗口，并支持窗口/全屏模式切换。
2. 显示带图标的主菜单（开始游戏、设置、离开游戏）。
3. 提供设置界面，用开关切换窗口模式和全屏模式。
4. 渲染 9x9 棋盘，并根据关卡二维数组显示不同颜色的方向箭头。
5. 部分箭头由 1 个三角形和 2-3 格长条身体组成，并规避格子重叠与无法通关的死局。
6. 检测点击的箭头是否能飞出棋盘，并在控制台输出结果。
7. 播放飞出/阻挡动画，显示关卡、剩余箭头，并在扣除机会时播放爱心碎裂特效。
8. 清除全部箭头后进入通关界面，机会耗尽后进入失败界面。
9. 以 60FPS 运行完整主循环。
"""

import math
import random
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

    # 棋盘配置：9x9 网格，格子尺寸按窗口大小适当缩小
    BOARD_SIZE = 9
    CELL_SIZE = 40
    CELL_GAP = 2

    # 箭头总数，以及其中使用 2-3 个正方形组成的长箭头占比
    TOTAL_ARROWS = 20
    LONG_ARROW_RATIO = 0.10
    INITIAL_MISTAKES = 3

    # 动画参数
    FLY_DURATION = 0.45
    SHAKE_DURATION = 0.70
    SHAKE_AMPLITUDE = 8
    BLOCKED_COLOR = (255, 80, 80)

    # 方向编码对应的行列偏移：1=上，2=下，3=左，4=右
    DIRECTIONS = {
        1: (-1, 0),
        2: (1, 0),
        3: (0, -1),
        4: (0, 1),
    }

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
    HEART_COLOR = (255, 90, 110)
    HEART_EMPTY_COLOR = (90, 95, 115)

    # 棋盘与箭头配色
    BOARD_CELL_COLOR = (39, 44, 60)
    BOARD_GRID_COLOR = (75, 82, 105)
    # 不同方向的箭头使用不同颜色：上、下、左、右
    ARROW_COLORS = {
        1: (95, 185, 255),
        2: (255, 130, 125),
        3: (140, 230, 150),
        4: (255, 215, 100),
    }

    def __init__(self):
        """初始化 Pygame、字体、时钟与初始窗口。"""
        pygame.init()

        self.clock = pygame.time.Clock()
        self.running = True

        # True 表示全屏，False 表示窗口模式
        self.is_fullscreen = False
        # 当前界面：menu 为主菜单，settings 为设置界面
        self.scene = "menu"
        # 当前要渲染的关卡数据，生成时已规避格子重叠，并保证关卡可通关
        self.level_data = self.generate_level()
        self.current_level = 1
        self.mistakes_left = self.INITIAL_MISTAKES
        self.remaining_arrows = self.count_arrow_groups(self.level_data)

        # 当前正在播放的箭头动画；同一时间只播放一个
        self.flying_animation = None
        self.shake_animation = None
        # 爱心扣除时产生的碎裂粒子
        self.heart_particles = []

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

    def generate_level(self, base_seed=20260918):
        """生成一个保证可以按某种顺序全部消除的 9x9 关卡。

        生成规则：
        - 0 表示空格，1/2/3/4 分别表示上、下、左、右箭头。
        - 约 10% 的箭头为长箭头，由 2-3 格长条身体和 1 个三角形箭头组成。
        - 每个箭头在生成时，都必须保证它的前方路径中没有已放置的箭头。
        - 因此按“后放置的先消除”顺序，可以稳定完成整关。
        """
        for attempt in range(200):
            # 每次重试使用不同种子，避免固定失败模式反复出现
            rng = random.Random(base_seed + attempt)
            board = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
            empty_cells = {
                (row, col)
                for row in range(self.BOARD_SIZE)
                for col in range(self.BOARD_SIZE)
            }

            long_arrow_count = max(1, round(self.TOTAL_ARROWS * self.LONG_ARROW_RATIO))
            single_arrow_count = self.TOTAL_ARROWS - long_arrow_count

            # 先生成箭头类型列表：长箭头的身体为 2 或 3 格
            arrow_specs = [rng.choice([2, 3]) for _ in range(long_arrow_count)]
            arrow_specs.extend([0] * single_arrow_count)
            rng.shuffle(arrow_specs)

            placed_all = True
            for body_count in arrow_specs:
                if not self.try_place_arrow(board, empty_cells, body_count, rng):
                    placed_all = False
                    break

            if placed_all:
                return board

        raise RuntimeError("无法生成可通关的关卡")

    def try_place_arrow(self, board, empty_cells, body_count, rng):
        """尝试放置一个不会导致关卡无法通关的箭头。"""
        total_length = body_count + 1
        directions = [1, 2, 3, 4]
        candidates = list(empty_cells)
        rng.shuffle(directions)
        rng.shuffle(candidates)

        for direction in directions:
            dr, dc = self.DIRECTIONS[direction]

            for start_row, start_col in candidates:
                cells = []
                valid = True

                # 检查箭头自身占用的格子是否全部在棋盘内且尚未被占用
                for index in range(total_length):
                    cell_row = start_row + dr * index
                    cell_col = start_col + dc * index
                    if not (
                        0 <= cell_row < self.BOARD_SIZE
                        and 0 <= cell_col < self.BOARD_SIZE
                        and (cell_row, cell_col) in empty_cells
                    ):
                        valid = False
                        break
                    cells.append((cell_row, cell_col))

                if not valid:
                    continue

                # 头部格子前方必须通畅，保证该箭头可以被后放置先消除
                head_row, head_col = cells[-1]
                if not self.is_path_clear(board, head_row, head_col, direction):
                    continue

                # 尾部后方不能紧挨同方向箭头，否则会被合并成同一个箭头组
                behind_row = cells[0][0] - dr
                behind_col = cells[0][1] - dc
                if (
                    0 <= behind_row < self.BOARD_SIZE
                    and 0 <= behind_col < self.BOARD_SIZE
                    and board[behind_row][behind_col] == direction
                ):
                    continue

                # 确认无误后写入箭头并更新空格集合
                for cell_row, cell_col in cells:
                    board[cell_row][cell_col] = direction
                    empty_cells.discard((cell_row, cell_col))
                return True

        return False

    def is_path_clear(self, board, row, col, direction):
        """检查从指定格子前方到棋盘边界是否存在其他箭头。"""
        dr, dc = self.DIRECTIONS[direction]
        check_row = row + dr
        check_col = col + dc

        while 0 <= check_row < self.BOARD_SIZE and 0 <= check_col < self.BOARD_SIZE:
            if board[check_row][check_col] != 0:
                return False
            check_row += dr
            check_col += dc

        return True

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
            elif self.scene == "game":
                self.handle_game_events(event)
            elif self.scene in ("win", "lose"):
                self.handle_result_events(event)

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

    def handle_game_events(self, event):
        """处理棋盘场景的事件。

        鼠标左键用于检测箭头能否飞出，ESC 用于返回主菜单。
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.scene = "menu"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.handle_board_click(event.pos)

    def handle_result_events(self, event):
        """处理通关或失败界面中的按钮点击。"""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        for button in self.build_result_buttons():
            if button["rect"].collidepoint(event.pos):
                button["action"]()
                break

    def handle_board_click(self, mouse_pos):
        """根据鼠标点击位置检测箭头，并触发飞出或被阻挡动画。"""
        # 动画播放期间不响应新的点击，避免多个动画互相干扰
        if self.flying_animation is not None or self.shake_animation is not None:
            print("动画播放中，请稍候")
            return

        cell = self.get_cell_from_mouse(mouse_pos)
        if cell is None:
            print("点击位置不在棋盘格子内")
            return

        row, col = cell
        direction = self.level_data[row][col]
        if direction == 0:
            print(f"格子 ({row}, {col}) 为空，无箭头")
            return

        # 长箭头可能占用多个格子，因此以完整箭头整体为单位处理，
        # 并用箭头最前端的头部格子作为路径检测起点。
        cells = self.collect_arrow_group(self.level_data, row, col)
        head_row, head_col = cells[-1]
        direction_names = {1: "上", 2: "下", 3: "左", 4: "右"}

        if self.can_arrow_fly_out(head_row, head_col, direction):
            print(f"格子 ({row}, {col})：{direction_names[direction]}方向箭头 -> 可飞出")
            self.start_flying_animation(cells, direction)
        else:
            print(f"格子 ({row}, {col})：{direction_names[direction]}方向箭头 -> 被阻挡")
            # 在爱心扣除前，先为即将消失的爱心生成碎裂粒子
            if self.mistakes_left > 0:
                self.spawn_heart_break(self.mistakes_left - 1)
            # 每次被阻挡扣 1 次失误，最低保持为 0
            self.mistakes_left = max(0, self.mistakes_left - 1)
            self.start_shake_animation(cells, direction)

    def get_cell_from_mouse(self, mouse_pos):
        """将鼠标像素坐标转换为棋盘格子坐标；点击到间隙时返回 None。"""
        left, top = self.get_board_top_left()
        local_x = mouse_pos[0] - left
        local_y = mouse_pos[1] - top

        step = self.CELL_SIZE + self.CELL_GAP
        col = local_x // step
        row = local_y // step

        if not (0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE):
            return None

        # 排除落在格子之间间隙上的点击
        cell_local_x = col * step
        cell_local_y = row * step
        if local_x - cell_local_x >= self.CELL_SIZE or local_y - cell_local_y >= self.CELL_SIZE:
            return None

        return row, col

    def can_arrow_fly_out(self, row, col, direction):
        """检测指定位置的箭头是否可以被前方箭头阻挡。

        从当前箭头的前一格开始，沿箭头方向逐格检查到棋盘边界：
        - 途中遇到其他箭头，返回 False，表示被阻挡。
        - 顺利到达棋盘外，返回 True，表示可以飞出并消除。
        """
        if direction not in self.DIRECTIONS:
            return False

        dr, dc = self.DIRECTIONS[direction]
        check_row = row + dr
        check_col = col + dc

        # 只要还在棋盘内，就继续向前检查
        while 0 <= check_row < self.BOARD_SIZE and 0 <= check_col < self.BOARD_SIZE:
            if self.level_data[check_row][check_col] != 0:
                return False
            check_row += dr
            check_col += dc

        return True

    def start_flying_animation(self, cells, direction):
        """开始飞出动画；动画结束后再从数组中移除箭头。"""
        self.flying_animation = {
            "cells": list(cells),
            "direction": direction,
            "elapsed": 0.0,
            "duration": self.FLY_DURATION,
        }

    def start_shake_animation(self, cells, direction):
        """开始被阻挡时的左右晃动动画。"""
        self.shake_animation = {
            "cells": list(cells),
            "direction": direction,
            "elapsed": 0.0,
            "duration": self.SHAKE_DURATION,
        }

    def count_arrow_groups(self, level_data):
        """统计棋盘中的箭头组数量，长箭头按一个箭头计算。"""
        visited = set()
        count = 0

        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                if not level_data[row][col] or (row, col) in visited:
                    continue

                cells = self.collect_arrow_group(level_data, row, col)
                visited.update(cells)
                count += 1

        return count

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

        点击后重置当前关卡并进入棋盘场景。
        """
        self.reset_game()

    def action_open_settings(self):
        """“设置”按钮的回调，进入设置界面。"""
        self.scene = "settings"

    def action_quit_game(self):
        """“离开游戏”按钮的回调，退出主循环。"""
        self.running = False

    def action_return_lobby(self):
        """通关或失败界面中“返回大厅”按钮的回调。"""
        self.scene = "menu"

    def action_restart_game(self):
        """失败界面中“重新开始”按钮的回调。"""
        self.reset_game()

    def reset_game(self):
        """重置当前棋盘、爱心数量和动画状态，并进入游戏场景。"""
        self.level_data = self.generate_level()
        self.current_level = 1
        self.mistakes_left = self.INITIAL_MISTAKES
        self.remaining_arrows = self.count_arrow_groups(self.level_data)
        self.flying_animation = None
        self.shake_animation = None
        self.heart_particles = []
        self.scene = "game"

    def build_result_buttons(self):
        """根据当前结算场景创建通关或失败界面的按钮。"""
        center_x = self.screen.get_width() // 2
        button_width = 240
        button_height = 60
        gap = 20

        if self.scene == "win":
            items = (
                {"label": "返回大厅", "action": self.action_return_lobby},
            )
        else:
            items = (
                {"label": "重新开始", "action": self.action_restart_game},
                {"label": "返回大厅", "action": self.action_return_lobby},
            )

        buttons = []
        total_height = len(items) * button_height + (len(items) - 1) * gap
        start_y = self.screen.get_height() // 2 - total_height // 2 + 80

        for index, item in enumerate(items):
            y = start_y + index * (button_height + gap)
            rect = pygame.Rect(0, 0, button_width, button_height)
            rect.center = (center_x, y + button_height // 2)
            buttons.append({"rect": rect, **item})

        return buttons

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

    def draw_arrow(self, surface, center, direction, offset=(0, 0), color_override=None):
        """在单个格子中绘制由三角形箭头和长方形箭身组成的箭头。

        方向约定：1=上，2=下，3=左，4=右。
        长方形箭身的中轴线与三角形底边上的高保持重合。
        """
        x = center[0] + offset[0]
        y = center[1] + offset[1]
        half = self.CELL_SIZE // 3
        body_half = half / 2
        color = self.ARROW_COLORS.get(direction, self.TEXT_COLOR)
        if color_override is not None:
            color = color_override

        if direction == 1:
            # 向上：箭头顶点在上方，箭身位于箭头下方
            points = (
                (x - body_half, y + half),
                (x + body_half, y + half),
                (x + body_half, y),
                (x + half, y),
                (x, y - half),
                (x - half, y),
                (x - body_half, y),
            )
        elif direction == 2:
            # 向下：箭头顶点在下方，箭身位于箭头上方
            points = (
                (x - body_half, y - half),
                (x + body_half, y - half),
                (x + body_half, y),
                (x + half, y),
                (x, y + half),
                (x - half, y),
                (x - body_half, y),
            )
        elif direction == 3:
            # 向左：箭头顶点在左侧，箭身位于箭头右侧
            points = (
                (x + half, y - body_half),
                (x, y - body_half),
                (x, y - half),
                (x - half, y),
                (x, y + half),
                (x, y + body_half),
                (x + half, y + body_half),
            )
        elif direction == 4:
            # 向右：箭头顶点在右侧，箭身位于箭头左侧
            points = (
                (x - half, y - body_half),
                (x, y - body_half),
                (x, y - half),
                (x + half, y),
                (x, y + half),
                (x, y + body_half),
                (x - half, y + body_half),
            )
        else:
            return

        pygame.draw.polygon(surface, color, points)

    def get_cell_center(self, row, col, board_left, board_top):
        """返回指定棋盘格子的中心像素坐标。"""
        center_x = board_left + col * (self.CELL_SIZE + self.CELL_GAP) + self.CELL_SIZE // 2
        center_y = board_top + row * (self.CELL_SIZE + self.CELL_GAP) + self.CELL_SIZE // 2
        return center_x, center_y

    def draw_continuous_arrow(
        self,
        surface,
        cells,
        direction,
        board_left,
        board_top,
        offset=(0, 0),
        color_override=None,
    ):
        """将长箭头绘制成一个完整连续的多边形。

        长箭头的身体是覆盖多个格子的长条矩形；矩形宽度为三角形底边的一半，
        并且矩形的中轴线与三角形底边上的高重合。
        """
        color = self.ARROW_COLORS.get(direction, self.TEXT_COLOR)
        if color_override is not None:
            color = color_override
        tail_x, tail_y = self.get_cell_center(*cells[0], board_left, board_top)
        head_x, head_y = self.get_cell_center(*cells[-1], board_left, board_top)
        tail_x += offset[0]
        tail_y += offset[1]
        head_x += offset[0]
        head_y += offset[1]
        half = self.CELL_SIZE // 3
        # 长方形的宽为原身体宽度的一半，因此纵向偏移使用 half / 2
        body_half = half / 2

        if direction == 4:
            # 向右：身体长条从尾部延伸到三角形底边，三角形顶点朝右
            base_x = head_x - half
            points = (
                (tail_x - half, tail_y - body_half),
                (base_x, tail_y - body_half),
                (base_x, tail_y - half),
                (head_x + half, head_y),
                (base_x, tail_y + half),
                (base_x, tail_y + body_half),
                (tail_x - half, tail_y + body_half),
            )
        elif direction == 3:
            # 向左：三角形顶点朝左
            base_x = head_x + half
            points = (
                (tail_x + half, tail_y - body_half),
                (base_x, tail_y - body_half),
                (base_x, tail_y - half),
                (head_x - half, head_y),
                (base_x, tail_y + half),
                (base_x, tail_y + body_half),
                (tail_x + half, tail_y + body_half),
            )
        elif direction == 2:
            # 向下：三角形顶点朝下
            base_y = head_y - half
            points = (
                (tail_x - body_half, tail_y - half),
                (tail_x + body_half, tail_y - half),
                (tail_x + body_half, base_y),
                (tail_x + half, base_y),
                (head_x, head_y + half),
                (tail_x - half, base_y),
                (tail_x - body_half, base_y),
            )
        elif direction == 1:
            # 向上：三角形顶点朝上
            base_y = head_y + half
            points = (
                (tail_x - body_half, tail_y + half),
                (tail_x + body_half, tail_y + half),
                (tail_x + body_half, base_y),
                (tail_x + half, base_y),
                (head_x, head_y - half),
                (tail_x - half, base_y),
                (tail_x - body_half, base_y),
            )
        else:
            return

        pygame.draw.polygon(surface, color, points)

    def draw_arrow_group(
        self,
        surface,
        cells,
        direction,
        board_left,
        board_top,
        offset=(0, 0),
        color_override=None,
    ):
        """根据箭头占用的格子列表绘制单格或长条箭头。"""
        if len(cells) == 1:
            center = self.get_cell_center(*cells[0], board_left, board_top)
            self.draw_arrow(
                surface,
                center,
                direction,
                offset=offset,
                color_override=color_override,
            )
        else:
            self.draw_continuous_arrow(
                surface,
                cells,
                direction,
                board_left,
                board_top,
                offset=offset,
                color_override=color_override,
            )

    def collect_arrow_group(self, level_data, row, col):
        """收集与指定格子相连、方向一致的完整箭头格子列表。"""
        direction = level_data[row][col]
        dr, dc = self.DIRECTIONS[direction]

        # 先沿反方向找到该箭头最靠后的起点
        start_row, start_col = row, col
        prev_row = start_row - dr
        prev_col = start_col - dc
        while (
            0 <= prev_row < self.BOARD_SIZE
            and 0 <= prev_col < self.BOARD_SIZE
            and level_data[prev_row][prev_col] == direction
        ):
            start_row, start_col = prev_row, prev_col
            prev_row -= dr
            prev_col -= dc

        # 从起点沿箭头方向收集所有连续格子
        cells = []
        current_row, current_col = start_row, start_col
        while (
            0 <= current_row < self.BOARD_SIZE
            and 0 <= current_col < self.BOARD_SIZE
            and level_data[current_row][current_col] == direction
        ):
            cells.append((current_row, current_col))
            current_row += dr
            current_col += dc

        return cells

    def get_board_top_left(self):
        """计算棋盘左上角坐标，使 9x9 棋盘在窗口中居中显示。"""
        board_width = self.BOARD_SIZE * self.CELL_SIZE + (self.BOARD_SIZE - 1) * self.CELL_GAP
        board_height = self.BOARD_SIZE * self.CELL_SIZE + (self.BOARD_SIZE - 1) * self.CELL_GAP

        left = (self.screen.get_width() - board_width) // 2
        # 垂直方向略微下移，避免与顶部标题重叠
        top = (self.screen.get_height() - board_height) // 2 + 45
        return left, top

    def draw_board(self, level_data, skip_cells=None):
        """根据关卡二维数组渲染 9x9 棋盘和箭头。"""
        left, top = self.get_board_top_left()
        skip_cells = skip_cells or set()

        # 先绘制所有格子的背景和边框
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                cell_x = left + col * (self.CELL_SIZE + self.CELL_GAP)
                cell_y = top + row * (self.CELL_SIZE + self.CELL_GAP)
                cell_rect = pygame.Rect(cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE)

                # 先绘制格子背景和边框
                pygame.draw.rect(self.screen, self.BOARD_CELL_COLOR, cell_rect)
                pygame.draw.rect(self.screen, self.BOARD_GRID_COLOR, cell_rect, width=2)

        # 再绘制箭头，并把每个完整箭头作为一个整体，保证身体和头部无空隙
        visited = set()
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                direction = level_data[row][col]
                if not direction or (row, col) in visited or (row, col) in skip_cells:
                    continue

                cells = self.collect_arrow_group(level_data, row, col)
                visited.update(cells)
                self.draw_arrow_group(
                    self.screen,
                    cells,
                    direction,
                    left,
                    top,
                )

    def get_active_animation_cells(self):
        """返回当前动画箭头占用的格子，用于避免重复绘制。"""
        if self.flying_animation is not None:
            return set(self.flying_animation["cells"])
        if self.shake_animation is not None:
            return set(self.shake_animation["cells"])
        return set()

    @staticmethod
    def get_animation_progress(animation, eased=True):
        """计算动画进度，范围限制在 0 到 1 之间。"""
        progress = animation["elapsed"] / animation["duration"]
        progress = max(0.0, min(1.0, progress))
        if eased:
            # 使用缓出曲线，让飞出动画在结尾更平滑
            return 1 - (1 - progress) ** 2
        return progress

    def get_fly_offset(self, animation):
        """根据飞出动画进度计算当前箭头的像素偏移量。"""
        progress = self.get_animation_progress(animation, eased=True)
        direction = animation["direction"]
        cells = animation["cells"]
        left, top = self.get_board_top_left()

        board_width = self.BOARD_SIZE * self.CELL_SIZE + (self.BOARD_SIZE - 1) * self.CELL_GAP
        board_height = self.BOARD_SIZE * self.CELL_SIZE + (self.BOARD_SIZE - 1) * self.CELL_GAP
        margin = self.CELL_SIZE

        # 用箭头最尾部的格子计算距离，确保整个箭头都移出棋盘
        tail_x, tail_y = self.get_cell_center(*cells[0], left, top)

        if direction == 4:
            distance = left + board_width + margin - tail_x
            return distance * progress, 0
        if direction == 3:
            distance = tail_x - (left - margin)
            return -distance * progress, 0
        if direction == 2:
            distance = top + board_height + margin - tail_y
            return 0, distance * progress
        if direction == 1:
            distance = tail_y - (top - margin)
            return 0, -distance * progress
        return 0, 0

    def draw_flying_arrow(self):
        """绘制正在向边界外移动的箭头。"""
        animation = self.flying_animation
        left, top = self.get_board_top_left()
        offset = self.get_fly_offset(animation)
        self.draw_arrow_group(
            self.screen,
            animation["cells"],
            animation["direction"],
            left,
            top,
            offset=offset,
        )

    def draw_shaking_arrow(self):
        """绘制被阻挡时左右晃动并变红的箭头。"""
        animation = self.shake_animation
        progress = self.get_animation_progress(animation, eased=False)

        # 左右晃动 2 次，即 sin 完成 2 个完整周期
        shake_x = math.sin(progress * 4 * math.pi) * self.SHAKE_AMPLITUDE
        left, top = self.get_board_top_left()
        self.draw_arrow_group(
            self.screen,
            animation["cells"],
            animation["direction"],
            left,
            top,
            offset=(shake_x, 0),
            color_override=self.BLOCKED_COLOR,
        )

    def draw_active_animation(self):
        """根据当前动画状态绘制动画箭头。"""
        if self.flying_animation is not None:
            self.draw_flying_arrow()
        elif self.shake_animation is not None:
            self.draw_shaking_arrow()

    def draw_heart_icon(self, center_x, center_y, size, color, filled):
        """使用圆形和三角形绘制一个爱心图标。"""
        radius = size // 4
        circle_width = 0 if filled else 2

        # 左右两个圆弧构成爱心的上半部分
        pygame.draw.circle(
            self.screen,
            color,
            (center_x - radius, center_y - 2),
            radius,
            circle_width,
        )
        pygame.draw.circle(
            self.screen,
            color,
            (center_x + radius, center_y - 2),
            radius,
            circle_width,
        )

        # 下方三角形构成爱心尖角
        points = (
            (center_x - size // 2, center_y - 2),
            (center_x + size // 2, center_y - 2),
            (center_x, center_y + size // 2 + 2),
        )
        pygame.draw.polygon(self.screen, color, points, circle_width)

    def get_heart_position(self, index):
        """返回第 index 颗爱心在 HUD 中的中心坐标。"""
        label_surface = self.subtitle_font.render("剩余机会：", True, self.TEXT_COLOR)
        hearts_start_x = 20 + label_surface.get_width() + 8
        hearts_y = 18 + 30 + 30
        size = 24
        spacing = size + 8
        center_x = hearts_start_x + index * spacing + size // 2
        center_y = hearts_y + size // 2
        return center_x, center_y

    def draw_hearts(self):
        """在 HUD 中绘制剩余机会的爱心图标。"""
        size = 24

        for index in range(self.INITIAL_MISTAKES):
            center_x, center_y = self.get_heart_position(index)
            if index < self.mistakes_left:
                self.draw_heart_icon(
                    center_x,
                    center_y,
                    size,
                    self.HEART_COLOR,
                    filled=True,
                )
            else:
                self.draw_heart_icon(
                    center_x,
                    center_y,
                    size,
                    self.HEART_EMPTY_COLOR,
                    filled=False,
                )

    def spawn_heart_break(self, heart_index):
        """在指定爱心位置生成一组碎裂粒子。"""
        center_x, center_y = self.get_heart_position(heart_index)

        for _ in range(18):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(50, 150)
            self.heart_particles.append(
                {
                    "x": center_x,
                    "y": center_y,
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed - 35,
                    "life": random.uniform(0.35, 0.60),
                    "max_life": 0.60,
                    "size": random.randint(2, 5),
                    "color": random.choice(
                        (self.HEART_COLOR, (255, 145, 155), (190, 55, 75))
                    ),
                }
            )

    def draw_heart_particles(self):
        """绘制爱心碎裂粒子。"""
        for particle in self.heart_particles:
            life_ratio = max(0.0, particle["life"] / particle["max_life"])
            radius = max(1, int(particle["size"] * life_ratio))
            pygame.draw.circle(
                self.screen,
                particle["color"],
                (int(particle["x"]), int(particle["y"])),
                radius,
            )

    def draw_hud(self):
        """在左上角显示当前关卡、剩余箭头数和爱心图标。"""
        x, y = 20, 18

        lines = (
            f"当前关卡：{self.current_level}",
            f"剩余箭头：{self.remaining_arrows}",
        )
        for line in lines:
            text_surface = self.subtitle_font.render(line, True, self.TEXT_COLOR)
            self.screen.blit(text_surface, (x, y))
            y += 30

        # 第三行显示“剩余机会”和对应数量的爱心
        label_surface = self.subtitle_font.render("剩余机会：", True, self.TEXT_COLOR)
        self.screen.blit(label_surface, (x, y))
        self.draw_hearts()
        self.draw_heart_particles()

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

    def draw_result_button(self, button):
        """绘制通关或失败界面中的普通文字按钮。"""
        rect = button["rect"]
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)

        background = self.BUTTON_HOVER_COLOR if hovered else self.BUTTON_COLOR
        pygame.draw.rect(self.screen, background, rect, border_radius=14)
        pygame.draw.rect(self.screen, self.BUTTON_BORDER_COLOR, rect, width=2, border_radius=14)
        self.draw_text(self.screen, self.button_font, button["label"], self.BUTTON_TEXT_COLOR, rect.center)

    def draw_result_screen(self, title, subtitle, title_color):
        """绘制通关或失败界面共用的布局。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 160)
        self.draw_text(self.screen, self.title_font, title, title_color, title_center)

        subtitle_center = (self.screen.get_width() // 2, 230)
        self.draw_text(self.screen, self.subtitle_font, subtitle, self.MUTED_COLOR, subtitle_center)

        for button in self.build_result_buttons():
            self.draw_result_button(button)

    def draw_win_screen(self):
        """绘制通关界面。"""
        self.draw_result_screen("通关！", "所有箭头已成功清除", (130, 235, 150))

    def draw_lose_screen(self):
        """绘制失败界面。"""
        self.draw_result_screen("失败", "剩余机会已用完", self.ICON_X_COLOR)

    def draw_game(self):
        """绘制棋盘场景，显示 HUD、棋盘和当前动画。"""
        self.screen.fill(self.BG_COLOR)
        self.draw_hud()

        title_center = (self.screen.get_width() // 2, 80)
        self.draw_text(self.screen, self.title_font, "第 1 关", self.TITLE_COLOR, title_center)

        hint_center = (self.screen.get_width() // 2, 128)
        self.draw_text(self.screen, self.subtitle_font, "按 ESC 返回主菜单", self.MUTED_COLOR, hint_center)

        # 渲染棋盘和箭头
        skip_cells = self.get_active_animation_cells()
        self.draw_board(self.level_data, skip_cells=skip_cells)
        self.draw_active_animation()

    def draw(self):
        """根据当前场景绘制整个画面。"""
        if self.scene == "menu":
            self.draw_menu()
        elif self.scene == "settings":
            self.draw_settings()
        elif self.scene == "game":
            self.draw_game()
        elif self.scene == "win":
            self.draw_win_screen()
        elif self.scene == "lose":
            self.draw_lose_screen()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # 更新与主循环
    # ------------------------------------------------------------------
    def update_flying_animation(self, dt):
        """推进飞出动画，并在箭头移出棋盘后从数组中移除。"""
        animation = self.flying_animation
        animation["elapsed"] += dt

        if animation["elapsed"] >= animation["duration"]:
            for row, col in animation["cells"]:
                self.level_data[row][col] = 0

            self.remaining_arrows = max(0, self.remaining_arrows - 1)
            self.flying_animation = None

            if self.remaining_arrows == 0 and self.scene == "game":
                self.scene = "win"

    def update_shake_animation(self, dt):
        """推进被阻挡时的晃动动画，结束后恢复箭头颜色。"""
        animation = self.shake_animation
        animation["elapsed"] += dt

        if animation["elapsed"] >= animation["duration"]:
            self.shake_animation = None
            if self.mistakes_left <= 0 and self.scene == "game":
                self.scene = "lose"

    def update_heart_particles(self, dt):
        """更新爱心碎裂粒子的位置和生命周期。"""
        for particle in self.heart_particles[:]:
            particle["life"] -= dt
            if particle["life"] <= 0:
                self.heart_particles.remove(particle)
                continue

            # 粒子受轻微重力影响，并持续向外飞散
            particle["vy"] += 180 * dt
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt

    def update(self, dt):
        """更新动画状态。"""
        if self.flying_animation is not None:
            self.update_flying_animation(dt)
        if self.shake_animation is not None:
            self.update_shake_animation(dt)
        self.update_heart_particles(dt)

    def run(self):
        """运行游戏主循环，直到收到退出请求。"""
        while self.running:
            # 限制帧率，并把实际帧间隔传给动画更新，保证动画速度稳定
            dt = self.clock.tick(self.FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()


def main():
    """程序入口：创建游戏实例并启动主循环。"""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
