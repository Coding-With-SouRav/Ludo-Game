import configparser
import ctypes
import sys
import tkinter as tk
from PIL import Image, ImageTk
import random
import json
import math
import time
import os
from typing import List, Dict, Tuple, Optional
  
  
# Add pygame import for sound
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not available. Sound effects will be disabled.")

if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.example.LudoGame")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
    return full_path

class LudoAI:
    COLOR_START = {
        'RED': 0,
        'GREEN': 13,
        'BLUE': 26,
        'YELLOW': 39
    }

    def __init__(self, ai_color: str, difficulty: str = "hard"):
        ai_color = ai_color.upper()

        if ai_color not in self.COLOR_START:
            raise ValueError("ai_color must be one of RED, GREEN, BLUE, YELLOW")
        self.ai_color = ai_color
        self.difficulty = difficulty if difficulty in ['easy', 'medium', 'hard', 'expert'] else 'hard'
        self.strategy_stage = 0
        self.active_coins: List[int] = []
        self.six_counter = 0
        self.consecutive_sixes = 0
        self.game_progress = 0.0
        self.opponent_progress: Dict[str, float] = {}
        self.move_history: List[Tuple[int, int]] = []
        self.last_move: Optional[Tuple[int, int]] = None
        self.difficulty_settings = {
            'easy': {
                'risk_tolerance': 0.8,
                'strategy_depth': 1,
                'aggression': 0.3,
                'prediction_accuracy': 0.6,
                'planning_horizon': 1,
                'memory_size': 5
            },
            'medium': {
                'risk_tolerance': 0.5,
                'strategy_depth': 2,
                'aggression': 0.6,
                'prediction_accuracy': 0.75,
                'planning_horizon': 2,
                'memory_size': 10
            },
            'hard': {
                'risk_tolerance': 0.2,
                'strategy_depth': 4,
                'aggression': 0.85,
                'prediction_accuracy': 0.9,
                'planning_horizon': 3,
                'memory_size': 15
            },
            'expert': {
                'risk_tolerance': 0.1,
                'strategy_depth': 6,
                'aggression': 0.95,
                'prediction_accuracy': 0.95,
                'planning_horizon': 4,
                'memory_size': 20
            }
        }
        self.early_game_threshold = 15
        self.mid_game_threshold = 40
        self.phase_weights = {
            'early': {'progress': 1.0, 'safety': 1.5, 'aggression': 0.5, 'strategy': 0.3},
            'mid': {'progress': 1.5, 'safety': 1.0, 'aggression': 1.0, 'strategy': 0.8},
            'late': {'progress': 2.0, 'safety': 0.5, 'aggression': 1.2, 'strategy': 1.0}
        }
        self.PATH_LENGTH = 57
        self.MAIN_TRACK_LENGTH = 52

    def get_dice_roll(self, game_state: Dict) -> int:
        return random.randint(1, 6)

    def choose_coin_to_move(self, game_state: Dict, dice_value: int) -> int:
        ai_positions = game_state.get(f"{self.ai_color}_positions", [-1, -1, -1, -1])
        opponent_colors = [color for color in ['RED', 'GREEN', 'BLUE', 'YELLOW'] if color != self.ai_color]
        self._update_active_coins(ai_positions)
        self._update_game_progress(game_state)
        self._update_opponent_progress(game_state)
        settings = self.difficulty_settings[self.difficulty]

        if self.difficulty == 'easy':
            return self._easy_ai_move(ai_positions, dice_value)

        if dice_value == 6 and any(pos == -1 for pos in ai_positions):
            coin_choice = self._strategic_coin_out(ai_positions, game_state, settings, self._get_game_phase(game_state))

            if coin_choice is not None and coin_choice != -1:
                return coin_choice
        possible_moves: List[Tuple[int, float]] = []
        for coin_num in range(4):
            current_pos = ai_positions[coin_num]

            if not self._is_valid_move(current_pos, dice_value, self.PATH_LENGTH):
                continue
            score = self._advanced_evaluate_move(coin_num, current_pos, dice_value, opponent_colors, game_state, settings, self._get_game_phase(game_state))
            possible_moves.append((coin_num, score))

        if not possible_moves:
            return -1
        possible_moves.sort(key=lambda x: x[1], reverse=True)

        if self.difficulty in ['hard', 'expert'] and len(possible_moves) > 1:
            best_move = self._strategic_move_selection(possible_moves, game_state, dice_value)

            if best_move != -1:
                return best_move
            return possible_moves[0][0]
        return possible_moves[0][0]

    def record_move(self, coin_moved: int, dice_value: int):
        self.last_move = (coin_moved, dice_value)

    def update_game_state(self, game_state: Dict):

        if hasattr(self, 'last_move') and self.last_move is not None:
            self.move_history.append(self.last_move)
            memory_size = self.difficulty_settings[self.difficulty]['memory_size']

            if len(self.move_history) > memory_size:
                self.move_history.pop(0)
            self.last_move = None

    def reset(self):
        self.strategy_stage = 0
        self.active_coins = []
        self.six_counter = 0
        self.consecutive_sixes = 0
        self.game_progress = 0.0
        self.opponent_progress = {}
        self.move_history = []
        self.last_move = None

    def _easy_ai_move(self, ai_positions: List[int], dice_value: int) -> int:
        best_coin = -1
        best_score = -999.0
        for coin_num, pos in enumerate(ai_positions):

            if not self._is_valid_move(pos, dice_value, self.PATH_LENGTH):
                continue
            new_pos = self._calculate_new_position(pos, dice_value)
            score = self._calculate_basic_progress_score(pos, new_pos)
            for color in [c for c in ['RED', 'GREEN', 'BLUE', 'YELLOW'] if c != self.ai_color]:
                opps = self._cached_game_state_get(color + '_positions')

                if opps and new_pos in opps and not self._is_safe_zone(new_pos):
                    score += 5.0

            if score > best_score:
                best_score = score
                best_coin = coin_num
        return best_coin

    def _cached_game_state_get(self, _key: str):
        return None

    def _advanced_strategic_move(self, ai_positions: List[int], opponent_colors: List[str], game_state: Dict, dice_value: int, settings: Dict) -> int:
        return self.choose_coin_to_move(game_state, dice_value)

    def _strategic_move_selection(self, possible_moves: List[Tuple[int, float]], game_state: Dict, dice_value: int) -> int:

        if not possible_moves:
            return -1
        best_score = possible_moves[0][1]
        top_moves = [m for m in possible_moves if m[1] >= best_score * 0.9]

        if not top_moves:
            return possible_moves[0][0]

        if len(top_moves) == 1:
            return top_moves[0][0]
        analyzed_moves: List[Tuple[int, float, float]] = []
        for coin_num, score in top_moves:
            strategic_value = self._calculate_strategic_value(coin_num, game_state, dice_value)
            analyzed_moves.append((coin_num, score, strategic_value))
        analyzed_moves.sort(key=lambda x: (x[2], x[1]), reverse=True)

        if self.difficulty == 'expert' and len(analyzed_moves) > 1:

            if random.random() < 0.2:
                return analyzed_moves[1][0]
        return analyzed_moves[0][0]

    def _calculate_strategic_value(self, coin_num: int, game_state: Dict, dice_value: int) -> float:
        strategic_value = 0.0
        ai_positions = game_state.get(f"{self.ai_color}_positions", [])
        current_pos = ai_positions[coin_num]
        new_position = self._calculate_new_position(current_pos, dice_value)

        if new_position >= self.PATH_LENGTH - 1:
            strategic_value += 5.0

        if current_pos < 51 <= new_position:
            strategic_value += 2.0

        if self._creates_blockade(coin_num, new_position, game_state):
            strategic_value += 1.5
        strategic_value += self._calculate_threat_value(new_position, game_state)
        return strategic_value

    def _creates_blockade(self, coin_num: int, new_position: int, game_state: Dict) -> bool:

        if not self._is_safe_zone(new_position):
            return False
        ai_positions = game_state.get(f"{self.ai_color}_positions", [])
        blockade_count = 0
        for i, pos in enumerate(ai_positions):

            if i != coin_num and pos != -1 and abs(pos - new_position) <= 3:
                blockade_count += 1
        return blockade_count >= 1

    def _calculate_threat_value(self, new_position: int, game_state: Dict) -> float:
        threat_value = 0.0
        for color in [c for c in ['RED', 'GREEN', 'BLUE', 'YELLOW'] if c != self.ai_color]:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos > -1 and not self._is_safe_zone(opp_pos):
                    distance = self._calculate_relative_distance(opp_pos, new_position, color)

                    if 1 <= distance <= 6:
                        threat_level = (6 - distance) / 6.0
                        opponent_prog = self.opponent_progress.get(color, 0)

                        if opponent_prog >= 45:
                            threat_level *= 2.0
                        threat_value += threat_level
        return threat_value * 0.5

    def _advanced_evaluate_move(self, coin_num: int, current_pos: int, dice_value: int, opponent_colors: List[str], game_state: Dict, settings: Dict, game_phase: str) -> float:
        score = 0.0
        new_position = self._calculate_new_position(current_pos, dice_value)
        phase_weights = self.phase_weights[game_phase]
        progress_score = self._calculate_advanced_progress_score(current_pos, new_position, game_phase)
        score += progress_score * phase_weights['progress']
        capture_score = self._evaluate_advanced_capture_opportunity(coin_num, new_position, opponent_colors, game_state, settings, game_phase)
        score += capture_score * phase_weights['aggression']
        safety_score = self._evaluate_advanced_safety(coin_num, new_position, opponent_colors, game_state, settings, game_phase)
        score += safety_score * phase_weights['safety']
        strategy_score = self._evaluate_advanced_strategic_position(new_position, game_state, settings, game_phase)
        score += strategy_score * phase_weights['strategy']
        disruption_score = self._evaluate_opponent_disruption(new_position, opponent_colors, game_state, settings)
        score += disruption_score

        if new_position >= 51:
            home_priority = (new_position - 50) * 0.5
            score += home_priority

        if new_position >= self.PATH_LENGTH - 1:
            score += 3.0
        risk_multiplier = self._calculate_risk_multiplier(game_phase, settings, game_state)
        score *= risk_multiplier

        if self.difficulty == 'expert':
            repetition_penalty = self._calculate_repetition_penalty(coin_num, current_pos)
            score -= repetition_penalty
        return score

    def _calculate_risk_multiplier(self, game_phase: str, settings: Dict, game_state: Dict) -> float:
        base_multiplier = 1.0

        if self._is_leading(game_state):

            if game_phase == 'late':
                base_multiplier *= (1 - settings['risk_tolerance'] * 0.7)
            else:
                base_multiplier *= (1 - settings['risk_tolerance'] * 0.3)
        else:

            if game_phase == 'late':
                base_multiplier *= (1 + settings['risk_tolerance'] * 0.5)
        return base_multiplier

    def _is_leading(self, game_state: Dict) -> bool:
        ai_prog = self.game_progress
        max_opp = max(self.opponent_progress.values()) if self.opponent_progress else 0
        return ai_prog > max_opp

    def _calculate_repetition_penalty(self, coin_num: int, current_pos: int) -> float:

        if len(self.move_history) < 3:
            return 0.0
        recent_moves = self.move_history[-3:]
        same_coin_count = sum(1 for move in recent_moves if move[0] == coin_num)
        return same_coin_count * 0.3

    def _evaluate_advanced_capture_opportunity(self, coin_num: int, new_position: int, opponent_colors: List[str], game_state: Dict, settings: Dict, game_phase: str) -> float:

        if self._is_safe_zone(new_position):
            return 0.0
        capture_value = 0.0
        for color in opponent_colors:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos == new_position and not self._is_safe_zone(opp_pos):
                    base_val = 2.5 * settings['aggression']
                    opp_prog = self.opponent_progress.get(color, 0)

                    if opp_prog >= 45:
                        base_val *= 2.0
                    elif opp_prog >= 30:
                        base_val *= 1.5
                    capture_value += base_val
                    break
        return capture_value

    def _evaluate_advanced_safety(self, coin_num: int, new_position: int, opponent_colors: List[str], game_state: Dict, settings: Dict, game_phase: str) -> float:

        if self._is_safe_zone(new_position):
            return 2.0
        immediate_danger = self._evaluate_immediate_threats(new_position, opponent_colors, game_state)
        traffic_danger = self._evaluate_traffic_danger(new_position, game_state)
        future_threats = self._evaluate_future_threats(new_position, opponent_colors, game_state)
        total_danger = immediate_danger + traffic_danger * 0.3 + future_threats * 0.2
        return -total_danger * (1 - settings['risk_tolerance'])

    def _evaluate_immediate_threats(self, new_position: int, opponent_colors: List[str], game_state: Dict) -> float:
        immediate_danger = 0.0
        prediction_range = 6
        for color in opponent_colors:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos > -1 and not self._is_safe_zone(opp_pos):
                    distance = self._calculate_relative_distance(opp_pos, new_position, color)

                    if 1 <= distance <= prediction_range:
                        danger_level = (prediction_range - distance + 1) / prediction_range
                        opp_prog = self.opponent_progress.get(color, 0)

                        if opp_prog >= 40:
                            danger_level *= 1.5
                        immediate_danger += danger_level
        return immediate_danger

    def _evaluate_future_threats(self, new_position: int, opponent_colors: List[str], game_state: Dict) -> float:
        future_threats = 0.0
        for color in opponent_colors:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos > -1 and not self._is_safe_zone(opp_pos):
                    for dice1 in range(1, 7):
                        intermediate_pos = opp_pos + dice1

                        if intermediate_pos <= 56:
                            for dice2 in range(1, 7):
                                future_pos = intermediate_pos + dice2

                                if future_pos == new_position:
                                    future_threats += 0.1
                                    break
        return future_threats

    def _evaluate_advanced_strategic_position(self, new_position: int, game_state: Dict, settings: Dict, game_phase: str) -> float:
        score = 0.0
        blocking_bonus = self._evaluate_blocking_position(new_position, game_state)
        score += blocking_bonus * settings['aggression']

        if game_phase == 'early':
            opponent_start_positions = self._get_opponent_start_positions()
            for start_pos in opponent_start_positions:

                if abs(new_position - start_pos) <= 3:
                    score += 0.6 * settings['aggression']
        future_capture_potential = self._evaluate_future_capture_potential(new_position, game_state)
        score += future_capture_potential * 0.5
        choke_points = [13, 26, 39, 8, 21, 34, 47]

        if new_position in choke_points:
            score += 0.8 * settings['aggression']
        return score

    def _evaluate_opponent_disruption(self, new_position: int, opponent_colors: List[str], game_state: Dict, settings: Dict) -> float:
        disruption = 0.0
        for color in opponent_colors:
            opponent_positions = game_state.get(f"{color}_positions", [])
            active_opponents = [p for p in opponent_positions if p > -1]

            if not active_opponents:
                continue
            leading_opponent = max(active_opponents)

            if new_position > leading_opponent:
                disruption += 0.3 * settings['aggression']

            if 45 <= new_position <= 50 and new_position > leading_opponent:
                disruption += 0.5 * settings['aggression']
            threatened_count = 0
            for opp_pos in active_opponents:

                if 1 <= abs(new_position - opp_pos) <= 6:
                    threatened_count += 1

            if threatened_count >= 2:
                disruption += 0.4 * settings['aggression']
        return disruption

    def _evaluate_blocking_position(self, position: int, game_state: Dict) -> float:

        if position in [8, 13, 21, 26, 34, 39, 47]:
            return 1.0
        block_count = 0
        for color in [c for c in ['RED', 'GREEN', 'BLUE', 'YELLOW'] if c != self.ai_color]:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos > -1 and abs(opp_pos - position) <= 3:
                    block_count += 1
        return min(block_count * 0.2, 1.0)

    def _evaluate_future_capture_potential(self, position: int, game_state: Dict) -> float:
        potential = 0.0
        for color in [c for c in ['RED', 'GREEN', 'BLUE', 'YELLOW'] if c != self.ai_color]:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos > -1 and not self._is_safe_zone(opp_pos):
                    for dice in range(1, 7):
                        future_opp_pos = opp_pos + dice

                        if future_opp_pos == position and not self._is_safe_zone(position):

                            if opp_pos >= 45:
                                potential += 0.2
                            else:
                                potential += 0.1
                            break
        return potential

    def _evaluate_traffic_danger(self, position: int, game_state: Dict) -> float:
        high_traffic_positions = [0, 1, 2, 3, 4, 5, 6, 13, 14, 15, 26, 27, 28, 39, 40, 41]

        if position in high_traffic_positions:
            return 0.8
        medium_traffic_positions = [7, 12, 16, 20, 25, 29, 33, 38, 42, 46]

        if position in medium_traffic_positions:
            return 0.4
        return 0.0

    def _calculate_advanced_progress_score(self, current_pos: int, new_position: int, game_phase: str) -> float:

        if current_pos == -1:
            return 1.5
        base_progress = (new_position - current_pos) / float(self.PATH_LENGTH - 1)

        if current_pos < 51 <= new_position:
            base_progress *= 2.5

        if game_phase == 'late' and new_position >= 45:
            base_progress *= 2.0

        if game_phase == 'early' and new_position > 20:
            base_progress *= 0.8
        return base_progress

    def _calculate_relative_distance(self, opp_pos: int, my_pos: int, opp_color: str) -> int:

        if opp_pos >= self.MAIN_TRACK_LENGTH or my_pos >= self.MAIN_TRACK_LENGTH:
            return abs(opp_pos - my_pos)

        if my_pos >= opp_pos:
            return my_pos - opp_pos
        return (self.MAIN_TRACK_LENGTH - opp_pos) + my_pos

    def _get_game_phase(self, game_state: Dict) -> str:
        ai_positions = game_state.get(f"{self.ai_color}_positions", [])
        active_positions = [pos for pos in ai_positions if pos != -1]

        if not active_positions:
            return 'early'
        avg_progress = sum(active_positions) / len(active_positions)

        if avg_progress < self.early_game_threshold:
            return 'early'
        elif avg_progress < self.mid_game_threshold:
            return 'mid'
        else:
            return 'late'

    def _update_game_progress(self, game_state: Dict):
        ai_positions = game_state.get(f"{self.ai_color}_positions", [])
        active_positions = [pos for pos in ai_positions if pos != -1]
        self.game_progress = sum(active_positions) / len(active_positions) if active_positions else 0.0

    def _update_opponent_progress(self, game_state: Dict):
        for color in ['RED', 'GREEN', 'BLUE', 'YELLOW']:

            if color == self.ai_color:
                continue
            positions = game_state.get(f"{color}_positions", [])
            active_positions = [p for p in positions if p != -1]
            self.opponent_progress[color] = sum(active_positions) / len(active_positions) if active_positions else 0.0

    def _strategic_coin_out(self, ai_positions: List[int], game_state: Dict, settings: Dict, game_phase: str) -> int:
        available_coins = [i for i, pos in enumerate(ai_positions) if pos == -1]

        if not available_coins:
            return -1

        if self.difficulty in ['hard', 'expert']:
            coin_scores: List[Tuple[int, float]] = []
            for coin in available_coins:
                score = 0.0
                score -= self._get_coin_recent_use_penalty(coin)

                if self._is_start_position_safe(coin, game_state, settings):
                    score += 1.0
                else:

                    if random.random() < settings['aggression']:
                        score += 0.5

                if game_phase == 'late':
                    coins_in_play = sum(1 for pos in ai_positions if pos != -1)

                    if coins_in_play >= 2:
                        score -= 0.5
                coin_scores.append((coin, score))
            coin_scores.sort(key=lambda x: x[1], reverse=True)
            return coin_scores[0][0]
        return random.choice(available_coins)

    def _get_coin_recent_use_penalty(self, coin_num: int) -> float:

        if len(self.move_history) < 2:
            return 0.0
        recent_moves = self.move_history[-2:]
        same_coin_count = sum(1 for move in recent_moves if move[0] == coin_num)
        return same_coin_count * 0.5

    def _update_active_coins(self, ai_positions: List[int]):
        self.active_coins = [i for i, pos in enumerate(ai_positions) if pos != -1]

    def _count_coins_at_home(self, game_state: Dict) -> int:
        ai_positions = game_state.get(f"{self.ai_color}_positions", [])
        return sum(1 for pos in ai_positions if pos == -1)

    def _is_valid_move(self, current_pos: int, dice_value: int, path_length: int) -> bool:

        if current_pos == -1:
            return dice_value == 6
        return current_pos + dice_value <= path_length - 1

    def _calculate_new_position(self, current_pos: int, dice_value: int) -> int:

        if current_pos == -1:
            return self.COLOR_START[self.ai_color]
        return current_pos + dice_value

    def _is_safe_zone(self, position: int) -> bool:
        safe_positions = [0, 8, 13, 21, 26, 34, 39, 47]
        return position in safe_positions

    def _is_start_position_safe(self, coin_num: int, game_state: Dict, settings: Dict) -> bool:
        start_pos = self.COLOR_START[self.ai_color]
        for color in [c for c in ['RED', 'GREEN', 'BLUE', 'YELLOW'] if c != self.ai_color]:
            opponent_positions = game_state.get(f"{color}_positions", [])
            for opp_pos in opponent_positions:

                if opp_pos > -1 and self._calculate_relative_distance(opp_pos, start_pos, color) <= 6:
                    return False
        return True

    def _get_move_path(self) -> List[int]:
        return list(range(self.PATH_LENGTH))

    def _get_opponent_start_positions(self) -> List[int]:
        return [self.COLOR_START[c] for c in ['RED', 'GREEN', 'BLUE', 'YELLOW']]


