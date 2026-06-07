from django.test import TestCase
from core.constructor.abstract import BaseTournamentSystem, WinFunction

class DummyTournament(BaseTournamentSystem):
    """Фиктивный класс для тестирования базовых методов турнирной системы"""
    def __str__(self):
        return "Dummy"
        
    def get_total_tours(self):
        return {"L1": 1}
        
    def generate_next_tour(self):
        return [("TeamA", "TeamB")]
        
    def count_ladder(self):
        return {}

class AbstractTournamentTests(TestCase):
    def setUp(self):
        self.teams = {
            'TeamA': [10, 5, 0, 'L1'], # плюсы, минусы, очки, лига
            'TeamB': [5, 10, 0, 'L1']
        }
        self.leagues = {'L1': 2}

    def test_win_function_updates(self):
        """Проверка инициализации и замены функции вероятностей"""
        func = WinFunction(lambda p1, m1, p2, m2: (0.8, 0.1, 0.1))
        self.assertEqual(func.match_probabilities(1, 1, 1, 1), (0.8, 0.1, 0.1))
        
        func.change_win_function(lambda p1, m1, p2, m2: (0.0, 1.0, 0.0))
        self.assertEqual(func.match_probabilities(1, 1, 1, 1), (0.0, 1.0, 0.0))

    def test_simulate_tour_logic(self):
        """Проверка логики симуляции тура (начисление очков и история)"""
        # Всегда побеждает первая команда
        func = WinFunction(lambda p1, m1, p2, m2: (1.0, 0.0, 0.0))
        tournament = DummyTournament(self.teams, self.leagues, func)
        
        # Симулируем тур, где A играет с B
        tournament.simulate_tour([("TeamA", "TeamB")])
        
        # Проверяем, что счетчик туров увеличился
        self.assertEqual(tournament.tour_counter, 1)
        
        # Команда А (первая) должна получить 2 очка, команда B - 0
        self.assertEqual(tournament.teams['TeamA'][2], 2)
        self.assertEqual(tournament.teams['TeamB'][2], 0)
        
        # В истории должна появиться запись (TeamA, TeamB, 1(победа 1-ой), 1 тур)
        self.assertEqual(tournament.match_history[0], ("TeamA", "TeamB", 1, 1))
