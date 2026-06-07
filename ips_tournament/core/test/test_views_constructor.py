import io
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from core.views_constructor import parse_constructor_files

class ViewsConstructorTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.valid_teams_csv = "№;Название;Класс;Лига\n1;Team A;7;Высшая\n2;Team B;7;Высшая\n".encode('utf-8-sig')
        self.valid_oly_csv = "№;Класс;Название;Плюсы;Минусы\n1;7;Team A;10;5\n2;7;Team B;5;10\n".encode('utf-8-sig')
        self.valid_matches_csv = "№;Класс;Тур;Команда 1;Счет 1;Команда 2;Счет 2\n1;7;1;Team A;10.5;Team B;9.0\n".encode('utf-8-sig')

    def test_parse_files_success(self):
        """Проверка успешного парсинга команд, олимпиады и матчей"""
        f_teams = io.BytesIO(self.valid_teams_csv)
        f_oly = io.BytesIO(self.valid_oly_csv)
        f_matches = io.BytesIO(self.valid_matches_csv)
        
        teams, leagues, match_history, ignored = parse_constructor_files(f_teams, f_oly, f_matches)
        
        self.assertEqual(len(teams), 2)
        self.assertEqual(leagues['Высшая'], 2)
        self.assertEqual(teams['Team A'][0], 10) # плюсы
        
        self.assertEqual(len(match_history), 1)
        # Team A (10.5) выиграла у Team B (9.0) -> результат 1 (победа первой)
        self.assertEqual(match_history[0], ('Team A', 'Team B', 1, 1))
        # Team A должна получить 2 балла в points
        self.assertEqual(teams['Team A'][2], 2)

    def test_parse_files_missing_team_in_oly(self):
        """Ошибка, если команда из файла Олимпиады не числится в основном списке"""
        f_teams = io.BytesIO(self.valid_teams_csv)
        invalid_oly = "№;Класс;Название;Плюсы;Минусы\n1;7;GHOST TEAM;10;5\n".encode('utf-8-sig')
        f_oly = io.BytesIO(invalid_oly)
        
        with self.assertRaises(ValueError) as context:
            parse_constructor_files(f_teams, f_oly)
        self.assertIn("не найдена в основном списке команд!", str(context.exception))

    def test_parse_files_missing_main_teams(self):
        """Ошибка, если команды из основного списка пропущены в Олимпиаде"""
        f_teams = io.BytesIO("№;Название;Класс;Лига\n1;Team A;7;Высшая\n2;Team B;7;Высшая\n".encode('utf-8-sig'))
        f_oly = io.BytesIO("№;Класс;Название;Плюсы;Минусы\n1;7;Team A;10;5\n".encode('utf-8-sig')) # Нет Team B
        
        with self.assertRaises(ValueError) as context:
            parse_constructor_files(f_teams, f_oly)
        self.assertIn("отсутствуют команды из основного списка: Team B", str(context.exception))

    def test_get_tournaments_api(self):
        """Получение списка доступных систем"""
        response = self.client.get('/api/constructor/tournaments/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data) >= 2)
        self.assertEqual(data[0]['name'], "Швейцарская система")

    def test_calculate_tours_api(self):
        """API возвращает верный лимит туров при загрузке команд"""
        response = self.client.post('/api/constructor/calc-tours/', {
            'tournament_id': 1, # 1 - Круговая
            'teams': SimpleUploadedFile("teams.csv", self.valid_teams_csv)
        })
        self.assertEqual(response.status_code, 200)
        # 2 команды в круговой системе -> 1 тур
        self.assertEqual(response.json()['tours'], 1)

    def test_run_simulation_api(self):
        """API корректно проводит симуляции Монте-Карло"""
        response = self.client.post('/api/constructor/simulate/', {
            'tournament_id': 0, # Швейцарка
            'sim_count': 5,
            'code': 'return (0.33, 0.33, 0.34)', # Базовый рандомный код
            'max_tours': 1,
            'teams': SimpleUploadedFile("teams.csv", self.valid_teams_csv),
            'olympiad': SimpleUploadedFile("oly.csv", self.valid_oly_csv)
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['results']), 2) # Ожидаем 2 команды

    def test_generate_pairing_api(self):
        """API генерирует CSV-файл с жеребьевкой"""
        response = self.client.post('/api/constructor/pairing/', {
            'tournament_id': 1,
            'code': 'return (1, 1, 1)', 
            'teams': SimpleUploadedFile("teams.csv", self.valid_teams_csv),
            'olympiad': SimpleUploadedFile("oly.csv", self.valid_oly_csv)
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
