"""touhou-arrow game 开始界面与基础窗口模块。

本文件负责：
1. 创建 800x600 的游戏窗口，并支持窗口/全屏模式切换。
2. 显示带图标的主菜单（开始游戏、设置、离开游戏）。
3. 提供设置界面，用开关切换窗口模式和全屏模式。
4. 渲染 9x9 棋盘，并根据关卡二维数组显示不同颜色的方向箭头。
5. 部分箭头由 1 个三角形和 2-3 格长条身体组成，并规避格子重叠。
6. 检测点击的箭头是否能飞出棋盘，并在控制台输出结果。
7. 以 60FPS 运行完整主循环。
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
        # 当前要渲染的关卡数据，生成时已规避长箭头之间的格子重叠
        self.level_data = self.generate_level()

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

    def generate_level(self):
        """生成一个 9x9 的关卡二维数组。

        生成规则：
        - 0 表示空格，1/2/3/4 分别表示上、下、左、右箭头。
        - 约 10% 的箭头为长箭头，由 2-3 格长条身体和 1 个三角形箭头组成。
        - 长箭头优先放置，剩余箭头只在空格上放置，因此不会发生格子重叠。
        """
        # 使用固定随机种子，保证每次运行时测试关卡保持一致
        rng = random.Random(20260918)

        board = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
        empty_cells = {
            (row, col)
            for row in range(self.BOARD_SIZE)
            for col in range(self.BOARD_SIZE)
        }

        long_arrow_count = max(1, round(self.TOTAL_ARROWS * self.LONG_ARROW_RATIO))
        single_arrow_count = self.TOTAL_ARROWS - long_arrow_count

        # 先放置长箭头，避免它们与后续箭头争抢同一片连续格子
        for _ in range(long_arrow_count):
            self.place_long_arrow(board, empty_cells, rng)

        # 再放置普通单格箭头
        for _ in range(single_arrow_count):
            self.place_single_arrow(board, empty_cells, rng)

        return board

    def place_long_arrow(self, board, empty_cells, rng):
        """在棋盘上放置一个长箭头，并更新空格集合。"""
        direction = rng.choice([1, 2, 3, 4])
        # 身体长条占 2 或 3 个格子，再加上 1 个三角形头部
        body_count = rng.choice([2, 3])
        total_length = body_count + 1

        dr, dc = self.DIRECTIONS[direction]
        valid_starts = []

        # 找出所有能完整容纳该长箭头的起点
        for row, col in empty_cells:
            cells = [
                (row + dr * index, col + dc * index)
                for index in range(total_length)
            ]
            if all(
                0 <= cell_row < self.BOARD_SIZE
                and 0 <= cell_col < self.BOARD_SIZE
                and (cell_row, cell_col) in empty_cells
                for cell_row, cell_col in cells
            ):
                valid_starts.append((row, col))

        if not valid_starts:
            return

        start_row, start_col = rng.choice(valid_starts)

        # 将长箭头占用的格子全部标记为该方向
        for index in range(total_length):
            cell_row = start_row + dr * index
            cell_col = start_col + dc * index
            board[cell_row][cell_col] = direction
            empty_cells.discard((cell_row, cell_col))

    def place_single_arrow(self, board, empty_cells, rng):
        """在剩余空格中放置一个普通单格箭头。"""
        if not empty_cells:
            return

        row, col = rng.choice(tuple(empty_cells))
        direction = rng.choice([1, 2, 3, 4])
        board[row][col] = direction
        empty_cells.discard((row, col))

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

    def handle_board_click(self, mouse_pos):
        """根据鼠标点击位置找到箭头，并在控制台打印路径检测结果。"""
        cell = self.get_cell_from_mouse(mouse_pos)
        if cell is None:
            print("点击位置不在棋盘格子内")
            return

        row, col = cell
        direction = self.level_data[row][col]
        if direction == 0:
            print(f"格子 ({row}, {col}) 为空，无箭头")
            return

        direction_names = {1: "上", 2: "下", 3: "左", 4: "右"}
        if self.can_arrow_fly_out(row, col, direction):
            print(f"格子 ({row}, {col})：{direction_names[direction]}方向箭头 -> 可飞出")
        else:
            print(f"格子 ({row}, {col})：{direction_names[direction]}方向箭头 -> 被阻挡")

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

        点击后进入棋盘渲染场景，展示第 1 关测试数据。
        """
        self.scene = "game"

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

    def draw_arrow(self, surface, center, direction):
        """根据方向值在指定中心绘制三角形箭头。

        方向约定：1=上，2=下，3=左，4=右。
        """
        x, y = center
        half = self.CELL_SIZE // 3
        color = self.ARROW_COLORS.get(direction, self.TEXT_COLOR)

        if direction == 1:
            # 向上：顶点在上方
            points = ((x, y - half), (x - half, y + half), (x + half, y + half))
        elif direction == 2:
            # 向下：顶点在下方
            points = ((x, y + half), (x - half, y - half), (x + half, y - half))
        elif direction == 3:
            # 向左：顶点在左侧
            points = ((x - half, y), (x + half, y - half), (x + half, y + half))
        elif direction == 4:
            # 向右：顶点在右侧
            points = ((x + half, y), (x - half, y - half), (x - half, y + half))
        else:
            return

        pygame.draw.polygon(surface, color, points)

    def get_cell_center(self, row, col, board_left, board_top):
        """返回指定棋盘格子的中心像素坐标。"""
        center_x = board_left + col * (self.CELL_SIZE + self.CELL_GAP) + self.CELL_SIZE // 2
        center_y = board_top + row * (self.CELL_SIZE + self.CELL_GAP) + self.CELL_SIZE // 2
        return center_x, center_y

    def draw_continuous_arrow(self, surface, cells, direction, board_left, board_top):
        """将长箭头绘制成一个完整连续的多边形。

        长箭头的身体是覆盖多个格子的长条矩形；矩形宽度为三角形底边的一半，
        并且矩形的中轴线与三角形底边上的高重合。
        """
        color = self.ARROW_COLORS.get(direction, self.TEXT_COLOR)
        tail_x, tail_y = self.get_cell_center(*cells[0], board_left, board_top)
        head_x, head_y = self.get_cell_center(*cells[-1], board_left, board_top)
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

    def draw_board(self, level_data):
        """根据关卡二维数组渲染 9x9 棋盘和箭头。"""
        left, top = self.get_board_top_left()

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
                if not direction or (row, col) in visited:
                    continue

                cells = self.collect_arrow_group(level_data, row, col)
                visited.update(cells)

                if len(cells) == 1:
                    center = self.get_cell_center(row, col, left, top)
                    self.draw_arrow(self.screen, center, direction)
                else:
                    self.draw_continuous_arrow(
                        self.screen,
                        cells,
                        direction,
                        left,
                        top,
                    )

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

    def draw_game(self):
        """绘制棋盘场景，展示第 1 关的测试箭头数据。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 80)
        self.draw_text(self.screen, self.title_font, "第 1 关", self.TITLE_COLOR, title_center)

        hint_center = (self.screen.get_width() // 2, 128)
        self.draw_text(self.screen, self.subtitle_font, "按 ESC 返回主菜单", self.MUTED_COLOR, hint_center)

        # 渲染棋盘和箭头
        self.draw_board(self.level_data)

    def draw(self):
        """根据当前场景绘制整个画面。"""
        if self.scene == "menu":
            self.draw_menu()
        elif self.scene == "settings":
            self.draw_settings()
        elif self.scene == "game":
            self.draw_game()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # 更新与主循环
    # ------------------------------------------------------------------
    def update(self):
        """更新游戏逻辑。当前阶段只做路径检测，不做消除或动画。"""
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
