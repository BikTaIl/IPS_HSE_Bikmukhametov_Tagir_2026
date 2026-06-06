from abc import ABC, abstractmethod
import random
from typing import List, Tuple, Dict, Callable


class PairingError(Exception):
    """
    Ошибка выбрасывается, когда алгоритм жеребьевки заходит в тупик 
    и не может подобрать пары.
    """
    def __init__(self, message="Невозможно составить пары для следующего тура."):
        self.message = message
        super().__init__(self.message)


class WinFunction():
    """
    Абстрактный класс функции, возвращающей вероятности исходов матча 
    в зависимости от силы команды и силы соперника.
    """
    def __init__(self, win_function):
        super().__init__()
        self.win_function: Callable = win_function

    def change_win_function(self, win_function: Callable) -> None:
        self.win_function = win_function

    def match_probabilities(self, plus_1: int, minus_1: int, plus_2: int, minus_2: int) -> Tuple[float, float, float]:
        """
        Возвращает кортеж из трех вероятностей (каждая от 0.0 до 1.0):
        (Вероятность победы первой команды, Вероятность ничьей, Вероятность победы второй команды).
        
        В сумме три значения должны давать 1.0.
        """
        return self.win_function(plus_1, minus_1, plus_2, minus_2)



class BaseTournamentSystem(ABC):
    """
    Абстрактный класс для описания логики турнирной системы (Швейцарская, Круговая и т.д.).
    """
    name = "Базовый тип турнира"

    def __init__(self, teams: Dict[str, list], leagues: Dict[str, int], win_function: WinFunction):
        # Словарь команд: 
        # {'Название команды': [плюсы, минусы, текущие_очки, 'Название лиги']}
        self.teams = teams
        
        # Словарь лиг: 
        # {'Название лиги': количество команд в ней}
        self.leagues = leagues
        
        self.win_function = win_function
        self.tour_counter = 0
        
        # Массив прошедших боев: [('Команда 1', 'Команда 2', результат, номер_тура)]
        # результат: 1 (победа 1-й), 0 (ничья), -1 (победа 2-й)
        self.match_history: List[Tuple[str, str, int, int]] = []

    @abstractmethod
    def __str__(self) -> str:
        """Возвращает название типа турнира."""
        pass

    @abstractmethod
    def get_total_tours(self) -> Dict[str, int]:
        """Возвращает словарь с количеством туров для каждой лиги {Лига: кол-во туров}"""
        pass

    @abstractmethod
    def generate_next_tour(self) -> List[Tuple[str, str]]:
        """
        Генерирует список пар для следующего тура.
        Реализация должна группировать команды по их лигам при составлении пар.
        Возвращает массив кортежей: [('Команда А', 'Команда Б'), ...]
        """
        pass

    @abstractmethod
    def count_ladder(self) -> Dict[str, List[Tuple[str, int, int]]]:
        """
        Считает порядок мест в каждой лиге. 
        Возвращает словарь, где ключ - лига, а значение - массив кортежей:
        [('Название команды', набранные_очки, место), ...]
        
        (Реализуется в наследниках, так как правила тай-брейка могут отличаться)
        """
        pass

    def simulate_tour(self, upcoming_matches: List[Tuple[str, str]]) -> None:
        """
        Проводит симуляцию текущего тура по списку предстоящих матчей. 
        Дополняет список прошедших матчей и изменяет количество набранных командами очков.
        """
        self.tour_counter += 1
        
        for team1, team2 in upcoming_matches:
            # Извлекаем параметры команд (четвертый элемент - лига - для симуляции боя не нужен)
            p1, m1, pts1, league1 = self.teams[team1]
            p2, m2, pts2, league2 = self.teams[team2]
            
            # Получаем вероятности (Победа 1, Ничья, Победа 2)
            prob_win, prob_draw, prob_loss = self.win_function.match_probabilities(p1, m1, p2, m2)
            
            # Ставим случайный трешхолд для победы
            treshold = random.random()
            
            # Определяем исход
            if treshold <= prob_win:
                result = 1  # Победила первая команда
            elif treshold <= prob_win + prob_draw:
                result = 0  # Ничья
            else:
                result = -1 # Победила вторая команда (т.к. treshold попадает в оставшийся отрезок)
                
            # Записываем результат в историю боев
            self.match_history.append((team1, team2, result, self.tour_counter))
            
            # Обновляем очки в основном словаре: +2 победа, +1 ничья, 0 поражение
            if result == 1:
                self.teams[team1][2] += 2
            elif result == -1:
                self.teams[team2][2] += 2
            else:
                self.teams[team1][2] += 1
                self.teams[team2][2] += 1