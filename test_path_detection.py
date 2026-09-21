"""路径检测逻辑的测试用例。

测试覆盖：
1. 棋盘边界箭头朝外时可以直接飞出。
2. 箭头在棋盘中间且前方存在其他箭头时会被阻挡。
3. 箭头在边缘且朝向边界外时可以飞出。
4. 上、下、左、右四个方向的越界处理。
"""

import os
import unittest

# 使用无窗口的 SDL 驱动，避免运行测试时弹出游戏窗口
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import main


class PathDetectionTest(unittest.TestCase):
    """测试 Game.can_arrow_fly_out 的路径检测规则。"""

    @classmethod
    def setUpClass(cls):
        cls.game = main.Game()

    def set_board(self, arrows):
        """用给定的 (row, col, direction) 列表生成测试棋盘。"""
        size = main.Game.BOARD_SIZE
        board = [[0 for _ in range(size)] for _ in range(size)]
        for row, col, direction in arrows:
            board[row][col] = direction
        self.game.level_data = board

    def test_edge_arrow_facing_outside_can_fly(self):
        """箭头位于棋盘边缘且朝向边界外：可以直接飞出。"""
        self.set_board([(0, 0, 1)])  # 左上角，方向向上
        self.assertTrue(self.game.can_arrow_fly_out(0, 0, 1))

    def test_middle_arrow_blocked_by_another_arrow(self):
        """箭头位于棋盘中间，且前方存在其他箭头：应被阻挡。"""
        self.set_board([(4, 1, 4), (4, 5, 1)])  # 中间箭头向右，右侧有箭头
        self.assertFalse(self.game.can_arrow_fly_out(4, 1, 4))

    def test_middle_arrow_without_block_can_fly(self):
        """箭头位于棋盘中间，且前方没有其他箭头：可以飞出。"""
        self.set_board([(4, 1, 4)])
        self.assertTrue(self.game.can_arrow_fly_out(4, 1, 4))

    def test_all_four_directions_can_reach_boundary(self):
        """上、下、左、右四个方向都能正确检查到边界。"""
        self.set_board(
            [
                (8, 0, 1),  # 底部，方向向上
                (0, 1, 2),  # 顶部，方向向下
                (2, 8, 3),  # 右侧，方向向左
                (5, 2, 4),  # 左侧，方向向右
            ]
        )
        self.assertTrue(self.game.can_arrow_fly_out(8, 0, 1))
        self.assertTrue(self.game.can_arrow_fly_out(0, 1, 2))
        self.assertTrue(self.game.can_arrow_fly_out(2, 8, 3))
        self.assertTrue(self.game.can_arrow_fly_out(5, 2, 4))

    def test_each_direction_can_be_blocked(self):
        """上、下、左、右四个方向遇到前方箭头时都返回被阻挡。"""
        self.set_board(
            [
                (7, 4, 1),
                (4, 4, 1),  # 上方箭头阻挡
                (1, 4, 2),
                (4, 4, 2),  # 下方箭头阻挡
                (4, 7, 3),
                (4, 4, 3),  # 左侧箭头阻挡
                (4, 1, 4),
                (4, 4, 4),  # 右侧箭头阻挡
            ]
        )
        self.assertFalse(self.game.can_arrow_fly_out(7, 4, 1))
        self.assertFalse(self.game.can_arrow_fly_out(1, 4, 2))
        self.assertFalse(self.game.can_arrow_fly_out(4, 7, 3))
        self.assertFalse(self.game.can_arrow_fly_out(4, 1, 4))


class LevelGenerationTest(unittest.TestCase):
    """测试关卡生成算法不会产生无法消除的死局。"""

    @classmethod
    def setUpClass(cls):
        cls.game = main.Game()

    def is_solvable(self, board):
        """模拟“每次消除一个当前可飞出的箭头”，判断是否能清空棋盘。"""
        board = [row[:] for row in board]

        while True:
            removed = False
            for row in range(self.game.BOARD_SIZE):
                for col in range(self.game.BOARD_SIZE):
                    direction = board[row][col]
                    if not direction:
                        continue

                    cells = self.game.collect_arrow_group(board, row, col)
                    head_row, head_col = cells[-1]
                    if not self.game.is_path_clear(board, head_row, head_col, direction):
                        continue

                    for cell_row, cell_col in cells:
                        board[cell_row][cell_col] = 0
                    removed = True
                    break

                if removed:
                    break

            if not removed:
                break

        return all(cell == 0 for row in board for cell in row)

    def test_generated_levels_are_solvable_and_have_expected_arrow_count(self):
        """多个随机种子生成的关卡都应能全部消除。"""
        for seed in (20260918, 1, 2, 3, 4, 5):
            board = self.game.generate_level(seed)
            self.assertEqual(self.game.count_arrow_groups(board), self.game.TOTAL_ARROWS)
            self.assertTrue(self.is_solvable(board), f"seed={seed} 生成的关卡无法通关")

    def test_all_three_level_configs_are_solvable(self):
        """9x9、11x11、13x13 三个关卡都应能全部消除。"""
        for level_number in (1, 2, 3):
            self.game.apply_level_config(level_number)

            for seed in (20260918, 1, 2):
                board = self.game.generate_level(seed)
                self.assertEqual(len(board), self.game.BOARD_SIZE)
                self.assertEqual(self.game.count_arrow_groups(board), self.game.TOTAL_ARROWS)
                self.assertTrue(
                    self.is_solvable(board),
                    f"level={level_number}, seed={seed} 生成的关卡无法通关",
                )

    def test_snake_levels_have_required_bend_ratios(self):
        """第二、三关的多格箭头应满足弯折比例要求，且不允许无弯折。"""
        for level_number in (2, 3):
            self.game.apply_level_config(level_number)
            arrows = self.game.arrows
            multi_arrows = [arrow for arrow in arrows if len(arrow["cells"]) > 1]

            bend_counts = []
            for arrow in multi_arrows:
                bends = 0
                previous_direction = None
                for index in range(1, len(arrow["cells"])):
                    direction = self.game.direction_between(
                        arrow["cells"][index],
                        arrow["cells"][index - 1],
                    )
                    if previous_direction is not None and direction != previous_direction:
                        bends += 1
                    previous_direction = direction
                bend_counts.append(bends)

            self.assertAlmostEqual(len(multi_arrows) / len(arrows), 0.80, delta=0.05)
            self.assertTrue(all(bends >= 1 for bends in bend_counts))
            one_bend_ratio = sum(1 for bends in bend_counts if bends == 1) / len(multi_arrows)
            multi_bend_ratio = sum(1 for bends in bend_counts if bends >= 2) / len(multi_arrows)

            if level_number == 3:
                # 第三关两弯折及以上长条占比提高到约 50%。
                self.assertAlmostEqual(one_bend_ratio, 0.50, delta=0.05)
                self.assertAlmostEqual(multi_bend_ratio, 0.50, delta=0.05)
            else:
                self.assertAlmostEqual(one_bend_ratio, 0.80, delta=0.05)
                self.assertAlmostEqual(multi_bend_ratio, 0.20, delta=0.05)

    def test_snake_levels_are_solvable(self):
        """第二、三关生成的蛇形箭头必须存在一个可全部消除的顺序。"""
        for level_number in (2, 3):
            self.game.apply_level_config(level_number)
            self.assertTrue(
                self.game.has_snake_solution(self.game.arrows, self.game.snake_grid),
                f"level={level_number} 生成的蛇形关卡无法通关",
            )


if __name__ == "__main__":
    unittest.main()