class LudoGame:
    def __init__(self, root):
        self.root = root
        self.WIDTH, self.HEIGHT = 600, 620
        self.BOARD_TOP_OFFSET = 20
        self.root.title("Ludo Game")
        self.root.resizable(False, False)
        self.root.config(bg="black")
        self.game_mode = "friends"
        self.ai = None
        self.data_dir = os.path.join(os.path.expanduser("~"), ".LudoGame")
        os.makedirs(self.data_dir, exist_ok=True)

        if sys.platform == "win32":
            try:
                ctypes.windll.kernel32.SetFileAttributesW(self.data_dir, 2)
            except:
                pass
        
        self.config_file = os.path.join(self.data_dir, "config.ini")
        self.SAVE_FILE = os.path.join(self.data_dir, "ludo_save.json")
        # self.SAVE_FILE =  "ludo_save.json"
        self.canvas = tk.Canvas(root, width=self.WIDTH, height=self.HEIGHT, highlightthickness=0)
        self.canvas.pack()
        
        # Initialize pygame mixer for sound if available
        self.sound_enabled = PYGAME_AVAILABLE
        if self.sound_enabled:
            try:
                pygame.mixer.init()
                # Load dice rolling sound
                rolling_sound_path = resource_path("Images/rolling_dice.wav")
                self.rolling_sound = pygame.mixer.Sound(rolling_sound_path)
                player_move_sound_path = resource_path("Images/player_moves.mp3")
                self.player_move_sound = pygame.mixer.Sound(player_move_sound_path)
                success_sound_path = resource_path("Images/success.wav")
                self.success_sound = pygame.mixer.Sound(success_sound_path)
                cut_sound_path = resource_path("Images/cut_player.wav")
                self.cut_sound = pygame.mixer.Sound(cut_sound_path)
                winning_sound_path = resource_path("Images/winning_sound.mp3")
                self.winning_sound = pygame.mixer.Sound(winning_sound_path)
                self.sound_loaded = True
            except Exception as e:
                print(f"Could not load sound: {e}")
                self.sound_enabled = False
                self.sound_loaded = False
        else:
            self.sound_loaded = False
        
        self.COLORS = [
            '#ff2e63', '#08d9d6', '#f9ed69', '#f08a5d',
            '#b83b5e', '#6a2c70', '#ffd460', '#ff6363',
            '#5ffbf1', '#9c1de7', '#fa7d09', '#00bbf9',
            '#ff9f1c', '#ffcbf2', '#d0ff00', '#00ff99'
        ]

        # Add these instance variables in LudoGame.__init__ method after other initializations
        self.stars = []
        self.star_burst_running = False
        self.winner = None

        self.BG_IMG = self.pil_img("Images/bg_image.png", (self.WIDTH, self.HEIGHT))
        self.LUDO_TXT_IMG = self.pil_img("Images/ludo_lover.png", (300, 300))
        self.SELECT_GAME_MODE_IMG = self.pil_img("Images/select_game_mode_text.png", (380, 380))
        self.MULTIPLAYER_IMG = self.pil_img("Images/select_multiplayer_text.png", (380, 380))
        self.CONTINUE_IMG = self.pil_img("Images/continue_img.png", (140, 30))
        self.NEW_GAME_IMG = self.pil_img("Images/new_game_img.png", (140, 30))
        self.EXIT_IMG = self.pil_img("Images/exit_img.png", (140, 40))
        self.PLAY_WITH_COMPUTER_IMG = self.pil_img("Images/play_with_computer.png", (130, 40))
        self.PLAY_WITH_FRIENDS_IMG = self.pil_img("Images/play_with_friends.png", (130, 50))
        self.BACK_TO_MAIN_MENU_IMG = self.pil_img("Images/back_to_main_menu.png", (130, 40))
        self.TWO_PLAYERS_IMG = self.pil_img("Images/2_players.png", (130, 30))
        self.THREE_PLAYERS_IMG = self.pil_img("Images/3_players.png", (130, 30))
        self.FOUR_PLAYERS_IMG = self.pil_img("Images/4_players.png", (130, 30))
        self.BACK_IMG = self.pil_img("Images/back.png", (130, 30))
        self.PLAY_ICON = self.pil_img("Images/play_icon.png", (50, 50))
        self.PAUSE_ICON = self.pil_img("Images/pause_icon.png", (25, 25))
        self.BOARD_IMG = self.pil_img("Images/board.png", (self.WIDTH, 600))
        ICON_IMG = self.pil_img("Images/icon.png", (32, 32))
        self.root.iconphoto(False, ICON_IMG)
        self.dice_images = [self.pil_img(f"Images/piece_{i}.png", (50, 50)) for i in range(1, 7)]
        self.rolling_images = [self.pil_img(f"Images/dice_rotating_{i}.png", (70, 70)) for i in range(1, 11)]
        self.coin_images = {
            "RED": self.pil_img("Images/red_player.png", (65, 65)),
            "GREEN": self.pil_img("Images/green_player.png", (65, 65)),
            "BLUE": self.pil_img("Images/blue_player.png", (65, 65)),
            "YELLOW": self.pil_img("Images/yellow_player.png", (65, 65))
        }
        
        self.dice_value = 1
        self.players = ["RED", "BLUE", "YELLOW", "GREEN"]
        self.turn = 0
        self.player_positions = {
            "RED": [(80,103), (157,103), (80,180), (157,180)],
            "GREEN": [(443,103), (520,103), (443,180), (520,180)],
            "BLUE": [(80,463), (157,463), (80,540), (157,540)],
            "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
        }
        self.active_coins = {p: [False]*4 for p in self.players}
        self.coin_steps = {p: [0]*4 for p in self.players}
        self.completed_coins = {p: [False]*4 for p in self.players}
        self.move_paths = self.define_move_paths()
        self.DICE_SIZE = 50
        self.DICE_POS = (self.WIDTH//2 - self.DICE_SIZE//2, 20 + (600//2 - self.DICE_SIZE//2))
        self.is_rolling = False
        self.can_roll = True
        self.auto_roll_delay = 500
        self._canvas_ids = {}
        self._image_refs = {}
        self.glow_angle = 0
        self.glow_animating = False
        self.game_paused = False
        self.glow_ids = []
        
        self.draw_background()
        self.control_menu()
        self.canvas.bind("<Button-1>", self.on_click)
        self.load_window_geometry()
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def play_rolling_sound(self):
        """Play the dice rolling sound"""
        if self.sound_enabled and self.sound_loaded:
            try:
                self.rolling_sound.play(loops=-1)  # Loop the sound
            except Exception as e:
                print(f"Error playing sound: {e}")

    def stop_rolling_sound(self):
        """Stop the dice rolling sound"""
        if self.sound_enabled and self.sound_loaded:
            try:
                self.rolling_sound.stop()
            except Exception as e:
                print(f"Error stopping sound: {e}")
                
    def draw_background(self):
        self.canvas.delete("background")
        self.canvas.create_image(0, 0, anchor="nw", image=self.BG_IMG, tags="background")
        self.canvas.tag_lower("background")

    def control_menu(self):
        # Stop any playing sounds first
        if hasattr(self, 'star_burst_running') and self.star_burst_running:
            self.stop_star_burst_animation()
        if hasattr(self, 'stop_rolling_sound'):
            self.stop_rolling_sound()
        
        # Reset all game state variables
        self.dice_value = random.randint(1, 6)
        self.turn = 0
        self.active_coins = {p: [False]*4 for p in self.players}
        self.coin_steps = {p: [0]*4 for p in self.players}
        self.completed_coins = {p: [False]*4 for p in self.players}
        self.player_positions = {
            "RED": [(80,103), (157,103), (80,180), (157,180)],
            "GREEN": [(443,103), (520,103), (443,180), (520,180)],
            "BLUE": [(80,463), (157,463), (80,540), (157,540)],
            "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
        }
        self.can_roll = True
        self.is_rolling = False
        self.game_paused = False
        self.glow_animating = False
        
        # Reset AI if it exists
        if hasattr(self, 'ai'):
            self.ai = None
        
        # Clear any existing movable coins
        if hasattr(self, "movable_coins"):
            self.movable_coins = []
        
        # Clear the canvas
        self.canvas.delete("all")
        for widget in self.canvas.winfo_children():
            widget.destroy()
        
        self.draw_background()
        self.canvas.delete("title")
        self.canvas.delete("game_mode_title")
        self.canvas.delete("multiplayer_title")
        self.canvas.create_image(self.WIDTH//2, (self.HEIGHT//2)-200, anchor="center", image=self.LUDO_TXT_IMG, tags="title")
        
        button_style = {
            "font": ("Arial", 12, "bold"),
            "bd": 0,
            "relief": "flat",
            "cursor": "hand2",
            "activeforeground": "black",
            "highlightthickness": 0,
        }
        
        save_exists = os.path.exists(self.SAVE_FILE)
        self.continue_playing_btn = tk.Button(
            self.canvas,
            image=self.CONTINUE_IMG,
            bg="#15fa4a" if save_exists else "#FBFBFB",
            fg="black",
            activebackground="#5ef481" if save_exists else "#FFFFFF",
            command=self.continue_game if save_exists else None,
            state=tk.NORMAL if save_exists else tk.DISABLED,
            **button_style
        )
        self.continue_playing_btn.place(relx=0.5, rely=0.4, anchor="center")
        
        self.new_game_btn = tk.Button(
            self.canvas,
            image=self.NEW_GAME_IMG,
            bg="#007bff",
            fg="white",
            activebackground="#339aff",
            command=self.start_new_game,
            **button_style
        )
        self.new_game_btn.place(relx=0.5, rely=0.5, anchor="center")
        
        self.exit_btn = tk.Button(
            self.canvas,
            image=self.EXIT_IMG,
            bg="#ff0909",
            fg="white",
            activebackground="#f55a6b",
            command=self.on_window_close,
            **button_style
        )
        self.exit_btn.place(relx=0.5, rely=0.6, anchor="center")

    def continue_game(self):

        if self.load_game_state():
            self.start_loaded_game()
        else:
            self.start_new_game()

    def start_loaded_game(self):
        for widget in self.canvas.winfo_children():
            widget.destroy()
        self.canvas.delete("all")
        self.redraw_all()

        if hasattr(self, 'game_paused'):
            self.game_paused = False

        if self.is_rolling:
            self.is_rolling = False
            self.can_roll = True
            self.draw_dice_face()

        if hasattr(self, "movable_coins") and self.movable_coins:
            self.draw_glow_for_movable_coins()
        else:
            current_player = self.players[self.turn]

            if self.game_mode != "computer" or current_player != "RED":
                self.can_roll = True
        self.canvas.bind("<Button-1>", self.on_click)

        if self.can_roll and not self.is_rolling:
            self.root.after(1000, self.start_auto_roll)

    def start_new_game(self):
        self.dice_value = 1
        self.turn = 0
        self.active_coins = {p: [False]*4 for p in self.players}
        self.coin_steps = {p: [0]*4 for p in self.players}
        self.completed_coins = {p: [False]*4 for p in self.players}
        self.player_positions = {
            "RED": [(80,103), (157,103), (80,180), (157,180)],
            "GREEN": [(443,103), (520,103), (443,180), (520,180)],
            "BLUE": [(80,463), (157,463), (80,540), (157,540)],
            "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
        }
        for widget in self.canvas.winfo_children():
            widget.destroy()
        self.canvas.delete("title")
        self.canvas.delete("multiplayer_title")
        self.canvas.delete("game_mode_title")
        self.canvas.create_image(self.WIDTH//2, (self.HEIGHT//2)-200, anchor="center", image=self.SELECT_GAME_MODE_IMG, tags="game_mode_title")
        button_style = {
            "font": ("Arial", 12, "bold"),
            "bd": 0,
            "relief": "flat",
            "highlightthickness": 0,
            "cursor": "hand2",
            "activeforeground": "black",
        }
        self.play_with_computer_btn = tk.Button(
            self.canvas,
            image=self.PLAY_WITH_COMPUTER_IMG,
            bg="#21fa04",
            fg="black",
            activebackground="#79f874",
            command=lambda: self.start_computer_game(),
            **button_style
        )
        self.play_with_computer_btn.place(relx=0.5, rely=0.4, anchor="center")
        self.play_with_friends_btn = tk.Button(
            self.canvas,
            image=self.PLAY_WITH_FRIENDS_IMG,
            bg="#305cfc",
            fg="white",
            activebackground="#4c80ff",
            command=self.play_with_friends,
            **button_style
        )
        self.play_with_friends_btn.place(relx=0.5, rely=0.5, anchor="center")
        self.back_btn = tk.Button(
            self.canvas,
            image=self.BACK_TO_MAIN_MENU_IMG,
            bg="#ff0000",
            fg="white",
            activebackground="#ff4366",
            command=self.control_menu,
            **button_style
        )
        self.back_btn.place(relx=0.5, rely=0.6, anchor="center")

    def start_computer_game(self):
        self.game_mode = "computer"
        self.ai = LudoAI(ai_color="RED", difficulty="expert")
        self.start_2_player_game()

    def play_with_friends(self):
        for widget in self.canvas.winfo_children():
            widget.destroy()
        self.canvas.delete("title")
        self.canvas.delete("multiplayer_title")
        self.canvas.delete("game_mode_title")
        self.canvas.create_image(self.WIDTH//2, (self.HEIGHT//2)-200, anchor="center", image=self.MULTIPLAYER_IMG, tags="multiplayer_title")
        friens2_btn = tk.Button(
            self.canvas,
            image=self.TWO_PLAYERS_IMG,
            bg="#21fa04",
            fg="black",
            activebackground="#79f874",
            font=("Arial", 12, "bold"),
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
            activeforeground="black",
            command=lambda: self.start_friends_game(2),
        )
        friens2_btn.place(relx=0.5, rely=0.4, anchor="center")
        friends3_btn = tk.Button(
            self.canvas,
            image=self.THREE_PLAYERS_IMG,
            bg="#21fa04",
            fg="black",
            activebackground="#79f874",
            font=("Arial", 12, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            activeforeground="black",
            highlightthickness=0,
            command=lambda: self.start_friends_game(3),
        )
        friends3_btn.place(relx=0.5, rely=0.5, anchor="center")
        friends4_btn = tk.Button(
            self.canvas,
            image=self.FOUR_PLAYERS_IMG,
            bg="#21fa04",
            fg="black",
            activebackground="#79f874",
            font=("Arial", 12, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            activeforeground="black",
            highlightthickness=0,
            command=lambda: self.start_friends_game(4),
        )
        friends4_btn.place(relx=0.5, rely=0.6, anchor="center")
        back_btn = tk.Button(
            self.canvas,
            image=self.BACK_IMG,
            bg="#ff0000",
            fg="white",
            activebackground="#ff4366",
            font=("Arial", 12, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            activeforeground="black",
            highlightthickness=0,
            command=self.start_new_game,
        )
        back_btn.place(relx=0.5, rely=0.7, anchor="center")

    def start_friends_game(self, num_players):
        self.game_mode = "friends"
        for widget in self.canvas.winfo_children():
            widget.destroy()
        self.canvas.delete("all")

        if num_players == 2:
            self.players = ["RED", "YELLOW"]
            self.player_positions = {
                "RED": [(80,103), (157,103), (80,180), (157,180)],
                "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
            }
        elif num_players == 3:
            self.players = ["RED", "BLUE", "YELLOW"]
            self.player_positions = {
                "RED": [(80,103), (157,103), (80,180), (157,180)],
                "BLUE": [(80,463), (157,463), (80,540), (157,540)],
                "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
            }
        else:
            self.players = ["RED", "BLUE", "YELLOW", "GREEN"]
            self.player_positions = {
                "RED": [(80,103), (157,103), (80,180), (157,180)],
                "GREEN": [(443,103), (520,103), (443,180), (520,180)],
                "BLUE": [(80,463), (157,463), (80,540), (157,540)],
                "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
            }
        self.active_coins = {p: [False]*4 for p in self.players}
        self.coin_steps = {p: [0]*4 for p in self.players}
        self.completed_coins = {p: [False]*4 for p in self.players}
        self.turn = 0
        self.redraw_all()
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.after(1000, self.start_auto_roll)

    def start_2_player_game(self):
        for widget in self.canvas.winfo_children():
            widget.destroy()
        self.canvas.delete("all")
        self.players = ["RED", "YELLOW"]
        self.player_positions = {
            "RED": [(80,103), (157,103), (80,180), (157,180)],
            "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
        }
        self.active_coins = {p: [False]*4 for p in self.players}
        self.coin_steps = {p: [0]*4 for p in self.players}
        self.completed_coins = {p: [False]*4 for p in self.players}
        self.redraw_all()
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.after(1000, self.start_auto_roll)

    def start_auto_roll(self):

        if not self.is_rolling and self.can_roll:
            self.roll_animation()

    def computer_turn(self):

        if hasattr(self, 'game_paused') and self.game_paused:
            return

        if self.game_mode != "computer" or self.players[self.turn] != "RED":
            return

        if self.is_rolling or not self.can_roll:
            return

        if not self.is_rolling and self.can_roll:
            self.roll_animation()

    def get_game_state(self):
        game_state = {
            "RED_positions": self.coin_steps["RED"],
            "GREEN_positions": self.coin_steps["GREEN"] if "GREEN" in self.players else [-1, -1, -1, -1],
            "BLUE_positions": self.coin_steps["BLUE"] if "BLUE" in self.players else [-1, -1, -1, -1],
            "YELLOW_positions": self.coin_steps["YELLOW"],
            "active_coins": self.active_coins
        }
        return game_state

    def save_game_state(self):
        game_state = {
            "dice_value": self.dice_value,
            "turn": self.turn,
            "players": self.players,
            "player_positions": self.player_positions,
            "active_coins": self.active_coins,
            "coin_steps": self.coin_steps,
            "completed_coins": self.completed_coins,
            "can_roll": self.can_roll,
            "is_rolling": self.is_rolling,
            "movable_coins": getattr(self, "movable_coins", []),
            "game_mode": self.game_mode
        }

        try:

            with open(self.SAVE_FILE, 'w') as f:
                json.dump(game_state, f, indent=2)
            return True

        except Exception as e:
            return False

    def load_game_state(self):

        try:

            with open(self.SAVE_FILE, 'r') as f:
                game_state = json.load(f)
            self.dice_value = game_state["dice_value"]
            self.turn = game_state["turn"]
            self.players = game_state["players"]
            self.player_positions = game_state["player_positions"]
            self.active_coins = game_state["active_coins"]
            self.coin_steps = game_state["coin_steps"]
            self.completed_coins = game_state.get("completed_coins", {p: [False]*4 for p in self.players})
            self.can_roll = game_state["can_roll"]
            self.is_rolling = game_state["is_rolling"]
            self.movable_coins = game_state.get("movable_coins", [])
            self.game_mode = game_state.get("game_mode", "friends")

            if self.dice_value < 1 or self.dice_value > 6:
                self.dice_value = 1

            if self.game_mode == "computer":
                self.ai = LudoAI(ai_color="RED", difficulty="expert")
            for player in self.player_positions:
                self.player_positions[player] = [tuple(pos) for pos in self.player_positions[player]]
            return True

        except Exception as e:
            return False

    def load_window_geometry(self):

        if os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)

            if "Geometry" in config:
                geometry = config["Geometry"].get("size", "")
                state = config["Geometry"].get("state", "normal")

                if geometry:
                    self.root.geometry(geometry)
                    self.root.update_idletasks()
                    self.root.update()

                if state == "zoomed":
                    self.root.state("zoomed")
                elif state == "iconic":
                    self.root.iconify()

    def save_window_geometry(self):
        config = configparser.ConfigParser()
        config["Geometry"] = {
            "size": self.root.geometry(),
            "state": self.root.state()
        }

        with open(self.config_file, "w") as f:
            config.write(f)

    def on_window_close(self):
        # Stop any playing sounds before closing
        if hasattr(self, 'stop_rolling_sound'):
            self.stop_rolling_sound()
        
        self.save_game_state()
        self.save_window_geometry()
        self.root.destroy()

    def pil_img(self, path, size=None):
        im = Image.open(resource_path(path)).convert("RGBA")

        if size:
            im = im.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(im)

    def define_move_paths(self):
        mp = {}
        mp["RED"] = [
            (60,280),(100,280),(140,280),(180,280),(220,280),(260,240),(260,200),(260,160),
            (260,120),(260,80),(260,40),(300,40),(340,40),(340,80),(340,120),(340,160),
            (340,200),(340,240),(380,280),(420,280),(460,280),(500,280),(540,280),(580,280),
            (580,320),(580,360),(540,360),(500,360),(460,360),(420,360),(380,360),(340,400),
            (340,440),(340,480),(340,520),(340,560),(340,600),(300,600),(260,600),(260,560),
            (260,520),(260,480),(260,440),(260,400),(220,360),(180,360),(140,360),(100,360),
            (60,360),(20,360),(20,320),(60,320),(100,320),(140,320),(180,320),(220,320),(260,320),
        ]
        mp["BLUE"] = [
            (260,560),(260,520),(260,480),(260,440),(260,400),(220,360),(180,360),(140,360),
            (100,360),(60,360),(20,360),(20,320),(20,280),(60,280),(100,280),(140,280),
            (180,280),(220,280),(260,240),(260,200),(260,160),(260,120),(260,80),(260,40),
            (300,40),(340,40),(340,80),(340,120),(340,160),(340,200),(340,240),(380,280),
            (420,280),(460,280),(500,280),(540,280),(580,280),(580,320),(580,360),(540,360),
            (500,360),(460,360),(420,360),(380,360),(340,400),(340,440),(340,480),(340,520),
            (340,560),(340,600),(300,600),(300,560),(300,520),(300,480),(300,440),(300,400),(300,360),
        ]
        mp["YELLOW"] = [
            (540,360),(500,360),(460,360),(420,360),(380,360),(340,400),(340,440),(340,480),
            (340,520),(340,560),(340,600),(300,600),(260,600),(260,560),(260,520),(260,480),
            (260,440),(260,400),(220,360),(180,360),(140,360),(100,360),(60,360),(20,360),
            (20,320),(20,280),(60,280),(100,280),(140,280),(180,280),(220,280),(260,240),
            (260,200),(260,160),(260,120),(260,80),(260,40),(300,40),(340,40),(340,80),
            (340,120),(340,160),(340,200),(340,240),(380,280),(420,280),(460,280),(500,280),
            (540,280),(580,280),(580,320),(540,320),(500,320),(460,320),(420,320),(380,320),(340,320),
        ]
        mp["GREEN"] = [
            (340,80),(340,120),(340,160),(340,200),(340,240),(380,280),(420,280),(460,280),
            (500,280),(540,280),(580,280),(580,320),(580,360),(540,360),(500,360),(460,360),
            (420,360),(380,360),(340,400),(340,440),(340,480),(340,520),(340,560),(340,600),
            (300,600),(260,600),(260,560),(260,520),(260,480),(260,440),(260,400),(220,360),
            (180,360),(140,360),(100,360),(60,360),(20,360),(20,320),(20,280),(60,280),
            (100,280),(140,280),(180,280),(220,280),(260,240),(260,200),(260,160),(260,120),
            (260,80),(260,40),(300,40),(300,80),(300,120),(300,160),(300,200),(300,240),(300,280),
        ]
        return mp

    def restrict_cut_player_path(self):
        self.path = [(60,280),(260,120),(340,80),(500,280),(540,360),
    (340,520),
    (260,560),
    (100,360),
    (60,320),
    (100,320),
    (140,320),
    (180,320),
    (220,320),
    (300,80),
    (300,120),
    (300,160),
    (300,200),
    (300,240),
    (540,320),
    (500,320),
    (460,320),
    (420,320),
    (380,320),
    (300,560),
    (500,320),
    (300,480),
    (300,440),
    (300,400),
]

    def draw_top_frame(self):
        self.canvas.create_rectangle(0, 0, self.WIDTH, self.BOARD_TOP_OFFSET, fill="black", width=0)
        self.pause_btn = tk.Button(
            self.canvas,
            image=self.PAUSE_ICON,
            font=("Arial", 10, "bold"),
            bg="#000000",
            fg="white",
            activebackground="#666666",
            activeforeground="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=self.pause_game
        )
        self.pause_btn.place(x=self.WIDTH//2 - 15, y=self.BOARD_TOP_OFFSET//2 - 10, width=30, height=20)
        self.play_btn = tk.Button(
            self.canvas,
            image=self.PLAY_ICON,
            font=("Arial", 10, "bold"),
            bg="#000000",
            fg="white",
            highlightthickness=0,
            activebackground="#666666",
            activeforeground="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=self.resume_game
        )
        self.back_btn = tk.Button(
            self.canvas,
            image=self.BACK_TO_MAIN_MENU_IMG,
            font=("Arial", 10, "bold"),
            bg="#0BFF07",
            fg="white",
            highlightthickness=0,
            activebackground="#7BFF00",
            activeforeground="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=self.control_menu,
        )
        

    def pause_game(self):
        self.pause_btn.place_forget()

        if hasattr(self, 'glow_animating'):
            self.glow_animating = False
        for after_id in self.root.tk.eval('after info').split():
            self.root.after_cancel(after_id)
        self.can_roll = False
        self.is_rolling = False
        self.show_pause_message()

    def resume_game(self):
        self.hide_pause_message()
        current_player = self.players[self.turn]
        self.can_roll = True

        if self.can_roll and not self.is_rolling:

            if self.game_mode == "computer" and current_player == "RED":
                self.root.after(1000, self.computer_turn)
            else:
                self.root.after(1000, self.start_auto_roll)

    def show_pause_message(self):
        if hasattr(self, 'stop_rolling_sound'):
            self.stop_rolling_sound()
        self.pause_overlay = self.canvas.create_rectangle(
            0, self.BOARD_TOP_OFFSET, self.WIDTH, self.HEIGHT,
            fill="black", stipple="gray50", tags="pause_overlay"
        )
        self.canvas.create_window(
            self.WIDTH//2, (self.BOARD_TOP_OFFSET + self.HEIGHT)//3,
            window=self.play_btn,
            tags="pause_overlay"
        )
        self.save_game_state()
        
        # Create a new back button instance for the pause overlay
        back_btn_pause = tk.Button(
            self.canvas,
            image=self.BACK_TO_MAIN_MENU_IMG,
            font=("Arial", 10, "bold"),
            bg="#0BFF07",
            fg="white",
            highlightthickness=0,
            activebackground="#7BFF00",
            activeforeground="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=self.control_menu,  # This should directly call control_menu
        )
        
        self.canvas.create_window(
            self.WIDTH//2, (self.BOARD_TOP_OFFSET + self.HEIGHT)//2,
            window=back_btn_pause,
            tags="pause_overlay"
        )

    def hide_pause_message(self):
        self.canvas.delete("pause_overlay")
        self.pause_btn.place(x=self.WIDTH//2 - 15, y=self.BOARD_TOP_OFFSET//2 - 10, width=30, height=20)

    def draw_glow(self, player):
        o = self.BOARD_TOP_OFFSET
        colors = {"RED":"#A70105", "BLUE":"#01018B", "YELLOW":"#828200", "GREEN":"#117702"}
        coords = {
            "RED": (0, o, 240, 240+o),
            "BLUE": (0, 360+o, 240, 600+o),
            "YELLOW": (360, 360+o, 600, 600+o),
            "GREEN": (360, o, 600, 240+o)
        }

        if player in coords:
            self.canvas.create_rectangle(*coords[player], outline=colors[player], width=6)

    def draw_board(self):
        self.canvas.delete("board_layer")
        self.draw_top_frame()
        self._canvas_ids['board'] = self.canvas.create_image(0, self.BOARD_TOP_OFFSET, anchor="nw", image=self.BOARD_IMG, tags="board_layer")
        self.draw_glow(self.players[self.turn])

    def draw_pieces(self):
        self.canvas.delete("piece")
        all_coins = []
        for p in self.players:
            for i, pos in enumerate(self.player_positions[p]):

                if self.completed_coins[p][i]:
                    continue
                all_coins.append((p, i, pos))
        pos_groups = {}
        for p, i, pos in all_coins:
            pos_groups.setdefault(pos, []).append((p, i))
        for pos, group in pos_groups.items():
            num = len(group)
            start_offset = -(num - 1) * 5 / 2
            for idx, (p, ci) in enumerate(group):
                offset_y = start_offset + idx * 5
                x, y = pos
                img = self.coin_images[p]
                iid = self.canvas.create_image(x, y + offset_y, image=img, tags=("piece", f"{p}_{ci}"))
                self._image_refs[iid] = img

    def draw_dice_face(self):
        self.canvas.delete("dice")
        img = self.dice_images[self.dice_value - 1]
        self._canvas_ids['dice'] = self.canvas.create_image(self.DICE_POS[0], self.DICE_POS[1], anchor="nw", image=img, tags="dice")
        self._image_refs['dice'] = img

    def redraw_all(self):
        self.draw_board()
        self.draw_pieces()
        self.draw_dice_face()

    def handle_turn(self):
        self.glow_animating = False
        self.canvas.delete("movable_glow")
        self.turn = (self.turn + 1) % len(self.players)
        self.redraw_all()
        self.root.after(self.auto_roll_delay, self.start_auto_roll)

    def roll_animation(self):
        if not self.can_roll or self.is_rolling:
            return
        
        self.is_rolling = True
        self.can_roll = False
        
        # Start playing rolling sound
        self.play_rolling_sound()
        
        frames = self.rolling_images.copy()
        idx = 0

        def frame_step():
            nonlocal idx
            if idx < len(frames):
                self.canvas.delete("dice")
                img = frames[idx]
                self.canvas.create_image(self.DICE_POS[0]-10, self.DICE_POS[1]-10, anchor="nw", image=img, tags="dice")
                self._image_refs[f'rolling_{idx}'] = img
                idx += 1
                # CHANGED: Reduced delay from 200ms to 80ms for faster animation
                self.root.after(80, frame_step)
            else:
                self.final_roll()
        
        frame_step()


    def final_roll(self):
        if self.game_mode == "computer" and self.players[self.turn] == "RED" and self.ai:
            game_state = self.get_game_state()
            self.dice_value = self.ai.get_dice_roll(game_state)
        else:
            self.dice_value = random.randint(1, 6)
        
        self.canvas.delete("dice")
        img = self.dice_images[self.dice_value-1]
        self.canvas.create_image(self.DICE_POS[0], self.DICE_POS[1], anchor="nw", image=img, tags="dice")
        self._image_refs['dice'] = img
        self.is_rolling = False
        
        # Stop the rolling sound when dice value is shown
        self.stop_rolling_sound()
        
        # CHANGED: Reduced delay from 1000ms to 500ms for faster gameplay
        self.root.after(500, self.after_roll)


    def after_roll(self):

        if self.dice_value < 1 or self.dice_value > 6:
            self.dice_value = 1
            self.draw_dice_face()
        current = self.players[self.turn]
        movable = []
        for i in range(4):

            if self.completed_coins[current][i]:
                continue

            if self.active_coins[current][i]:
                start = self.coin_steps[current][i]

                if start + self.dice_value < len(self.move_paths[current]):
                    movable.append(i)
            elif self.dice_value == 6:
                movable.append(i)
        self.movable_coins = movable
        self.redraw_all()

        if movable:
            self.draw_glow_for_movable_coins()
        else:
            self.glow_animating = False
            self.canvas.delete("movable_glow")

        if not movable:
            self.handle_turn()
            self.can_roll = True
            return
        self.extra_turn = False

        if self.game_mode == "computer" and current == "RED" and self.ai and movable:
            game_state = self.get_game_state()
            coin_to_move = self.ai.choose_coin_to_move(game_state, self.dice_value)

            if coin_to_move != -1 and coin_to_move in movable:
                # CHANGED: Reduced delay from 500ms to 300ms for faster AI response
                self.root.after(300, lambda: self.auto_move_and_end(current, coin_to_move))
            else:

                if movable:
                    # CHANGED: Reduced delay from 500ms to 300ms for faster AI response
                    self.root.after(300, lambda: self.auto_move_and_end(current, movable[0]))
                else:
                    self.glow_animating = False
                    self.canvas.delete("movable_glow")
                    self.handle_turn()
                    self.can_roll = True
        elif len(movable) == 1:
            i = movable[0]
            self.can_roll = False
            # CHANGED: Reduced delay from 1000ms to 500ms for faster single-move response
            self.root.after(500, lambda: self.auto_move_and_end(current, i))
        else:
            self.can_roll = False

    def auto_move_and_end(self, player, i):
        self.extra_turn = False
        moved = self.move_coin(player, i)

        def after_move_done():

            if self.dice_value == 6 or getattr(self, "extra_turn", False):
                self.can_roll = True

                if self.game_mode == "computer" and player == "RED":
                    self.root.after(self.auto_roll_delay, self.computer_turn)
                else:
                    self.root.after(self.auto_roll_delay, self.start_auto_roll)
            else:
                self.handle_turn()
                self.can_roll = True
        # CHANGED: Reduced delay from 1000ms to 500ms for faster gameplay
        self.root.after(500, after_move_done)

    def move_coin(self, player, i):
        self.glow_animating = False
        self.canvas.delete("movable_glow")

        if hasattr(self, "movable_coins"):
            self.movable_coins = []

        if not self.active_coins[player][i]:
            if self.dice_value == 6:
                self.active_coins[player][i] = True
                self.coin_steps[player][i] = 0
                self.player_positions[player][i] = self.move_paths[player][0]
                self.redraw_all()
                self.check_for_cut(player, i)
                return True
            return False
            
        start = self.coin_steps[player][i]
        end = min(start + self.dice_value, len(self.move_paths[player]) - 1)

        if end == start:
            return False
            
        step = start + 1

        def step_anim():
            nonlocal step
            self.coin_steps[player][i] = step
            self.player_positions[player][i] = self.move_paths[player][step]
            self.redraw_all()
            step += 1
            if hasattr(self, 'player_move_sound'):
                self.player_move_sound.play()

            if step <= end:
                self.root.after(150, step_anim)
            else:
                self.check_for_cut(player, i)

                if end == len(self.move_paths[player]) - 1:
                    self.completed_coins[player][i] = True
                    self.active_coins[player][i] = False
                    self.extra_turn = True
                    if hasattr(self, 'success_sound'):
                        self.success_sound.play()
                    
                    # Check for win condition after coin completion
                    self.check_win_condition()

        step_anim()
        return True
    # def show_completion_message(self, player):
        # message = f"{player} coin completed!"
        # self.canvas.create_text(self.WIDTH//2, self.BOARD_TOP_OFFSET//2,
        #                        text=message, fill="white", font=("Arial", 14, "bold"),
        #                        tags="completion_message")
        # self.root.after(2000, lambda: self.canvas.delete("completion_message"))

    def animate_return_to_home(self, opponent, j, delay=5):

        if not self.active_coins[opponent][j]:
            self.player_positions[opponent][j] = self.get_home_position(opponent, j)
            self.coin_steps[opponent][j] = 0
            self.redraw_all()
            return
        current_step = self.coin_steps[opponent][j]

        if current_step >= len(self.move_paths[opponent]):
            current_step = len(self.move_paths[opponent]) - 1

        def step_back():
            nonlocal current_step

            if current_step > 0:
                current_step -= 1
                self.coin_steps[opponent][j] = current_step
                self.player_positions[opponent][j] = self.move_paths[opponent][current_step]
                self.redraw_all()
                self.root.after(delay, step_back)
            else:
                home_pos = self.get_home_position(opponent, j)
                cx, cy = self.player_positions[opponent][j]
                hx, hy = home_pos
                frames = 6
                frame = 0

                def interp():
                    nonlocal frame

                    if frame < frames:
                        t = (frame + 1) / frames
                        nx = int(cx + (hx - cx) * t)
                        ny = int(cy + (hy - cy) * t)
                        self.player_positions[opponent][j] = (nx, ny)
                        self.redraw_all()
                        frame += 1
                        self.root.after(int(delay / frames), interp)
                    else:
                        self.player_positions[opponent][j] = home_pos
                        self.active_coins[opponent][j] = False
                        self.coin_steps[opponent][j] = 0
                        self.redraw_all()
                interp()
        step_back()

    def check_for_cut(self, player, coin_index):

        if not hasattr(self, 'path'):
            self.restrict_cut_player_path()
        pos = self.player_positions[player][coin_index]

        if pos in self.path:
            return
        cut_occurred = False
        to_animate = []
        for opponent in self.players:

            if opponent == player:
                continue
            for j in range(4):

                if self.active_coins[opponent][j] and self.player_positions[opponent][j] == pos:
                    to_animate.append((opponent, j))
                    cut_occurred = True
                    self.cut_sound.play()  # Play cut sound effect

        if cut_occurred:
            self.extra_turn = True
            for idx, (opp, j) in enumerate(to_animate):
                self.root.after(idx * 120, lambda o=opp, k=j: self.animate_return_to_home(o, k))
        self.redraw_all()

    def get_home_position(self, player, i):
        home_positions = {
            "RED": [(80,103), (157,103), (80,180), (157,180)],
            "GREEN": [(443,103), (520,103), (443,180), (520,180)],
            "BLUE": [(80,463), (157,463), (80,540), (157,540)],
            "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
        }
        return home_positions[player][i] if player in home_positions else (0, 0)

    def on_click(self, event):

        if hasattr(self, 'game_paused') and self.game_paused:
            return
        x, y = event.x, event.y

        if self.game_mode == "computer" and self.players[self.turn] == "RED":
            return

        if self.can_roll:
            return
        current = self.players[self.turn]

        if not hasattr(self, "movable_coins") or not self.movable_coins:
            return
        for i, pos in enumerate(self.player_positions[current]):

            if self.completed_coins[current][i]:
                continue
            img = self.coin_images[current]
            w, h = img.width(), img.height()
            px, py = pos

            if (px - w//2 <= x <= px + w//2) and (py - h//2 <= y <= py + h//2):

                if i not in self.movable_coins:
                    return
                self.extra_turn = False
                moved = self.move_coin(current, i)

                if moved:
                    self.can_roll = False
                    self.movable_coins = []

                    def after_move():

                        if self.dice_value == 6 or getattr(self, "extra_turn", False):
                            self.can_roll = True
                            self.root.after(self.auto_roll_delay, self.start_auto_roll)
                        else:
                            self.handle_turn()
                            self.can_roll = True
                    # CHANGED: Reduced delay from 400ms to 200ms for faster response
                    self.root.after(200, after_move)
                break

    def draw_glow_for_movable_coins(self):
        self.canvas.delete("movable_glow")

        if not hasattr(self, "movable_coins"):
            return
        current = self.players[self.turn]
        self.glow_angle = 0
        self.glow_animating = True
        self.glow_ids = []

        def update_rotation():

            if not self.glow_animating:
                return
            self.canvas.delete("movable_glow")

            try:
                angle_img = Image.open(resource_path("Images/chakra.png")).convert("RGBA").resize((80, 80), Image.LANCZOS)
                rotated_img = angle_img.rotate(self.glow_angle, resample=Image.BICUBIC)
                ring_tk = ImageTk.PhotoImage(rotated_img)
                for i in self.movable_coins:
                    x, y = self.player_positions[current][i]
                    img_id = self.canvas.create_image(x, y, image=ring_tk, tags="movable_glow")
                    self._image_refs[f"glow_{current}_{i}"] = ring_tk
                    self.glow_ids.append(img_id)
                self.canvas.tag_lower("movable_glow", "piece")
                self.glow_angle = (self.glow_angle + 8) % 360
                # CHANGED: Reduced delay from 1000ms to 500ms for faster glow animation
                self.root.after(50, update_rotation)

            except Exception as e:
                pass
        update_rotation()

    def check_win_condition(self):
        """Check if any player has won the game"""
        for player in self.players:
            if all(self.completed_coins[player]):
                self.winner = player
                self.show_win_celebration(player)
                return True
        return False

    def show_win_celebration(self, winner):
        """Show win celebration overlay with star burst animation"""
        # Stop any ongoing game sounds
        if hasattr(self, 'stop_rolling_sound'):
            self.stop_rolling_sound()
        
        # Stop any ongoing animations
        self.glow_animating = False
        self.can_roll = False
        self.is_rolling = False
        
        # Create win overlay
        self.win_overlay = self.canvas.create_rectangle(
            0, self.BOARD_TOP_OFFSET, self.WIDTH, self.HEIGHT,
            fill="black", stipple="gray50", tags="win_overlay"
        )
        
        # Display winner text
        winner_color = {"RED": "#FF0000", "GREEN": "#00FF00", 
                    "BLUE": "#0000FF", "YELLOW": "#FFFF00"}
        color = winner_color.get(winner, "#FFFFFF")
        
        self.canvas.create_text(
            self.WIDTH//2, self.HEIGHT//3 - 50,
            text=f"{winner} WINS!",
            fill=color, font=("Arial", 36, "bold"),
            tags="win_overlay"
        )
        
        self.canvas.create_text(
            self.WIDTH//2, self.HEIGHT//3 + 10,
            text="Congratulations!",
            fill="white", font=("Arial", 24, "bold"),
            tags="win_overlay"
        )
        
        # Create buttons
        self.play_again_btn = tk.Button(
            self.canvas,
            text="Play Again",
            font=("Arial", 16, "bold"),
            bg="#21fa04",
            fg="black",
            activebackground="#79f874",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=self.restart_game
        )
        
        self.main_menu_btn = tk.Button(
            self.canvas,
            text="Main Menu",
            font=("Arial", 16, "bold"),
            bg="#ff0000",
            fg="white",
            activebackground="#ff4366",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=self.control_menu
        )
        
        # Place buttons
        self.canvas.create_window(
            self.WIDTH//2, self.HEIGHT//2 + 50,
            window=self.play_again_btn,
            tags="win_overlay"
        )
        
        self.canvas.create_window(
            self.WIDTH//2, self.HEIGHT//2 + 100,
            window=self.main_menu_btn,
            tags="win_overlay"
        )
        
        # Start star burst animation
        self.star_burst_running = True
        self.stars = []
        self.pause_btn.place_forget()

        if hasattr(self, 'glow_animating'):
            self.glow_animating = False
        for after_id in self.root.tk.eval('after info').split():
            self.root.after_cancel(after_id)
        self.can_roll = False
        self.is_rolling = False
        self.winning_sound.play(loops=-1)
        self.start_star_burst_animation()

    # def pause_game(self):
    #     self.pause_btn.place_forget()

    #     if hasattr(self, 'glow_animating'):
    #         self.glow_animating = False
    #     for after_id in self.root.tk.eval('after info').split():
    #         self.root.after_cancel(after_id)
    #     self.can_roll = False
    #     self.is_rolling = False
    #     self.show_pause_message()
        
    def create_star_points(self, x, y, size):
        """Generate 5-point star coordinates."""
        points = []
        for i in range(10):
            angle = math.pi / 5 * i
            radius = size if i % 2 == 0 else size / 2.5
            px = x + math.sin(angle) * radius
            py = y - math.cos(angle) * radius
            points.append(px)
            points.append(py)
        return points

    def create_star(self):
        """Create one star with random attributes."""
        size = random.randint(8, 30)
        color = random.choice(self.COLORS)
        start_x = self.WIDTH / 2 + random.uniform(-100, 100)
        start_y = self.HEIGHT - 50

        points = self.create_star_points(start_x, start_y, size)
        star_id = self.canvas.create_polygon(points, fill=color, outline="", smooth=True, tags="win_star")

        drift_x = random.uniform(-300, 300)
        rise_y = random.uniform(self.HEIGHT * 0.4, self.HEIGHT * 0.7)
        rotate = random.uniform(-720, 720)
        duration = random.uniform(3.5, 5.5)  # seconds
        fps = 60

        self.stars.append({
            "id": star_id,
            "x": start_x,
            "y": start_y,
            "dx": drift_x / (duration * fps),
            "dy": -rise_y / (duration * fps),
            "rotation": rotate / (duration * fps),
            "opacity": 1.0,
            "life": duration * fps
        })

    def animate_stars(self):
        """Update position and fade stars."""
        if not self.star_burst_running:
            return
            
        for star in self.stars[:]:
            star["x"] += star["dx"]
            star["y"] += star["dy"]
            star["life"] -= 1

            # fade and shrink
            if star["life"] < 50:
                star["opacity"] -= 0.02

            # update visual
            size = max(3, (star["life"] / (60 * 5)) * 25)
            points = self.create_star_points(star["x"], star["y"], size)
            self.canvas.coords(star["id"], *points)

            # apply opacity (simulate by color brightness)
            opacity_factor = max(0, star["opacity"])
            # For tkinter, we simulate opacity by adjusting stipple pattern
            if opacity_factor < 0.5:
                self.canvas.itemconfig(star["id"], stipple="gray50")
            else:
                self.canvas.itemconfig(star["id"], stipple="")

            # remove dead
            if star["opacity"] <= 0 or star["life"] <= 0:
                self.canvas.delete(star["id"])
                self.stars.remove(star)

        if self.star_burst_running:
            self.root.after(16, self.animate_stars)  # ~60 FPS

    def continuous_star_throw(self):
        """Continuously throw new stars."""
        if not self.star_burst_running:
            return
            
        for _ in range(random.randint(1, 2)):
            self.create_star()
            
        if self.star_burst_running:
            self.root.after(180, self.continuous_star_throw)

    def start_star_burst_animation(self):
        """Start the star burst animation."""
        if os.path.exists(self.SAVE_FILE):
            os.remove(self.SAVE_FILE)
        self.animate_stars()
        self.continuous_star_throw()

    def stop_star_burst_animation(self):
        """Stop the star burst animation."""
        self.winning_sound.stop()
        self.star_burst_running = False
        for star in self.stars:
            self.canvas.delete(star["id"])
        self.stars = []
    
    def restart_game(self):
        """Restart the game with same settings"""
        self.stop_star_burst_animation()
        self.canvas.delete("win_overlay")
        self.canvas.delete("win_star")
        self.winner = None
        
        # Reset game state
        self.dice_value = 1
        self.turn = 0
        self.active_coins = {p: [False]*4 for p in self.players}
        self.coin_steps = {p: [0]*4 for p in self.players}
        self.completed_coins = {p: [False]*4 for p in self.players}
        self.player_positions = {
            "RED": [(80,103), (157,103), (80,180), (157,180)],
            "GREEN": [(443,103), (520,103), (443,180), (520,180)],
            "BLUE": [(80,463), (157,463), (80,540), (157,540)],
            "YELLOW": [(443,463), (520,463), (443,540), (520,540)]
        }
        
        # Redraw everything
        self.redraw_all()
        self.canvas.bind("<Button-1>", self.on_click)
        
        # Start the game
        self.can_roll = True
        self.root.after(1000, self.start_auto_roll)
        
        
if __name__ == "__main__":
    root = tk.Tk()
    app = LudoGame(root)
    root.mainloop()