"""arrow-game 开始界面与基础窗口模块。

本文件负责：
1. 创建 800x600 的游戏窗口，并支持窗口/全屏模式切换。
2. 显示主菜单、选关界面和三个可通关的 9x9/11x11/13x13 关卡。
3. 提供设置界面，用开关切换窗口模式和全屏模式。
4. 渲染 9x9 棋盘，并根据关卡二维数组显示不同颜色的方向箭头。
5. 第一关使用直线箭头；第二、三关使用可弯折的蛇形多段箭头。
6. 检测点击的箭头是否能飞出棋盘，并在控制台输出结果。
7. 播放飞出/阻挡动画，显示关卡、剩余箭头，并在扣除机会时播放爱心碎裂特效。
8. 清除全部箭头后进入通关界面，机会耗尽后进入失败界面。
9. 支持关卡重开、返回选关界面和返回大厅。
10. 以 60FPS 运行完整主循环。
"""

import copy
from array import array
import math
import random
import sys

import pygame


class Game:
    """游戏主类，封装窗口、场景切换、事件处理与主循环。"""

    # 窗口模式下的显示尺寸
    WINDOW_SIZE = (800, 600)
    # 游戏窗口标题
    TITLE = "arrow-game"
    # 目标帧率
    FPS = 60

    # 棋盘配置：9x9 网格，格子尺寸按窗口大小适当缩小
    BOARD_SIZE = 9
    CELL_SIZE = 40
    CELL_GAP = 2

    # 三个关卡配置：棋盘尺寸、格子像素大小和箭头总数
    LEVELS = {
        1: {"size": 9, "cell_size": 40, "total_arrows": 20},
        2: {"size": 11, "cell_size": 36, "total_arrows": 24},
        3: {"size": 13, "cell_size": 32, "total_arrows": 34},
    }

    # 箭头总数，以及其中使用 2-3 个正方形组成的长箭头占比
    TOTAL_ARROWS = 20
    LONG_ARROW_RATIO = 0.10
    INITIAL_MISTAKES = 3

    # 动画参数
    FLY_DURATION = 0.30
    SNAKE_STEP_INTERVAL = 0.08
    SNAKE_MULTI_STEP_INTERVAL = 0.045
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
        self.init_sounds()

        self.clock = pygame.time.Clock()
        self.running = True

        # True 表示全屏，False 表示窗口模式
        self.is_fullscreen = False
        # 当前界面：menu 为主菜单，settings 为设置界面
        self.scene = "menu"
        # 默认加载第 1 关，并初始化该关卡的棋盘尺寸、箭头数和关卡数据
        self.current_level = 1
        # 缓存每个关卡的原始生成结果，重新开始时直接复制，避免重复生成。
        self.level_cache = {}
        self.apply_level_config(self.current_level)

        # 当前正在播放的箭头动画；同一时间只播放一个
        self.flying_animation = None
        self.shake_animation = None
        self.snake_flying_animation = None
        # 爱心扣除时产生的碎裂粒子
        self.heart_particles = []
        # 得分、计时与无尽模式状态
        self.score = 0
        self.elapsed_time = 0.0
        self.endless_mode = False

        self.screen = pygame.display.set_mode(self.WINDOW_SIZE)
        pygame.display.set_caption(self.TITLE)

        # 优先使用系统中常见的中文字体，避免按钮文字显示为方框
        self.title_font = self._load_font(52)
        self.subtitle_font = self._load_font(24)
        self.button_font = self._load_font(28)
        self.setting_font = self._load_font(30)

        # 提前生成第三关，后续选择第三关时直接使用缓存。
        self.preload_third_level()

    @staticmethod
    def _load_font(size):
        """创建指定大小的中文字体对象。"""
        font_names = ["microsoftyahei", "msyh", "simhei", "simsun"]
        return pygame.font.SysFont(font_names, size)

    def init_sounds(self):
        """初始化简单音效；音频设备不可用时静默降级。"""
        self.sound_error = None
        self.sound_success = None
        self.sound_ok = False

        try:
            pygame.mixer.init(22050, -16, 1, 512)
            self.sound_error = self._make_tone(160, 0.12, 0.25)
            self.sound_success = self._make_metal_sound()
            self.sound_ok = True
        except Exception:
            self.sound_ok = False

    @staticmethod
    def _make_tone(frequency, duration, volume):
        """生成一个简单的正弦波音效。"""
        sample_rate = 22050
        sample_count = int(sample_rate * duration)
        samples = array("h")
        for index in range(sample_count):
            value = int(
                math.sin(2 * math.pi * frequency * index / sample_rate)
                * volume
                * 32767
            )
            samples.append(value)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _make_metal_sound(self):
        """生成一个短促、带衰减的醇厚金属音。"""
        sample_rate = 22050
        duration = 0.28
        sample_count = int(sample_rate * duration)
        samples = array("h")

        for index in range(sample_count):
            time = index / sample_rate
            envelope = math.exp(-12.0 * time)
            value = (
                math.sin(2 * math.pi * 880 * time) * 0.35
                + math.sin(2 * math.pi * 1320 * time) * 0.22
                + math.sin(2 * math.pi * 1760 * time) * 0.12
            )
            samples.append(int(value * envelope * 32767))

        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play_sound(self, sound):
        """播放音效，音频不可用时直接忽略。"""
        if self.sound_ok and sound is not None:
            sound.play()

    def apply_level_config(self, level_number):
        """按关卡编号设置棋盘尺寸、格子大小和箭头数量，并生成关卡。"""
        config = self.LEVELS[level_number]
        self.current_level = level_number
        self.BOARD_SIZE = config["size"]
        self.CELL_SIZE = config["cell_size"]
        self.TOTAL_ARROWS = config["total_arrows"]

        self.use_snake_movement = level_number > 1

        if level_number in self.level_cache:
            cached_level = self.level_cache[level_number]
            if self.use_snake_movement:
                self.arrows = copy.deepcopy(cached_level["arrows"])
                self.snake_grid = copy.deepcopy(cached_level["snake_grid"])
                self.level_data = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
            else:
                self.level_data = copy.deepcopy(cached_level["level_data"])
                self.arrows = None
                self.snake_grid = None
        else:
            if self.use_snake_movement:
                # 第二、三关使用可弯折的多段箭头
                self.arrows = self.generate_snake_level()
                self.level_data = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
                self.level_cache[level_number] = {
                    "arrows": copy.deepcopy(self.arrows),
                    "snake_grid": copy.deepcopy(self.snake_grid),
                }
            else:
                # 第一关保持原来的直线箭头生成方式
                self.LONG_ARROW_RATIO = 0.0
                self.level_data = self.generate_level()
                self.arrows = None
                self.snake_grid = None
                self.level_cache[level_number] = {
                    "level_data": copy.deepcopy(self.level_data),
                }

        self.remaining_arrows = (
            len(self.arrows) if self.use_snake_movement else self.count_arrow_groups(self.level_data)
        )

        self.mistakes_left = self.INITIAL_MISTAKES
        self.flying_animation = None
        self.shake_animation = None
        self.snake_animation = None
        self.snake_flying_animation = None
        self.heart_particles = []

    def preload_third_level(self):
        """提前生成第三关并写入缓存，避免首次点击第三关时阻塞。"""
        if 3 in self.level_cache:
            return

        config = self.LEVELS[3]
        self.current_level = 3
        self.BOARD_SIZE = config["size"]
        self.CELL_SIZE = config["cell_size"]
        self.TOTAL_ARROWS = config["total_arrows"]
        self.use_snake_movement = True

        arrows = self.generate_snake_level()
        self.level_cache[3] = {
            "arrows": copy.deepcopy(arrows),
            "snake_grid": copy.deepcopy(self.snake_grid),
        }

        # 恢复初始第一关状态，避免预生成影响启动界面。
        self.apply_level_config(1)

    def generate_snake_level(self, base_seed=None):
        """生成第二、三关使用的可弯折多段箭头。"""
        if base_seed is None:
            base_seed = 20260919

        for attempt in range(200):
            rng = random.Random(base_seed + attempt)
            arrows, grid = self.try_build_snake_level(rng)
            if arrows is not None and self.has_snake_solution(arrows, grid):
                self.snake_grid = grid
                return arrows
        raise RuntimeError("无法生成可弯折箭头关卡")

    def try_build_snake_level(self, rng):
        """尝试生成一组不重叠的可弯折箭头。"""
        size = self.BOARD_SIZE
        grid = [[0 for _ in range(size)] for _ in range(size)]
        occupied = set()
        empty_cells = {
            (row, col)
            for row in range(size)
            for col in range(size)
        }
        empty_cells_list = list(empty_cells)
        arrows = []

        multi_count = round(self.TOTAL_ARROWS * 0.80)
        single_count = self.TOTAL_ARROWS - multi_count
        if self.current_level == 3 or self.endless_mode:
            # 第三关将两弯折及以上的多格箭头占比提高到约 50%。
            one_bend_count = multi_count // 2
            multi_bend_count = multi_count - one_bend_count
        else:
            # 第二关仍保持：多格箭头中 80% 一次弯折，20% 多次弯折。
            one_bend_count = round(multi_count * 0.80)
            multi_bend_count = multi_count - one_bend_count
        single_attempts = 300 if size >= 13 else 150
        one_bend_attempts = 500 if size >= 13 else 250
        multi_bend_attempts = 700 if size >= 13 else 350

        # 单格箭头
        for _ in range(single_count):
            placed = False
            for _ in range(single_attempts):
                if not empty_cells:
                    return None, None

                row, col = rng.choice(empty_cells_list)
                direction = rng.choice([1, 2, 3, 4])
                candidate = {"cells": [(row, col)], "direction": direction}

                if self.is_snake_arrow_path_clear(candidate, grid):
                    self.commit_snake_arrow(
                        candidate,
                        occupied,
                        empty_cells,
                        empty_cells_list,
                        grid,
                        arrows,
                    )
                    placed = True
                    break

            if not placed:
                return None, None

        # 一次弯折的多格箭头
        for _ in range(one_bend_count):
            placed = False
            for _ in range(one_bend_attempts):
                path = self.generate_bent_path(
                    empty_cells,
                    empty_cells_list,
                    rng,
                    min_bends=1,
                    max_bends=1,
                )
                if path is None:
                    continue

                candidate = self.make_snake_arrow_candidate(path)
                if self.is_snake_arrow_path_clear(candidate, grid):
                    self.commit_snake_arrow(
                        candidate,
                        occupied,
                        empty_cells,
                        empty_cells_list,
                        grid,
                        arrows,
                    )
                    placed = True
                    break

            if not placed:
                return None, None

        # 二次及以上弯折的多格箭头
        for _ in range(multi_bend_count):
            placed = False
            for _ in range(multi_bend_attempts):
                path = self.generate_bent_path(
                    empty_cells,
                    empty_cells_list,
                    rng,
                    min_bends=2,
                    max_bends=5,
                )
                if path is None:
                    continue

                candidate = self.make_snake_arrow_candidate(path)
                if self.is_snake_arrow_path_clear(candidate, grid):
                    self.commit_snake_arrow(
                        candidate,
                        occupied,
                        empty_cells,
                        empty_cells_list,
                        grid,
                        arrows,
                    )
                    placed = True
                    break

            if not placed:
                return None, None

        return arrows, grid

    def register_snake_arrow(self, tail_to_head_path, occupied, grid, arrows):
        """将生成好的路径转换为头到尾顺序，并写入占用网格。"""
        cells = list(reversed(tail_to_head_path))
        arrow_id = len(arrows) + 1

        for row, col in cells:
            occupied.add((row, col))
            grid[row][col] = arrow_id

        if len(cells) == 1:
            direction = 1
        else:
            direction = self.direction_between(cells[1], cells[0])

        arrows.append({"cells": cells, "direction": direction})

    def make_snake_arrow_candidate(self, tail_to_head_path):
        """根据路径创建候选箭头字典，不修改任何网格。"""
        cells = list(reversed(tail_to_head_path))
        if len(cells) == 1:
            direction = 1
        else:
            direction = self.direction_between(cells[1], cells[0])
        return {"cells": cells, "direction": direction}

    def commit_snake_arrow(self, arrow, occupied, empty_cells, empty_cells_list, grid, arrows):
        """把通过路径检测的候选箭头正式写入占用数据。"""
        arrow_id = len(arrows) + 1
        for row, col in arrow["cells"]:
            occupied.add((row, col))
            if (row, col) in empty_cells:
                empty_cells.remove((row, col))
                empty_cells_list.remove((row, col))
            grid[row][col] = arrow_id
        arrows.append(arrow)

    def generate_bent_path(self, empty_cells, empty_cells_list, rng, min_bends, max_bends):
        """随机生成一条满足弯折次数要求的路径。

        使用 O(1) 的 empty_cells_list 选取起点，避免反复把集合转成 tuple。
        """
        size = self.BOARD_SIZE
        path_attempts = 300 if size >= 13 else 150

        for _ in range(path_attempts):
            if not empty_cells_list:
                return None

            target_length = rng.randint(3, min(6, size))
            start_row, start_col = rng.choice(empty_cells_list)
            path = [(start_row, start_col)]
            previous_direction = None
            bends = 0

            while len(path) < target_length:
                directions = [1, 2, 3, 4]
                rng.shuffle(directions)
                placed = False

                for direction in directions:
                    dr, dc = self.DIRECTIONS[direction]
                    next_row = path[-1][0] + dr
                    next_col = path[-1][1] + dc

                    if not (
                        0 <= next_row < size
                        and 0 <= next_col < size
                        and (next_row, next_col) in empty_cells
                        and (next_row, next_col) not in path
                    ):
                        continue

                    if previous_direction is not None and direction == self.opposite_direction(previous_direction):
                        continue

                    new_bends = bends
                    if previous_direction is not None and direction != previous_direction:
                        new_bends += 1

                    if new_bends > max_bends:
                        continue

                    remaining = target_length - len(path) - 1
                    if new_bends + remaining < min_bends:
                        continue

                    path.append((next_row, next_col))
                    previous_direction = direction
                    bends = new_bends
                    placed = True
                    break

                if not placed:
                    break

            if len(path) == target_length and min_bends <= bends <= max_bends:
                return path

        return None

    def build_template_path(self, start, directions, step_counts):
        """按方向和步数模板生成路径，任何越界/占用都返回 None。"""
        size = self.BOARD_SIZE
        path = [start]

        for direction, steps in zip(directions, step_counts):
            dr, dc = self.DIRECTIONS[direction]
            for _ in range(steps):
                row = path[-1][0] + dr
                col = path[-1][1] + dc
                if not (
                    0 <= row < size
                    and 0 <= col < size
                    and (row, col) in self._current_empty_cells
                    and (row, col) not in path
                ):
                    return None
                path.append((row, col))

        return path

    def generate_one_bend_path(self, empty_cells_list, rng):
        """一次弯折模板：直走一段 -> 转一次 -> 继续直走。"""
        if not empty_cells_list:
            return None

        size = self.BOARD_SIZE
        target_length = rng.randint(3, min(6, size))

        for _ in range(120):
            start = rng.choice(empty_cells_list)
            first_direction = rng.choice([1, 2, 3, 4])
            second_direction = rng.choice(
                [d for d in (1, 2, 3, 4) if d not in (first_direction, self.opposite_direction(first_direction))]
            )

            first_steps = rng.randint(1, target_length - 2)
            second_steps = target_length - 1 - first_steps
            path = self.build_template_path(
                start,
                (first_direction, second_direction),
                (first_steps, second_steps),
            )
            if path is not None:
                return path

        return None

    def generate_multi_bend_path(self, empty_cells_list, rng, min_bends, max_bends):
        """多次弯折模板：至少转两次，适合第三关 50% 的多次弯折箭头。"""
        if not empty_cells_list:
            return None

        size = self.BOARD_SIZE
        target_length = rng.randint(4, min(6, size))

        for _ in range(160):
            start = rng.choice(empty_cells_list)
            first_direction = rng.choice([1, 2, 3, 4])
            second_direction = rng.choice(
                [d for d in (1, 2, 3, 4) if d not in (first_direction, self.opposite_direction(first_direction))]
            )
            third_direction = rng.choice(
                [d for d in (1, 2, 3, 4) if d not in (second_direction, self.opposite_direction(second_direction))]
            )

            # 至少三段：a + b + c = target_length - 1
            total_steps = target_length - 1
            first_steps = rng.randint(1, total_steps - 2)
            remaining = total_steps - first_steps
            second_steps = rng.randint(1, remaining - 1)
            third_steps = remaining - second_steps

            path = self.build_template_path(
                start,
                (first_direction, second_direction, third_direction),
                (first_steps, second_steps, third_steps),
            )
            if path is not None:
                bends = 2 if second_direction != first_direction and third_direction != second_direction else 3
                if min_bends <= bends <= max_bends:
                    return path

        return None

    @staticmethod
    def opposite_direction(direction):
        """返回相反方向。"""
        return {1: 2, 2: 1, 3: 4, 4: 3}[direction]

    def direction_between(self, from_cell, to_cell):
        """返回从一个格子到相邻格子的方向编码。"""
        dr = to_cell[0] - from_cell[0]
        dc = to_cell[1] - from_cell[1]
        for direction, (expected_dr, expected_dc) in self.DIRECTIONS.items():
            if (dr, dc) == (expected_dr, expected_dc):
                return direction
        return 1

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

            long_arrow_count = round(self.TOTAL_ARROWS * self.LONG_ARROW_RATIO)
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
            elif self.scene == "level_select":
                self.handle_level_select_events(event)
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

        鼠标左键用于点击棋盘箭头或右上角按钮，ESC 用于退回选关界面。
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.scene = "menu"
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 优先处理右上角的重新开始和返回选关按钮
            if self.get_game_restart_button_rect().collidepoint(event.pos):
                self.reset_game()
                return
            if self.get_game_level_select_button_rect().collidepoint(event.pos):
                self.scene = "level_select"
                return

            self.handle_board_click(event.pos)

    def handle_result_events(self, event):
        """处理通关或失败界面中的按钮点击。"""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        for button in self.build_result_buttons():
            if not button.get("enabled", True):
                continue
            if button["rect"].collidepoint(event.pos):
                button["action"]()
                break

    def handle_level_select_events(self, event):
        """处理选关界面中的关卡按钮点击。"""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        for button in self.build_level_select_buttons():
            if button["rect"].collidepoint(event.pos):
                button["action"]()
                break

    def handle_board_click(self, mouse_pos):
        """根据鼠标点击位置检测箭头，并触发飞出或被阻挡动画。"""
        if self.use_snake_movement:
            self.handle_snake_board_click(mouse_pos)
            return

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
            self.play_sound(self.sound_error)
            # 在爱心扣除前，先为即将消失的爱心生成碎裂粒子
            if self.mistakes_left > 0:
                self.spawn_heart_break(self.mistakes_left - 1)
            # 每次被阻挡扣 1 次失误，最低保持为 0
            self.mistakes_left = max(0, self.mistakes_left - 1)
            self.start_shake_animation(cells, direction)

    def handle_snake_board_click(self, mouse_pos):
        """处理第二、三关的蛇形箭头发射。"""
        if (
            self.snake_animation is not None
            or self.snake_flying_animation is not None
            or self.shake_animation is not None
        ):
            print("箭头移动中，请稍候")
            return

        cell = self.get_cell_from_mouse(mouse_pos)
        if cell is None:
            print("点击位置不在棋盘格子内")
            return

        row, col = cell
        if self.snake_grid[row][col] == 0:
            print(f"格子 ({row}, {col}) 为空，无箭头")
            return

        # 找到被点击的箭头
        for index, arrow in enumerate(self.arrows):
            if not arrow["cells"]:
                continue
            if (row, col) in arrow["cells"]:
                if not self.can_snake_arrow_fly_out(index):
                    self.trigger_snake_blocked(index)
                elif len(arrow["cells"]) == 1:
                    # 单格箭头用一格的像素飞出动画，避免在边界瞬间消失。
                    self.start_snake_fly_animation(index)
                else:
                    self.snake_animation = {
                        "arrow_index": index,
                        "elapsed": 0.0,
                        "step_interval": self.SNAKE_MULTI_STEP_INTERVAL,
                    }
                    print(f"箭头 {index + 1} 开始移动")
                return

    def can_snake_arrow_step(self, arrow_index):
        """只读判断蛇形箭头下一步的状态，不修改 cells 和 snake_grid。

        返回：
        - "fly_out"：下一步越界，可以飞出棋盘
        - "blocked"：下一步会被其他箭头阻挡
        - "move"：下一步可以正常移动
        """
        arrow = self.arrows[arrow_index]
        cells = arrow["cells"]
        direction = arrow["direction"]
        dr, dc = self.DIRECTIONS[direction]

        head_row, head_col = cells[0]
        next_row = head_row + dr
        next_col = head_col + dc

        if not (0 <= next_row < self.BOARD_SIZE and 0 <= next_col < self.BOARD_SIZE):
            return "fly_out"

        next_grid_id = self.snake_grid[next_row][next_col]
        if next_grid_id != 0 and (next_row, next_col) != cells[-1]:
            return "blocked"

        return "move"

    def can_snake_arrow_fly_out(self, arrow_index):
        """只读判断蛇形箭头从头部到棋盘边界之间是否全程无阻挡。

        从 cells[0] 的头部开始，沿 direction 对应的 (dr, dc) 逐格检查。
        途中只要 snake_grid 上有非 0 格子，就返回 False。
        一路到棋盘外都没有障碍，才返回 True。
        """
        arrow = self.arrows[arrow_index]
        return self.is_snake_arrow_path_clear(arrow, self.snake_grid)

    def is_snake_arrow_path_clear(self, arrow, grid):
        """只读判断一个蛇形箭头前方路径是否完全没有阻挡。"""
        direction = arrow["direction"]
        dr, dc = self.DIRECTIONS[direction]
        head_row, head_col = arrow["cells"][0]
        check_row = head_row + dr
        check_col = head_col + dc

        while 0 <= check_row < self.BOARD_SIZE and 0 <= check_col < self.BOARD_SIZE:
            if grid[check_row][check_col] != 0:
                return False
            check_row += dr
            check_col += dc

        return True

    def has_snake_solution(self, arrows, grid):
        """检测一组蛇形箭头是否存在一个可以全部消除的点击顺序。"""
        arrows_copy = [
            {"cells": list(arrow["cells"]), "direction": arrow["direction"]}
            for arrow in arrows
        ]
        grid_copy = [row[:] for row in grid]
        remaining = len(arrows_copy)

        while remaining > 0:
            removed_this_round = False

            for arrow in arrows_copy:
                if not arrow["cells"]:
                    continue

                if self.is_snake_arrow_path_clear(arrow, grid_copy):
                    for row, col in arrow["cells"]:
                        if 0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE:
                            grid_copy[row][col] = 0
                    arrow["cells"] = []
                    remaining -= 1
                    removed_this_round = True
                    break

            if not removed_this_round:
                return False

        return True

    def step_snake_arrow(self, arrow_index):
        """让蛇形箭头前进一步。

        返回 True 表示本次移动完成；越界飞出或被阻挡时会启动对应动画并返回 False。
        """
        arrow = self.arrows[arrow_index]
        step_status = self.can_snake_arrow_step(arrow_index)

        # 下一步被阻挡时，先触发碰撞反馈，不移动原箭头
        if step_status == "blocked":
            self.trigger_snake_blocked(arrow_index)
            return False

        # cells[0] 是头部，后面依次是身体各段
        # 必须先完整备份旧坐标，不能边遍历边修改原数组
        old_cells = arrow["cells"].copy()
        direction = arrow["direction"]
        dr, dc = self.DIRECTIONS[direction]

        # 1. 先保存上一帧头部坐标，供身体段依次跟随
        old_head = old_cells[0]

        # 2. 预判头部下一格
        new_head = (old_head[0] + dr, old_head[1] + dc)
        new_row, new_col = new_head

        arrow_id = arrow_index + 1
        old_tail = old_cells[-1]

        # 蛇式移动：新头部插到最前，身体段使用旧坐标，去掉旧尾巴。
        new_cells = [new_head]
        for index in range(1, len(old_cells)):
            new_cells.append(old_cells[index - 1])

        # 更新占用网格：旧尾巴让出，新头部占入。
        # 如果新头部已经越界，则只清除旧尾巴，不写入 outside_head。
        self.snake_grid[old_tail[0]][old_tail[1]] = 0
        if 0 <= new_row < self.BOARD_SIZE and 0 <= new_col < self.BOARD_SIZE:
            self.snake_grid[new_row][new_col] = arrow_id

        arrow["cells"] = new_cells

        # 当所有身体段都已经移出棋盘后，再正式移除箭头。
        if all(
            not (0 <= cell[0] < self.BOARD_SIZE and 0 <= cell[1] < self.BOARD_SIZE)
            for cell in new_cells
        ):
            self.remove_snake_arrow(arrow_index)

        return True

    def is_arrow_straight(self, arrow):
        """判断蛇形箭头是否已经变成一条完整直线。"""
        cells = arrow["cells"]
        if len(cells) <= 2:
            return True

        dr, dc = self.DIRECTIONS[arrow["direction"]]
        for index in range(len(cells) - 1):
            current = cells[index]
            next_cell = cells[index + 1]
            if (current[0] - next_cell[0], current[1] - next_cell[1]) != (dr, dc):
                return False
        return True

    def remove_snake_arrow(self, arrow_index):
        """移除一条已经飞出边界的蛇形箭头。"""
        arrow = self.arrows[arrow_index]
        for row, col in arrow["cells"]:
            # 部分身体段可能已经移动到棋盘外，不能继续索引 snake_grid。
            if 0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE:
                self.snake_grid[row][col] = 0

        arrow["cells"] = []
        self.remaining_arrows = max(0, self.remaining_arrows - 1)
        self.score += 10
        self.play_sound(self.sound_success)

        if self.remaining_arrows == 0 and self.scene == "game":
            self.scene = "win"

    def trigger_snake_blocked(self, arrow_index):
        """蛇形箭头被阻挡时触发爱心扣减和红色晃动反馈，但不移动箭头。"""
        arrow = self.arrows[arrow_index]
        self.play_sound(self.sound_error)

        if self.mistakes_left > 0:
            self.spawn_heart_break(self.mistakes_left - 1)
        self.mistakes_left = max(0, self.mistakes_left - 1)

        self.shake_animation = {
            "cells": list(arrow["cells"]),
            "direction": arrow["direction"],
            "elapsed": 0.0,
            "duration": self.SHAKE_DURATION,
            "snake": True,
        }

    def start_snake_fly_animation(self, arrow_index):
        """开始蛇形箭头的连续飞出动画，动画结束后才从网格移除。"""
        arrow = self.arrows[arrow_index]
        self.snake_flying_animation = {
            "arrow_index": arrow_index,
            "direction": arrow["direction"],
            "elapsed": 0.0,
            "duration": self.FLY_DURATION,
        }

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

        items = (
            {"label": "开始游戏", "icon": "triangle", "action": self.action_start_game},
            {"label": "设置", "icon": "gear", "action": self.action_open_settings},
            {"label": "离开游戏", "icon": "x", "action": self.action_quit_game},
        )

        # 按钮列整体居中，并在垂直方向上稍微偏下，为标题留出空间
        total_height = len(items) * button_height + (len(items) - 1) * gap
        start_y = self.screen.get_height() // 2 - total_height // 2 + 50
        center_x = self.screen.get_width() // 2

        buttons = []
        for index, item in enumerate(items):
            y = start_y + index * (button_height + gap)
            rect = pygame.Rect(0, 0, button_width, button_height)
            rect.center = (center_x, y + button_height // 2)
            buttons.append({"rect": rect, **item})

        return buttons

    def action_start_game(self):
        """“开始游戏”按钮的回调。

        点击后进入选关界面。
        """
        self.scene = "level_select"

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

    def action_next_level(self):
        """通关界面中“下一关”按钮的回调。"""
        if self.current_level < max(self.LEVELS):
            # 进入新的普通关卡时重置得分和用时，避免上一关得分带入下一关。
            self.score = 0
            self.elapsed_time = 0.0
            self.apply_level_config(self.current_level + 1)
            self.scene = "game"

    def action_back_to_level_select(self):
        """退回选关界面。"""
        self.scene = "level_select"

    def action_select_level(self, level_number):
        """选择指定关卡并开始游戏。"""
        self.endless_mode = False
        self.score = 0
        self.elapsed_time = 0.0
        self.apply_level_config(level_number)
        self.scene = "game"

    def action_start_endless(self):
        """进入无尽模式。"""
        self.endless_mode = True
        self.score = 0
        self.elapsed_time = 0.0
        self.mistakes_left = self.INITIAL_MISTAKES
        self.start_endless_level()

    def start_endless_level(self):
        """生成无尽模式新地图，地图规则与第三关相同。"""
        config = self.LEVELS[3]
        self.current_level = 3
        self.BOARD_SIZE = config["size"]
        self.CELL_SIZE = config["cell_size"]
        self.TOTAL_ARROWS = config["total_arrows"]
        self.use_snake_movement = True

        # 无尽模式每次通关都必须生成全新的随机地图，因此传入新的随机种子。
        self.arrows = self.generate_snake_level(base_seed=random.randint(1, 10**9))
        self.level_data = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
        self.remaining_arrows = len(self.arrows)
        self.snake_animation = None
        self.shake_animation = None
        self.snake_flying_animation = None
        self.heart_particles = []
        self.scene = "game"

    def reset_game(self):
        """重置当前棋盘、爱心数量和动画状态，并进入游戏场景。"""
        if self.endless_mode:
            self.score = 0
            self.elapsed_time = 0.0
            self.mistakes_left = self.INITIAL_MISTAKES
            self.start_endless_level()
        else:
            self.score = 0
            self.elapsed_time = 0.0
            self.apply_level_config(self.current_level)
            self.scene = "game"

    def build_result_buttons(self):
        """根据当前结算场景创建通关或失败界面的按钮。"""
        center_x = self.screen.get_width() // 2
        button_width = 240
        button_height = 60
        gap = 20

        if self.scene == "win":
            has_next_level = self.current_level < max(self.LEVELS)
            items = (
                {
                    "label": "下一关",
                    "action": self.action_next_level,
                    "enabled": has_next_level,
                },
                {"label": "返回选关", "action": self.action_back_to_level_select},
                {"label": "返回大厅", "action": self.action_return_lobby},
            )
        else:
            items = (
                {"label": "重新开始", "action": self.action_restart_game},
                {"label": "返回大厅", "action": self.action_return_lobby},
                {"label": "返回选关", "action": self.action_back_to_level_select},
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

    def build_level_select_buttons(self):
        """创建选关界面的三个关卡按钮。"""
        center_x = self.screen.get_width() // 2
        button_width = 320
        button_height = 64
        gap = 22

        buttons = []
        for index, (level_number, config) in enumerate(self.LEVELS.items()):
            y = 250 + index * (button_height + gap)
            rect = pygame.Rect(0, 0, button_width, button_height)
            rect.center = (center_x, y + button_height // 2)
            buttons.append(
                {
                    "rect": rect,
                    "label": f"第 {level_number} 关（{config['size']}x{config['size']}）",
                    "action": lambda level=level_number: self.action_select_level(level),
                }
            )

        # 无尽模式按钮
        y = 250 + len(self.LEVELS) * (button_height + gap)
        rect = pygame.Rect(0, 0, button_width, button_height)
        rect.center = (center_x, y + button_height // 2)
        buttons.append(
            {
                "rect": rect,
                "label": "无尽模式",
                "action": self.action_start_endless,
            }
        )

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

    def get_game_level_select_button_rect(self):
        """返回游戏界面右上角“返回选关”按钮的区域。"""
        width, height = 130, 40
        margin = 20
        rect = pygame.Rect(0, 0, width, height)
        rect.topright = (self.screen.get_width() - margin, 18)
        return rect

    def get_game_restart_button_rect(self):
        """返回游戏界面右上角“重新开始”按钮的区域。"""
        width, height = 130, 40
        gap = 10
        back_rect = self.get_game_level_select_button_rect()
        rect = pygame.Rect(0, 0, width, height)
        rect.topright = (back_rect.left - gap, 18)
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
    def draw_level_icon(surface, center, size, color):
        """绘制选关按钮前的四宫格图标。"""
        half = size // 2
        gap = max(2, size // 10)
        cell_size = (size - gap) // 2

        for row in range(2):
            for col in range(2):
                x = center[0] - half + col * (cell_size + gap)
                y = center[1] - half + row * (cell_size + gap)
                pygame.draw.rect(surface, color, (x, y, cell_size, cell_size), border_radius=2)

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
        elif button["icon"] == "level":
            self.draw_level_icon(self.screen, icon_center, icon_size, self.ICON_GEAR_COLOR)
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

    def draw_snake_board(self, skip_cells=None):
        """绘制第二、三关的可弯折多段箭头。"""
        left, top = self.get_board_top_left()
        skip_cells = skip_cells or set()

        # 绘制棋盘格背景
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                cell_x = left + col * (self.CELL_SIZE + self.CELL_GAP)
                cell_y = top + row * (self.CELL_SIZE + self.CELL_GAP)
                cell_rect = pygame.Rect(cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE)
                pygame.draw.rect(self.screen, self.BOARD_CELL_COLOR, cell_rect)
                pygame.draw.rect(self.screen, self.BOARD_GRID_COLOR, cell_rect, width=2)

        for arrow in self.arrows:
            if not arrow["cells"]:
                continue
            if any(cell in skip_cells for cell in arrow["cells"]):
                continue
            self.draw_snake_arrow(arrow, left, top)

    def draw_snake_arrow(
        self,
        arrow,
        board_left,
        board_top,
        offset=(0, 0),
        color_override=None,
    ):
        """绘制一个可弯折的蛇形箭头。"""
        # cells 必须保持有序：cells[0] 是头部，后续为身体段。
        cells = arrow["cells"]
        direction = arrow["direction"]
        color = self.ARROW_COLORS.get(direction, self.TEXT_COLOR)
        if color_override is not None:
            color = color_override
        half = self.CELL_SIZE // 3
        body_width = max(2, int(half))

        # 先按顺序取得所有格子中心，保证画出来的折线首尾相连。
        ordered_points = [
            self.get_cell_center(*cell, board_left, board_top)
            for cell in cells
        ]
        ordered_points = [
            (point[0] + offset[0], point[1] + offset[1])
            for point in ordered_points
        ]
        head_center = ordered_points[0]

        # 单格箭头直接使用第一关的“三角形 + 长方形箭身”样式。
        if len(cells) == 1:
            self.draw_arrow(
                self.screen,
                head_center,
                direction,
                color_override=color,
            )
            return

        dr, dc = self.DIRECTIONS[direction]

        # 身体折线起点不是头部中心，而是头部三角形底边，避免身体插入三角形内部。
        body_start = (
            head_center[0] - dc * half,
            head_center[1] - dr * half,
        )
        body_points = [body_start] + ordered_points[1:]

        # 按顺序连接：底边 -> 第 2 段 -> 第 3 段 -> ... -> 尾巴。
        for index in range(len(body_points) - 1):
            pygame.draw.line(
                self.screen,
                color,
                body_points[index],
                body_points[index + 1],
                body_width,
            )

        # 在身体段的连接点补圆，保证拐弯处连续、无缺口。
        for point in body_points[1:]:
            pygame.draw.circle(self.screen, color, point, max(1, body_width // 2))

        # 头部单独绘制三角形，指向当前移动方向。
        x, y = head_center
        if direction == 1:
            points = ((x, y - half), (x - half, y + half), (x + half, y + half))
        elif direction == 2:
            points = ((x, y + half), (x - half, y - half), (x + half, y - half))
        elif direction == 3:
            points = ((x - half, y), (x + half, y - half), (x + half, y + half))
        else:
            points = ((x + half, y), (x - half, y - half), (x - half, y + half))

        pygame.draw.polygon(self.screen, color, points)

    def get_active_animation_cells(self):
        """返回当前动画箭头占用的格子，用于避免重复绘制。"""
        if self.flying_animation is not None:
            return set(self.flying_animation["cells"])
        if self.shake_animation is not None:
            return set(self.shake_animation["cells"])
        if self.snake_flying_animation is not None:
            arrow_index = self.snake_flying_animation["arrow_index"]
            return set(self.arrows[arrow_index]["cells"])
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

    def get_snake_fly_offset(self):
        """计算蛇形箭头飞出动画的像素偏移量。"""
        animation = self.snake_flying_animation
        progress = self.get_animation_progress(animation, eased=True)
        direction = animation["direction"]
        cells = self.arrows[animation["arrow_index"]]["cells"]
        left, top = self.get_board_top_left()

        board_width = self.BOARD_SIZE * self.CELL_SIZE + (self.BOARD_SIZE - 1) * self.CELL_GAP
        board_height = self.BOARD_SIZE * self.CELL_SIZE + (self.BOARD_SIZE - 1) * self.CELL_GAP
        margin = self.CELL_SIZE

        # cells[-1] 是蛇形箭头的尾巴，使用它确保整条箭头都移出棋盘。
        tail_x, tail_y = self.get_cell_center(*cells[-1], left, top)

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

    def draw_snake_flying_arrow(self):
        """绘制正在飞出的蛇形箭头。"""
        animation = self.snake_flying_animation
        arrow = self.arrows[animation["arrow_index"]]
        left, top = self.get_board_top_left()
        offset = self.get_snake_fly_offset()
        self.draw_snake_arrow(arrow, left, top, offset=offset)

    def draw_shaking_arrow(self):
        """绘制被阻挡时左右晃动并变红的箭头。"""
        animation = self.shake_animation
        progress = self.get_animation_progress(animation, eased=False)

        # 左右晃动 2 次，即 sin 完成 2 个完整周期
        shake_x = math.sin(progress * 4 * math.pi) * self.SHAKE_AMPLITUDE
        left, top = self.get_board_top_left()

        if animation.get("snake"):
            arrow = {
                "cells": animation["cells"],
                "direction": animation["direction"],
            }
            self.draw_snake_arrow(
                arrow,
                left,
                top,
                offset=(shake_x, 0),
                color_override=self.BLOCKED_COLOR,
            )
        else:
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
        elif self.snake_flying_animation is not None:
            self.draw_snake_flying_arrow()
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
        hearts_y = 12 + 4 * 20
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
        x, y = 20, 12

        lines = (
            f"当前关卡：{self.current_level}",
            f"剩余箭头：{self.remaining_arrows}",
            f"得分：{self.score}",
            f"时间：{int(self.elapsed_time)}s",
        )
        for line in lines:
            text_surface = self.subtitle_font.render(line, True, self.TEXT_COLOR)
            self.screen.blit(text_surface, (x, y))
            y += 20

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
        enabled = button.get("enabled", True)
        hovered = enabled and rect.collidepoint(mouse_pos)

        if not enabled:
            background = (52, 54, 60)
            border_color = (72, 74, 82)
            text_color = (110, 112, 120)
        else:
            background = self.BUTTON_HOVER_COLOR if hovered else self.BUTTON_COLOR
            border_color = self.BUTTON_BORDER_COLOR
            text_color = self.BUTTON_TEXT_COLOR

        pygame.draw.rect(self.screen, background, rect, border_radius=14)
        pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=14)
        self.draw_text(self.screen, self.button_font, button["label"], text_color, rect.center)

    def draw_game_top_button(self, rect, label):
        """绘制游戏界面右上角的小型功能按钮。"""
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)
        background = self.BUTTON_HOVER_COLOR if hovered else self.BUTTON_COLOR

        pygame.draw.rect(self.screen, background, rect, border_radius=10)
        pygame.draw.rect(self.screen, self.BUTTON_BORDER_COLOR, rect, width=2, border_radius=10)
        self.draw_text(self.screen, self.subtitle_font, label, self.BUTTON_TEXT_COLOR, rect.center)

    def draw_result_screen(self, title, subtitle, title_color):
        """绘制通关或失败界面共用的布局。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 160)
        self.draw_text(self.screen, self.title_font, title, title_color, title_center)

        subtitle_center = (self.screen.get_width() // 2, 230)
        self.draw_text(self.screen, self.subtitle_font, subtitle, self.MUTED_COLOR, subtitle_center)

        for button in self.build_result_buttons():
            self.draw_result_button(button)

    def get_final_score(self):
        """计算与用时和剩余失误次数相关的最终得分。"""
        time_bonus = max(0, 1000 - int(self.elapsed_time) * 10)
        mistake_bonus = self.mistakes_left * 200
        return self.score + time_bonus + mistake_bonus

    def get_star_count(self):
        """星级只与剩余失误次数相关，失败时为 0 星。"""
        if self.scene == "lose":
            return 0
        return self.mistakes_left

    def draw_star_icon(self, center_x, center_y, size, color, filled):
        """绘制一个五角星图标。"""
        outer_radius = size // 2
        inner_radius = outer_radius * 0.45
        points = []

        for index in range(10):
            radius = outer_radius if index % 2 == 0 else inner_radius
            angle = math.pi / 2 + index * math.pi / 5
            points.append(
                (
                    center_x + math.cos(angle) * radius,
                    center_y - math.sin(angle) * radius,
                )
            )

        width = 0 if filled else 2
        pygame.draw.polygon(self.screen, color, points, width)

    def draw_star_rating(self, center_y):
        """绘制 0-3 颗星的星级评价。"""
        star_count = self.get_star_count()
        size = 34
        spacing = size + 12
        total_width = 3 * size + 2 * spacing
        start_x = self.screen.get_width() // 2 - total_width // 2 + size // 2

        for index in range(3):
            filled = index < star_count
            color = self.HEART_COLOR if filled else self.HEART_EMPTY_COLOR
            self.draw_star_icon(
                start_x + index * spacing,
                center_y,
                size,
                color,
                filled,
            )

    def draw_win_screen(self):
        """绘制通关界面。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 120)
        self.draw_text(self.screen, self.title_font, "通关！", (130, 235, 150), title_center)

        score_center = (self.screen.get_width() // 2, 185)
        self.draw_text(
            self.screen,
            self.setting_font,
            f"最终得分：{self.get_final_score()}",
            self.TEXT_COLOR,
            score_center,
        )

        self.draw_star_rating(245)

        for button in self.build_result_buttons():
            self.draw_result_button(button)

    def draw_lose_screen(self):
        """绘制失败界面。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 120)
        self.draw_text(self.screen, self.title_font, "失败", self.ICON_X_COLOR, title_center)

        score_center = (self.screen.get_width() // 2, 185)
        self.draw_text(
            self.screen,
            self.setting_font,
            f"最终得分：{self.score}",
            self.TEXT_COLOR,
            score_center,
        )

        self.draw_star_rating(245)

        for button in self.build_result_buttons():
            self.draw_result_button(button)

    def draw_level_select(self):
        """绘制选关界面。"""
        self.screen.fill(self.BG_COLOR)

        title_center = (self.screen.get_width() // 2, 120)
        self.draw_text(self.screen, self.title_font, "选择关卡", self.TITLE_COLOR, title_center)

        subtitle_center = (self.screen.get_width() // 2, 185)
        self.draw_text(self.screen, self.subtitle_font, "选择一个棋盘大小开始游戏", self.MUTED_COLOR, subtitle_center)

        for button in self.build_level_select_buttons():
            self.draw_result_button(button)

    def draw_game(self):
        """绘制棋盘场景，显示 HUD、棋盘和当前动画。"""
        self.screen.fill(self.BG_COLOR)
        self.draw_hud()

        board_left, board_top = self.get_board_top_left()
        center_x = self.screen.get_width() // 2

        # 根据棋盘顶部位置放置标题和提示，避免大棋盘遮挡文字
        title_center = (center_x, max(60, board_top - 100))
        self.draw_text(
            self.screen,
            self.title_font,
            f"第 {self.current_level} 关",
            self.TITLE_COLOR,
            title_center,
        )

        hint_center = (center_x, max(105, board_top - 30))
        self.draw_text(self.screen, self.subtitle_font, "按 ESC 返回主界面", self.MUTED_COLOR, hint_center)

        # 右上角功能按钮
        self.draw_game_top_button(self.get_game_restart_button_rect(), "重新开始")
        self.draw_game_top_button(self.get_game_level_select_button_rect(), "返回选关")

        # 渲染棋盘和箭头
        skip_cells = self.get_active_animation_cells()
        if self.use_snake_movement:
            self.draw_snake_board(skip_cells=skip_cells)
        else:
            self.draw_board(self.level_data, skip_cells=skip_cells)

        self.draw_active_animation()

    def draw(self):
        """根据当前场景绘制整个画面。"""
        if self.scene == "menu":
            self.draw_menu()
        elif self.scene == "settings":
            self.draw_settings()
        elif self.scene == "level_select":
            self.draw_level_select()
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
            self.score += 10
            self.play_sound(self.sound_success)

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

    def update_snake_animation(self, dt):
        """推进蛇形箭头的逐步移动动画。"""
        if self.snake_animation is None:
            return

        animation = self.snake_animation
        animation["elapsed"] += dt

        while animation["elapsed"] >= animation["step_interval"]:
            animation["elapsed"] -= animation["step_interval"]
            moved = self.step_snake_arrow(animation["arrow_index"])
            arrow_index = animation["arrow_index"]

            # 碰撞阻挡，或箭头已经飞出并被移除时，都要结束本次动画
            if not moved or not self.arrows[arrow_index]["cells"]:
                self.snake_animation = None
                break

    def update_snake_flying_animation(self, dt):
        """推进蛇形箭头的飞出动画，动画结束后再清除箭头。"""
        if self.snake_flying_animation is None:
            return

        animation = self.snake_flying_animation
        animation["elapsed"] += dt

        if animation["elapsed"] >= animation["duration"]:
            self.remove_snake_arrow(animation["arrow_index"])
            self.snake_flying_animation = None

    def update(self, dt):
        """更新动画状态。"""
        if self.scene == "game":
            self.elapsed_time += dt

        if self.use_snake_movement:
            self.update_snake_animation(dt)
            self.update_snake_flying_animation(dt)
            if self.shake_animation is not None:
                self.update_shake_animation(dt)
        else:
            if self.flying_animation is not None:
                self.update_flying_animation(dt)
            if self.shake_animation is not None:
                self.update_shake_animation(dt)
        self.update_heart_particles(dt)

        # 无尽模式通关后继续生成新地图，不重置剩余失误次数。
        if self.scene == "win" and self.endless_mode:
            if self.mistakes_left > 0:
                self.start_endless_level()
            else:
                self.scene = "lose"

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
