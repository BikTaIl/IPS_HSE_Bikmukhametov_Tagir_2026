import json
import csv
import io
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.db.utils import IntegrityError
from django.db.models import Max, Q
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, Tournament, Team, Fight, Olympiad, FAQ


# --- 1. Отображение HTML страницы ---

@login_required
def admin_panel_view(request):
    """Отображает HTML-страницу панели администратора"""
    return render(request, 'admin_panel.html')

@login_required
def constructor_page(request):
    """Отображает HTML-страницу конструктора"""
    # Защита: пускаем только админов
    if request.user.role not in ['ADMIN', 'SUPERADMIN'] and not request.user.is_superuser:
        return HttpResponseForbidden("Доступ запрещен. Только для организаторов.")
        
    return render(request, 'constructor.html')

def broadcast_view(request):
    """Отображает вкладку трансляции турнира"""
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    classes = []
    if current_tournament:
        classes = Team.objects.filter(tournament=current_tournament)\
                              .exclude(school_class__isnull=True)\
                              .values_list('school_class', flat=True)\
                              .distinct().order_by('school_class')

    context = {
        'tournament': current_tournament,
        'classes': classes,
    }
    return render(request, 'broadcast.html', context)

def info_page_view(request):
    """Отображает вкладку с общей информацией о турнире (Доступно всем)"""
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    context = {
        'tournament': current_tournament,
        'faqs': current_tournament.faqs.all() if current_tournament else [],
    }
    return render(request, 'info_page.html', context)

# --- 2. Функции API для JavaScript ---

@login_required
@require_GET
def get_users_by_role(request):
    """Возвращает список пользователей запрошенной роли."""
    role_param = request.GET.get('role', '').upper()
    if role_param not in [User.Role.ADMIN, User.Role.EDITOR]:
        return JsonResponse({'error': 'Неверная роль'}, status=400)

    users = User.objects.filter(role=role_param).select_related('granted_by')
    
    data = []
    for u in users:
        data.append({
            'login': u.username,
            'granted_by': u.granted_by.username if u.granted_by else 'Система',
            'can_delete': request.user.can_manage(u) # Проверка иерархии
        })
        
    return JsonResponse({'users': data})

@login_required
@require_POST
def add_role(request):
    """Назначает пользователю новую роль."""
    try:
        data = json.loads(request.body)
        target_login = data.get('login')
        new_role = data.get('role', '').upper()
        
        if new_role not in [User.Role.ADMIN, User.Role.EDITOR]:
            return JsonResponse({'error': 'Неверная роль'}, status=400)
            
        if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
            return JsonResponse({'error': 'Недостаточно прав'}, status=403)

        target_user = User.objects.get(username=target_login)
        
        if target_user.role == new_role:
            return JsonResponse({'error': 'Пользователь уже имеет эту роль'}, status=400)

        target_user.role = new_role
        target_user.granted_by = request.user
        target_user.save()
        
        return JsonResponse({'status': 'success'})
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'Пользователь не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def remove_role(request):
    """Снимает роль с пользователя."""
    try:
        data = json.loads(request.body)
        target_login = data.get('login')
        
        target_user = User.objects.get(username=target_login)
        
        if not request.user.can_manage(target_user):
            return JsonResponse({'error': 'Недостаточно прав для отзыва роли'}, status=403)
            
        target_user.role = User.Role.USER
        target_user.granted_by = None
        target_user.save()
        
        return JsonResponse({'status': 'success'})
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'Пользователь не найден'}, status=404)
    

