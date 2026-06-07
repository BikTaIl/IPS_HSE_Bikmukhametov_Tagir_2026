from django.test import TestCase
from core.constructor.round_robin import RoundRobinTournamentSystem
from core.constructor.abstract import PairingError, WinFunction

class RoundRobinTests(TestCase):
    def setUp(self):
        # teams: {Название: [плюсы, минусы, очки, лига]}
        self.teams_even = {
            'T1': [10, 5, 2, 'L1'],
            'T2': [8, 8, 2, 'L1'],
            'T3': [5, 10, 0, 'L1'],
            'T4': [0, 0, 0, 'L1']
        }
        self.leagues_even = {'L1': 4}
        
        self.teams_odd = {
            'T1': [0, 0, 0, 'L2'],
            'T2': [0, 0, 0, 'L2'],
            'T3': [0, 0, 0, 'L2']
        }
        self.leagues_odd = {'L2': 3}
        
        self.win_func = WinFunction(lambda p1, m1, p2, m2: (1, 0, 0))

    def test_total_tours_calculation(self):
        """N-1 для четных, N для нечетных, 0 если команд <= 1"""
        rr_even = RoundRobinTournamentSystem(self.teams_even, self.leagues_even, self.win_func)
        self.assertEqual(rr_even.get_total_tours()['L1'], 3)
        
        rr_odd = RoundRobinTournamentSystem(self.teams_odd, self.leagues_odd, self.win_func)
        self.assertEqual(rr_odd.get_total_tours()['L2'], 3)
        
        rr_single = RoundRobinTournamentSystem({'T1': [0,0,0,'L3']}, {'L3': 1}, self.win_func)
        self.assertEqual(rr_single.get_total_tours()['L3'], 0)

    def test_ladder_sorting_logic(self):
        """Таблица сортируется по очкам, затем личным встречам, затем плюсам-минусам"""
        rr = RoundRobinTournamentSystem(self.teams_even, self.leagues_even, self.win_func)
        # T1 и T2 имеют по 2 очка. Сымитируем личную встречу: T2 победила T1.
        rr.match_history = [('T2', 'T1', 1, 1)] # 1 значит победа первой команды (T2)
        
        ladder = rr.count_ladder()['L1']
        # Ожидаем порядок: T2 (личная встреча), T1, T3 (разница -5), T4 (разница 0)
        # T4 выше T3, т.к. 0 > -5
        self.assertEqual(ladder[0][0], 'T2')
        self.assertEqual(ladder[1][0], 'T1')
        self.assertEqual(ladder[2][0], 'T4')
        self.assertEqual(ladder[3][0], 'T3')

    def test_pairing_even_teams(self):
        """Карусельная генерация пар для четного числа команд"""
        rr = RoundRobinTournamentSystem(self.teams_even, self.leagues_even, self.win_func)
        pairs = rr.generate_next_tour()
        self.assertEqual(len(pairs), 2) # 4 команды -> 2 пары

    def test_pairing_odd_teams(self):
        """Для нечетного числа добавляется bye (пустая команда), пара пропускается"""
        rr = RoundRobinTournamentSystem(self.teams_odd, self.leagues_odd, self.win_func)
        pairs = rr.generate_next_tour()
        # 3 команды + 1 пустая = 4 слота = 2 пары, но одна содержит пустую, поэтому вернется только 1 реальная пара
        self.assertEqual(len(pairs), 1)

    def test_pairing_limit_exceeded(self):
        """Ошибка, если запрашивается жеребьевка, когда все туры сыграны"""
        rr = RoundRobinTournamentSystem(self.teams_even, self.leagues_even, self.win_func)
        rr.tour_counter = 3 # Уже сыграно 3 тура из 3 возможных
        with self.assertRaises(PairingError) as context:
            rr.generate_next_tour()
        self.assertIn("все команды уже сыграли друг с другом", str(context.exception))