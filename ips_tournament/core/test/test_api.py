import json
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from core.models import User, Tournament, Team, Fight, FAQ, Olympiad

class MasterTournamentApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.superadmin = User.objects.create_user(username='super', password='123', role=User.Role.SUPERADMIN)
        self.admin = User.objects.create_user(username='admin', password='123', role=User.Role.ADMIN)
        self.editor = User.objects.create_user(username='editor', password='123', role=User.Role.EDITOR)
        self.ordinary_user = User.objects.create_user(username='user', password='123', role=User.Role.USER)

        self.tournament = Tournament.objects.create(tournament_number=1, start_date='2026-01-01', end_date='2026-01-02')

        self.team1 = Team.objects.create(
            tournament=self.tournament, work_name='W1', child_name='Team A', 
            school_class=10, league='L1', players_quantity='6', current_points=0
        )
        self.team2 = Team.objects.create(
            tournament=self.tournament, work_name='W2', child_name='Team B', 
            school_class=10, league='L1', players_quantity='6', current_points=0
        )

    def test_team1_clear_win(self):
        """Разрыв > 3: Команда 1 должна получить 2 балла, Команда 2 - 0 баллов"""
        self.client.login(username='admin', password='123')
        data = {'team1_id': self.team1.id, 'team2_id': self.team2.id, 'points1': 15, 'points2': 10, 'tour': 1}
        response = self.client.post(reverse('add_fight'), json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.team1.refresh_from_db()
        self.team2.refresh_from_db()
        self.assertEqual(self.team1.current_points, 2)
        self.assertEqual(self.team2.current_points, 0)

    def test_draw_condition_exact_gap(self):
        """Разрыв ровно 3 очка (13:10): Считается ничьей. Обе получают по 1 баллу"""
        self.client.login(username='admin', password='123')
        data = {'team1_id': self.team1.id, 'team2_id': self.team2.id, 'points1': 13, 'points2': 10, 'tour': 1}
        self.client.post(reverse('add_fight'), json.dumps(data), content_type='application/json')
        
        self.team1.refresh_from_db()
        self.team2.refresh_from_db()
        self.assertEqual(self.team1.current_points, 1)
        self.assertEqual(self.team2.current_points, 1)

    def test_cannot_fight_itself(self):
        """API должно отклонять бой команды самой с собой"""
        self.client.login(username='admin', password='123')
        data = {'team1_id': self.team1.id, 'team2_id': self.team1.id, 'points1': 10, 'points2': 10, 'tour': 1}
        response = self.client.post(reverse('add_fight'), json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('не может играть сама с собой', response.json()['error'])

    def test_remove_fight_result_rollback(self):
        """Проверка отката очков при удалении результата боя"""
        self.client.login(username='admin', password='123')
        
        self.team1.current_points = 2
        self.team1.save()
        
        fight = Fight.objects.create(
            team_one=self.team1, team_two=self.team2,
            team_one_points=15, team_two_points=10,
            tour_number=1, ended=True
        )

        response = self.client.post(reverse('remove_fight_result'), json.dumps({'fight_id': fight.id}), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        self.team1.refresh_from_db()
        self.assertEqual(self.team1.current_points, 0) 
        
        fight.refresh_from_db()
        self.assertFalse(fight.ended)

    def test_add_scheduled_fight_result(self):
        """Добавление счета в уже запланированный в расписании бой"""
        self.client.login(username='editor', password='123') 
        fight = Fight.objects.create(team_one=self.team1, team_two=self.team2, tour_number=2, ended=False)

        data = {'team1_id': self.team1.id, 'team2_id': self.team2.id, 'points1': 10, 'points2': 10, 'tour': 2}
        response = self.client.post(reverse('add_fight_result'), json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        fight.refresh_from_db()
        self.assertTrue(fight.ended)
        self.assertEqual(fight.team_one_points, 10)

    def test_schedule_fight_api(self):
        """Постановка боя в расписание без результатов"""
        self.client.login(username='admin', password='123')
        data = {
            'team1_id': self.team1.id, 
            'team2_id': self.team2.id, 
            'tour': 3, 
            'judge_first': 'Старков Е.Е.',
            'place': 'Aud 1', 
            'value_day': '2026-01-01', 
            'fight_time': '10:00',
            'solution_place': 'Aud 1', 
            'solution_time': '12:00'
        }
        response = self.client.post(reverse('schedule_fight'), json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Fight.objects.filter(tour_number=3, ended=False).exists())

    # ==========================================
    # БЛОК 2: ТЕСТИРОВАНИЕ CRUD ДЛЯ КОМАНД И FAQ
    # ==========================================

    def test_team_crud_operations(self):
        """Проверка добавления, редактирования и удаления команд"""
        self.client.login(username='admin', password='123')
        
        # Добавление
        add_data = {'work_name': 'W3', 'child_name': 'Team C', 'school_class': 11, 'league': 'L2'}
        self.client.post(reverse('add_team'), json.dumps(add_data), content_type='application/json')
        self.assertTrue(Team.objects.filter(child_name='Team C').exists())
        
        team_c = Team.objects.get(child_name='Team C')
        
        # Редактирование
        edit_data = {'team_id': team_c.id, 'work_name': 'W3_edit', 'child_name': 'Team C_edit', 'school_class': 11, 'league': 'L3'}
        self.client.post(reverse('edit_team'), json.dumps(edit_data), content_type='application/json')
        team_c.refresh_from_db()
        self.assertEqual(team_c.child_name, 'Team C_edit')

        # Удаление
        self.client.post(reverse('delete_team'), json.dumps({'team_id': team_c.id}), content_type='application/json')
        self.assertFalse(Team.objects.filter(id=team_c.id).exists())

    def test_faq_crud(self):
        """Создание и удаление ЧаВО"""
        self.client.login(username='admin', password='123')
        
        self.client.post(reverse('add_faq'), json.dumps({'question': 'Q1?', 'answer': 'A1!'}), content_type='application/json')
        self.assertTrue(FAQ.objects.filter(question='Q1?').exists())
        
        faq = FAQ.objects.get(question='Q1?')
        self.client.post(reverse('delete_faq'), json.dumps({'faq_id': faq.id}), content_type='application/json')
        self.assertFalse(FAQ.objects.filter(id=faq.id).exists())


    def test_olympiad_save_and_get(self):
        """Проверка сохранения и получения результатов олимпиады"""
        self.client.login(username='admin', password='123')
        
        data = {'team_id': self.team1.id, 'plus_count': 10, 'minus_count': 2}
        response = self.client.post(reverse('save_olympiad'), json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        res = self.client.get(reverse('get_olympiad_list') + '?school_class=10')
        teams_data = res.json()['teams']

        self.assertEqual(teams_data[0]['name'], 'Team A')
        self.assertEqual(teams_data[0]['plus_count'], 10)


    def test_html_views_and_permissions(self):
        """Проверка отдачи HTML страниц и базовых прав доступа"""
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('broadcast')).status_code, 200)
        self.assertEqual(self.client.get(reverse('info_page')).status_code, 200)
        
        self.assertEqual(self.client.get(reverse('admin_panel')).status_code, 302)
        
        self.client.login(username='user', password='123')
        self.assertEqual(self.client.get(reverse('constructor_page')).status_code, 403)
        
        self.client.login(username='admin', password='123')
        self.assertEqual(self.client.get(reverse('admin_panel')).status_code, 200)
        self.assertEqual(self.client.get(reverse('constructor_page')).status_code, 200)

    def test_create_tournament_permissions(self):
        """Пересоздать турнир может только SUPERADMIN"""
        self.client.login(username='admin', password='123')
        data = {'password': '123', 'number': 2, 'start_date': '2026-02-01', 'end_date': '2026-02-02'}
        self.assertEqual(self.client.post(reverse('create_tournament'), json.dumps(data), content_type='application/json').status_code, 403)

        self.client.logout()
        self.client.login(username='super', password='123')
        self.assertEqual(self.client.post(reverse('create_tournament'), json.dumps(data), content_type='application/json').status_code, 200)
        self.assertEqual(Tournament.objects.first().tournament_number, 2)


    def test_upload_teams_csv(self):
        """Парсинг команд из CSV"""
        self.client.login(username='admin', password='123')
        csv_content = "WorkName1;ChildName1;10;LeagueA\nWorkName2;ChildName2;11;LeagueB".encode('utf-8-sig')
        csv_file = SimpleUploadedFile("teams.csv", csv_content, content_type="text/csv")
        
        response = self.client.post(reverse('upload_teams_csv'), {'file': csv_file})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Team.objects.filter(child_name='ChildName1', school_class=10).exists())

    def test_exports_csv_api(self):
        """Проход по всем ручкам выгрузки в CSV"""
        self.client.login(username='admin', password='123')
        export_types = ['teams', 'olympiad', 'schedule', 'matches']
        
        for exp_type in export_types:
            response = self.client.get(reverse('export_csv', args=[exp_type]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'text/csv')