@login_required
@require_POST
def create_new_user(request):
    """Создает нового обычного пользователя (роль USER)"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав для создания пользователей'}, status=403)

    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return JsonResponse({'error': 'Логин и пароль обязательны'}, status=400)

        user = User.objects.create_user(username=username, password=password)
        
        return JsonResponse({'status': 'success', 'message': f'Пользователь {username} успешно создан!'})

    except IntegrityError:
        return JsonResponse({'error': 'Пользователь с таким логином уже существует'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
@require_POST
def create_tournament_api(request):
    """Создание нового турнира суперадмином"""
    if request.user.role != User.Role.SUPERADMIN and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        password = data.get('password')
        number = data.get('number')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        user = authenticate(username=request.user.username, password=password)
        if user is None:
            return JsonResponse({'error': 'Неверный пароль'}, status=403)

        Tournament.objects.all().delete()

        Tournament.objects.create(
            tournament_number=number,
            start_date=start_date,
            end_date=end_date
        )
        return JsonResponse({'status': 'success', 'message': 'Новый турнир успешно создан!'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def add_team_api(request):
    """Добавление новой команды"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'error': 'Сначала создайте турнир!'}, status=400)

    try:
        data = json.loads(request.body)
        
        Team.objects.create(
            tournament=current_tournament,
            work_name=data.get('work_name'),
            child_name=data.get('child_name'),
            school_class=int(data.get('school_class')),
            league=data.get('league', ''),
            players_quantity='6', # По умолчанию
            current_points=0
        )
        return JsonResponse({'status': 'success', 'message': 'Команда добавлена!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
@require_GET
def get_teams_api(request):
    """Возвращает список команд текущего турнира"""
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    if not current_tournament:
        return JsonResponse({'teams': []})

    teams = Team.objects.filter(tournament=current_tournament).order_by('school_class', 'league', 'child_name')
    
    data = []
    for t in teams:
        data.append({
            'id': t.id,
            'work_name': t.work_name,
            'child_name': t.child_name,
            'school_class': t.school_class,
            'league': t.league if t.league else '—'
        })
        
    return JsonResponse({'teams': data})

@login_required
@require_POST
def delete_team_api(request):
    """Удаление команды по ID"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        Team.objects.filter(id=team_id).delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def upload_teams_csv_api(request):
    """Парсинг и загрузка команд из CSV файла"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'error': 'Сначала создайте турнир!'}, status=400)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['file']
    
    try:
        decoded_file = file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        
        reader = csv.reader(io_string, delimiter=';')
        
        count = 0
        for row in reader:
            if not row or len(row) < 3:
                # Если парсинг с ; не удался, пробуем с запятой для этой строки
                row = [item.strip() for item in row[0].split(',')] if row else []
                if len(row) < 3: continue

            work_name = row[0].strip()
            child_name = row[1].strip()
            school_class_str = row[2].strip()
            league = row[3].strip() if len(row) > 3 else ''

            if work_name and child_name and school_class_str.isdigit():
                Team.objects.create(
                    tournament=current_tournament,
                    work_name=work_name,
                    child_name=child_name,
                    school_class=int(school_class_str),
                    league=league,
                    players_quantity='6',
                    current_points=0
                )
                count += 1
                
        return JsonResponse({'status': 'success', 'message': f'Успешно загружено команд: {count}'})
    except Exception as e:
        return JsonResponse({'error': f'Ошибка обработки файла: {str(e)}'}, status=500)
    

@login_required
@require_GET
def get_teams_for_select_api(request):
    """Отдает список команд для выпадающих списков (зависит от класса и лиги)"""
    school_class = request.GET.get('school_class')
    league = request.GET.get('league', '')
    
    if not school_class:
        return JsonResponse({'teams': []})
        
    teams = Team.objects.filter(school_class=school_class, league=league).order_by('child_name')
    data = [{'id': t.id, 'name': t.child_name} for t in teams]
    return JsonResponse({'teams': data})

@login_required
@require_POST
def add_fight_api(request):
    """Добавление результата боя и обновление очков команд"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        team1 = Team.objects.get(id=data.get('team1_id'))
        team2 = Team.objects.get(id=data.get('team2_id'))
        points1 = int(data.get('points1', 0))
        points2 = int(data.get('points2', 0))
        tour = int(data.get('tour', 1))

        if team1.id == team2.id:
            return JsonResponse({'error': 'Команда не может играть сама с собой!'}, status=400)

        # Создаем запись о бое
        Fight.objects.create(
            team_one=team1,
            team_two=team2,
            team_one_points=points1,
            team_two_points=points2,
            tour_number=tour,
            place='Не указано',
            value_day=timezone.now().date(),
            ended=True
        )

        if points1 > points2 + 3:
            team1.current_points += 2
        elif points1 + 3 < points2:
            team2.current_points += 2
        else:
            team1.current_points += 1
            team2.current_points += 1

        team1.save()
        team2.save()
        return JsonResponse({'status': 'success', 'message': 'Результат сохранен!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_GET
def get_fights_list_api(request):
    """Возвращает список всех завершенных боев для таблицы в модалке"""
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'fights': []})

    fights = Fight.objects.filter(team_one__tournament=current_tournament, ended=True).order_by('-id')
    
    data = []
    for f in fights:
        data.append({
            'id': f.id,
            'class': f.team_one.school_class,
            'tour': f.tour_number,
            'match_name': f"{f.team_one.child_name} vs {f.team_two.child_name}",
            'score': f"{f.team_one_points} : {f.team_two_points}"
        })
    return JsonResponse({'fights': data})


@login_required
@require_GET
def get_scheduled_fights_api(request):
    """Возвращает список запланированных (неоконченных) боев для модалки расписания"""
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'fights': []})

    fights = Fight.objects.filter(team_one__tournament=current_tournament, ended=False).order_by('-id')
    
    data = []
    for f in fights:
        data.append({
            'id': f.id,
            'class': f.team_one.school_class,
            'tour': f.tour_number,
            'match_name': f"{f.team_one.child_name} vs {f.team_two.child_name}",
            'time_place': f"{f.place} ({f.fight_time.strftime('%H:%M')})"
        })
    return JsonResponse({'fights': data})

@login_required
@require_POST
def remove_fight_result_api(request):
    """Удаляет ТОЛЬКО результат боя, откатывает очки и делает его неоконченным"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        fight = Fight.objects.get(id=data.get('fight_id'))
        
        # Если бой был завершен, откатываем баллы по правилу "отрыв > 3"
        if fight.ended and fight.team_one_points is not None and fight.team_two_points is not None:
            if fight.team_one_points > fight.team_two_points + 3:
                fight.team_one.current_points -= 2
            elif fight.team_one_points + 3 < fight.team_two_points:
                fight.team_two.current_points -= 2
            else:
                fight.team_one.current_points -= 1
                fight.team_two.current_points -= 1
                
            fight.team_one.save()
            fight.team_two.save()
            
        # Затираем счет и меняем статус, но сам бой не удаляем
        fight.team_one_points = None
        fight.team_two_points = None
        fight.ended = False
        fight.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def delete_fight_api(request):
    """ПОЛНОЕ УДАЛЕНИЕ боя из базы (из расписания)"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        fight = Fight.objects.get(id=data.get('fight_id'))
        
        # Если удаляют уже завершенный бой, сначала откатываем очки
        if fight.ended and fight.team_one_points is not None and fight.team_two_points is not None:
            if fight.team_one_points > fight.team_two_points + 3:
                fight.team_one.current_points -= 2
            elif fight.team_one_points + 3 < fight.team_two_points:
                fight.team_two.current_points -= 2
            else:
                fight.team_one.current_points -= 1
                fight.team_two.current_points -= 1
            fight.team_one.save()
            fight.team_two.save()
            
        fight.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
@require_POST
def edit_team_api(request):
    """Сохранение отредактированных данных команды"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        team = Team.objects.get(id=data.get('team_id'))
        
        # Обновляем поля
        team.work_name = data.get('work_name', team.work_name)
        team.child_name = data.get('child_name', team.child_name)
        team.school_class = int(data.get('school_class', team.school_class))
        
        # Обрабатываем лигу (если передали пустую строку, сохраняем как пустую)
        league_val = data.get('league', '')
        team.league = league_val if league_val and league_val != '—' else ''
        
        team.save()
        return JsonResponse({'status': 'success', 'message': 'Команда обновлена!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_GET
def get_leagues_api(request):
    """Возвращает список уникальных лиг для выбранного класса"""
    school_class = request.GET.get('school_class')
    if not school_class:
        return JsonResponse({'leagues': []})
        
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    # Ищем все уникальные непустые лиги для этого класса в текущем турнире
    leagues = Team.objects.filter(
        tournament=current_tournament, 
        school_class=school_class
    ).exclude(league='').values_list('league', flat=True).distinct()
    
    return JsonResponse({'leagues': list(leagues)})

@require_GET
def get_class_summary_api(request):
    """Возвращает данные для отрисовки шахматок выбранного класса"""
    school_class = request.GET.get('school_class')
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    if not current_tournament or not school_class:
        return JsonResponse({'leagues': []})
        
    # Ищем все уникальные лиги в этом классе (отбрасываем пустые)
    leagues_names = Team.objects.filter(
        tournament=current_tournament, 
        school_class=school_class
    ).exclude(league='').values_list('league', flat=True).distinct()
    
    # Добавляем обработку для команд, у которых не указана лига
    has_no_league = Team.objects.filter(tournament=current_tournament, school_class=school_class, league='').exists()
    leagues_list = list(leagues_names)
    if has_no_league:
        leagues_list.append('')
        
    data = []
    for league in leagues_list:
        teams = Team.objects.filter(
            tournament=current_tournament, 
            school_class=school_class, 
            league=league
        ).order_by('-current_points', 'child_name')
        
        teams_data = []
        for idx, t in enumerate(teams, start=1):
            teams_data.append({
                'id': t.id,
                'num': idx,
                'name': t.child_name,
                'points': t.current_points
            })
        
        team_ids = [t['id'] for t in teams_data]
        fights = Fight.objects.filter(team_one__id__in=team_ids, team_two__id__in=team_ids, ended=True)
        
        matches_data = []
        for f in fights:
            matches_data.append({
                't1_id': f.team_one.id,
                't2_id': f.team_two.id,
                'score1': f.team_one_points,
                'score2': f.team_two_points
            })
            
        league_title = league if league else "Без лиги"
        data.append({
            'name': league_title,
            'teams': teams_data,
            'matches': matches_data
        })
        
    return JsonResponse({'leagues': data})


@login_required
@require_POST
def save_olympiad_api(request):
    """Сохранение результатов командной олимпиады (плюсы и минусы)"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        team = Team.objects.get(id=data.get('team_id'))
        
        Olympiad.objects.update_or_create(
            team=team,
            defaults={
                'plus_count': int(data.get('plus_count', 0)),
                'minus_count': int(data.get('minus_count', 0))
            }
        )
        return JsonResponse({'status': 'success', 'message': 'Результат Комола сохранен!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def get_olympiad_api(request):
    """Возвращает таблицу результатов олимпиады"""
    school_class = request.GET.get('school_class')
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    if not current_tournament or not school_class:
        return JsonResponse({'teams': []})
        
    teams = Team.objects.filter(tournament=current_tournament, school_class=school_class)
    
    data = []
    for t in teams:
        try:
            res = t.olympiad
            plus = res.plus_count
            minus = res.minus_count
        except Olympiad.DoesNotExist:
            plus = 0
            minus = 0
            
        data.append({
            'team_id': t.id,
            'name': t.child_name,
            'league': t.league,
            'plus_count': plus,
            'minus_count': minus
        })
    
    # Сортировка: больше плюсов (по убыванию), затем меньше минусов (по возрастанию), затем по алфавиту
    data.sort(key=lambda x: (-x['plus_count'], x['minus_count'], x['name']))
    return JsonResponse({'teams': data})


@login_required
@require_POST
def schedule_fight_api(request):
    """Добавление боя в расписание (без результатов)"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        t1 = Team.objects.get(id=data.get('team1_id'))
        t2 = Team.objects.get(id=data.get('team2_id'))
        
        if t1.id == t2.id:
            return JsonResponse({'error': 'Команда не может играть сама с собой!'}, status=400)

        Fight.objects.create(
            team_one=t1,
            team_two=t2,
            tour_number=int(data.get('tour')),
            judge_first=data.get('judge_first'),
            judge_second=data.get('judge_second', ''),
            place=data.get('place'),
            solution_place=data.get('solution_place'),
            value_day=data.get('value_day'),
            fight_time=data.get('fight_time'),
            solution_ts=data.get('solution_time'),
            ended=False
        )
        return JsonResponse({'status': 'success', 'message': 'Бой добавлен в расписание!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def add_fight_result_api(request):
    """Внесение результатов в уже существующий в расписании бой"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        t1 = Team.objects.get(id=data.get('team1_id'))
        t2 = Team.objects.get(id=data.get('team2_id'))
        p1 = int(data.get('points1', 0))
        p2 = int(data.get('points2', 0))
        tour = int(data.get('tour', 0)) 

        fight = Fight.objects.filter(
            Q(team_one=t1, team_two=t2) | Q(team_one=t2, team_two=t1),
            tour_number=tour, 
            ended=False
        ).first()

        if not fight:
            return JsonResponse({'error': 'Согласно расписанию такого боя в этом туре не было (или он уже завершен)!'}, status=400)

        if fight.team_one == t1:
            fight.team_one_points = p1
            fight.team_two_points = p2
        else:
            fight.team_one_points = p2
            fight.team_two_points = p1

        fight.ended = True
        fight.save()

        if p1 > p2 + 3:
            t1.current_points += 2
        elif p1 + 3 < p2:
            t2.current_points += 2
        else:
            t1.current_points += 1
            t2.current_points += 1

        t1.save()
        t2.save()

        return JsonResponse({'status': 'success', 'message': 'Счет успешно добавлен!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def get_schedule_api(request):
    """Возвращает расписание боев для максимального тура выбранного класса"""
    school_class = request.GET.get('school_class')
    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    
    if not current_tournament or not school_class:
        return JsonResponse({'schedule': []})

    max_tour_dict = Fight.objects.filter(
        team_one__tournament=current_tournament,
        team_one__school_class=school_class
    ).aggregate(Max('tour_number'))
    
    max_tour = max_tour_dict['tour_number__max']
    
    if not max_tour:
        return JsonResponse({'schedule': []})

    fights = Fight.objects.filter(
        team_one__tournament=current_tournament,
        team_one__school_class=school_class,
        tour_number=max_tour
    ).order_by('team_one__league', 'fight_time')

    data = []
    for f in fights:
        score_str = f"{f.team_one_points}:{f.team_two_points}" if f.ended else '<i style="color:gray;">Не окончен</i>'
        
        data.append({
            'tour': f.tour_number,
            'league': f.team_one.league,
            'teams': f"{f.team_one.child_name} — {f.team_two.child_name}",
            'j1': f.judge_first,
            'j2': f.judge_second,
            'fight_place': f"{f.place}<br><small>{f.value_day.strftime('%d.%m.%Y')} {f.fight_time.strftime('%H:%M')}</small>",
            'sol_place': f"{f.solution_place}<br><small>{f.value_day.strftime('%d.%m.%Y')} {f.solution_ts.strftime('%H:%M')}</small>",
            'score': score_str
        })
        
    return JsonResponse({'schedule': data})

@login_required
@require_POST
def upload_schedule_csv_api(request):
    """Парсинг и загрузка расписания из CSV файла"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'error': 'Сначала создайте турнир!'}, status=400)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['file']
    
    try:
        decoded_file = file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        reader = csv.reader(io_string, delimiter=';') # Ожидаем ; от Excel
        
        count = 0
        errors = []
        
        for idx, row in enumerate(reader, start=1):
            if not row or len(row) < 10:
                # Если не разбилось по точке с запятой, пробуем запятую
                row = [item.strip() for item in row[0].split(',')] if row else []
                if len(row) < 10: continue

            # Парсим колонки согласно форме
            # Ожидаемый формат:
            # 0: Класс, 1: Лига, 2: Тур, 3: Дата (YYYY-MM-DD), 4: Команда 1, 5: Команда 2
            # 6: Судья 1, 7: Судья 2, 8: Место, 9: Время, 10: Место разбора, 11: Время разбора
            
            tour = row[2].strip()
            date_val = row[3].strip()
            t1_name = row[4].strip()
            t2_name = row[5].strip()
            j1 = row[6].strip()
            j2 = row[7].strip()
            place = row[8].strip()
            fight_time = row[9].strip()
            
            sol_place = row[10].strip() if len(row) > 10 and row[10].strip() else place
            sol_time = row[11].strip() if len(row) > 11 and row[11].strip() else fight_time

            t1 = Team.objects.filter(tournament=current_tournament, child_name__iexact=t1_name).first()
            t2 = Team.objects.filter(tournament=current_tournament, child_name__iexact=t2_name).first()

            if not t1 or not t2:
                errors.append(f"Строка {idx}: Команды '{t1_name}' или '{t2_name}' не найдены в базе.")
                continue

            Fight.objects.create(
                team_one=t1,
                team_two=t2,
                tour_number=int(tour) if tour.isdigit() else 1,
                value_day=date_val,
                fight_time=fight_time,
                judge_first=j1,
                judge_second=j2,
                place=place,
                solution_place=sol_place,
                solution_ts=sol_time,
                ended=False
            )
            count += 1
                
        msg = f'Успешно запланировано боев: {count}.'
        if errors:
            msg += f' Ошибок: {len(errors)} (например: {errors[0]})'
            
        return JsonResponse({'status': 'success', 'message': msg})
    except Exception as e:
        return JsonResponse({'error': f'Ошибка обработки файла: {str(e)}'}, status=500)
    
@login_required
@require_POST
def upload_olympiad_csv_api(request):
    """Массовая загрузка результатов Комола из CSV"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'error': 'Сначала создайте турнир!'}, status=400)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['file']
    try:
        decoded_file = file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        reader = csv.reader(io_string, delimiter=';')
        
        count = 0
        for row in reader:
            if not row or len(row) < 4:
                row = [item.strip() for item in row[0].split(',')] if row else []
                if len(row) < 4: continue

            s_class = row[0].strip()
            t_name = row[2].strip()
            plus = row[3].strip()
            minus = row[4].strip() if len(row) > 4 else "0"

            team = Team.objects.filter(
                tournament=current_tournament, 
                school_class=s_class, 
                child_name__iexact=t_name
            ).first()

            if team:
                Olympiad.objects.update_or_create(
                    team=team,
                    defaults={
                        'plus_count': int(plus) if plus.isdigit() else 0,
                        'minus_count': int(minus) if minus.isdigit() else 0
                    }
                )
                count += 1
                
        return JsonResponse({'status': 'success', 'message': f'Обновлено результатов: {count}'})
    except Exception as e:
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)
    

@login_required
@require_POST
def upload_matches_csv_api(request):
    """Массовая загрузка результатов завершенных боев из CSV"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['file']
    try:
        decoded_file = file.read().decode('utf-8-sig')
        reader = csv.reader(io.StringIO(decoded_file), delimiter=';')
        
        count = 0
        for row in reader:
            if not row or len(row) < 7:
                row = [item.strip() for item in row[0].split(',')] if row else []
                if len(row) < 7: continue

            tour = row[2].strip()
            t1_name = row[3].strip()
            score1 = row[4].strip()
            t2_name = row[5].strip()
            score2 = row[6].strip()

            t1 = Team.objects.filter(tournament=current_tournament, child_name__iexact=t1_name).first()
            t2 = Team.objects.filter(tournament=current_tournament, child_name__iexact=t2_name).first()

            if t1 and t2:
                fight = Fight.objects.filter(
                    Q(team_one=t1, team_two=t2) | Q(team_one=t2, team_two=t1),
                    tour_number=int(tour) if tour.isdigit() else 1
                ).first()

                if not fight:
                    fight = Fight(team_one=t1, team_two=t2, tour_number=int(tour) if tour.isdigit() else 1)

                if fight.team_one == t1:
                    fight.score_one = float(score1.replace(',', '.')) if score1 else 0.0
                    fight.score_two = float(score2.replace(',', '.')) if score2 else 0.0
                else:
                    fight.score_one = float(score2.replace(',', '.')) if score2 else 0.0
                    fight.score_two = float(score1.replace(',', '.')) if score1 else 0.0
                    
                fight.ended = True
                fight.save()
                count += 1
                
        return JsonResponse({'status': 'success', 'message': f'Загружено результатов боев: {count}'})
    except Exception as e:
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)


@login_required
def export_csv_api(request, export_type):
    """Универсальная выгрузка таблиц в CSV"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN, User.Role.EDITOR] and not request.user.is_superuser:
        return HttpResponse('Доступ запрещен', status=403)
        
    tournament = Tournament.objects.order_by('-tournament_number').first()
    response = HttpResponse(content_type='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename="{export_type}.csv"'
    
    response.write('\ufeff'.encode('utf8')) 
    writer = csv.writer(response, delimiter=';')
    
    if export_type == 'teams':
        writer.writerow(['Рабочее название', 'Детское название', 'Класс', 'Лига'])
        for t in Team.objects.filter(tournament=tournament):
            writer.writerow([t.work_name, t.child_name, t.school_class, t.league])
            
    elif export_type == 'olympiad':
        writer.writerow(['Класс', 'Лига', 'Команда', 'Плюсы', 'Минусы'])
        for o in Olympiad.objects.filter(team__tournament=tournament):
            writer.writerow([o.team.school_class, o.team.league, o.team.child_name, o.plus_count, o.minus_count])
            
    elif export_type == 'schedule':
        writer.writerow(['Класс', 'Лига', 'Тур', 'Дата', 'Команда 1', 'Команда 2', 'Судья 1', 'Судья 2', 'Место', 'Время', 'Место разбора', 'Время разбора'])
        for f in Fight.objects.filter(team_one__tournament=tournament):
            writer.writerow([f.team_one.school_class, f.team_one.league, f.tour_number, f.value_day, f.team_one.child_name, f.team_two.child_name, f.judge_first, f.judge_second, f.place, f.fight_time, f.solution_place, f.solution_ts])
            
    elif export_type == 'matches':
        writer.writerow(['Класс', 'Лига', 'Тур', 'Команда 1', 'Баллы 1', 'Команда 2', 'Баллы 2'])
        for f in Fight.objects.filter(team_one__tournament=tournament, ended=True):
            writer.writerow([f.team_one.school_class, f.team_one.league, f.tour_number, f.team_one.child_name, f.score_one, f.team_two.child_name, f.score_two])
            
    return response

@login_required
@require_POST
def upload_tournament_doc_api(request, doc_type):
    """Загрузка документов (свод правил или информационное письмо)"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'error': 'Сначала создайте турнир!'}, status=400)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['file']
    
    try:
        if doc_type == 'rules':
            current_tournament.rules_file = file
        elif doc_type == 'info_letter':
            current_tournament.info_letter_file = file
        else:
            return JsonResponse({'error': 'Неизвестный тип документа'}, status=400)
            
        current_tournament.save()
        return JsonResponse({'status': 'success', 'message': 'Документ успешно загружен!'})
    except Exception as e:
        return JsonResponse({'error': f'Ошибка загрузки файла: {str(e)}'}, status=500)

@login_required
@require_POST
def add_faq_api(request):
    """Добавление ответа на частый вопрос (ЧаВО)"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    current_tournament = Tournament.objects.order_by('-tournament_number').first()
    if not current_tournament:
        return JsonResponse({'error': 'Сначала создайте турнир!'}, status=400)

    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not question or not answer:
            return JsonResponse({'error': 'Вопрос и ответ не могут быть пустыми'}, status=400)
            
        FAQ.objects.create(tournament=current_tournament, question=question, answer=answer)
        return JsonResponse({'status': 'success', 'message': 'Вопрос добавлен!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def delete_faq_api(request):
    """Удаление вопроса из ЧаВО"""
    if request.user.role not in [User.Role.ADMIN, User.Role.SUPERADMIN] and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    try:
        data = json.loads(request.body)
        FAQ.objects.filter(id=data.get('faq_id')).delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)