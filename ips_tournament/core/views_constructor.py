import csv
import io
import copy
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from collections import defaultdict

from .constructor.switz import SwitzTournamentSystem
from .constructor.round_robin import RoundRobinTournamentSystem
from .constructor.python_parser import FromPythonCode

# Список доступных систем
TOURNAMENTS = [SwitzTournamentSystem, RoundRobinTournamentSystem]

@require_GET
def get_tournaments_api(request):
    """Отдает список турниров для dropdown-меню на фронтенде"""
    data = [{"id": idx, "name": t.name} for idx, t in enumerate(TOURNAMENTS)]
    return JsonResponse(data, safe=False)

def parse_constructor_files(teams_file, oly_file, matches_file=None):
    """Парсит файлы и строго проверяет соответствие составов команд."""
    teams_dict = {}  
    leagues_dict = defaultdict(int)
    match_history = []
    ignored_matches = 0

    # 1. Парсим Команды
    raw_teams = teams_file.read()
    try:
        decoded_teams = raw_teams.decode('utf-8-sig')
    except UnicodeDecodeError:
        decoded_teams = raw_teams.decode('windows-1251')
    
    reader = csv.reader(io.StringIO(decoded_teams), delimiter=';')
    next(reader, None)
    for row in reader:
        if len(row) >= 4:
            name, league = row[1].strip(), row[3].strip()
            if name:
                teams_dict[name] = [0, 0, 0, league]
                leagues_dict[league] += 1

    # 2. Парсим Олимпиаду + Проверяем составы команд. На всякий случай добавляем проверку кодировки, так как файл может быть сохранен по-разному
    raw_oly = oly_file.read()
    try:
        decoded_oly = raw_oly.decode('utf-8-sig')
    except UnicodeDecodeError:
        decoded_oly = raw_oly.decode('windows-1251')
    
    reader = csv.reader(io.StringIO(decoded_oly), delimiter=';')
    next(reader, None)
    
    oly_teams = set()
    for row in reader:
        if len(row) >= 5:
            name = row[2].strip()
            if not name: continue
            
            if name not in teams_dict:
                raise ValueError(f"Ошибка в файле олимпиады: команда '{name}' не найдена в основном списке команд!")
            
            teams_dict[name][0] = int(row[3].strip() or 0) # Плюсы
            teams_dict[name][1] = int(row[4].strip() or 0) # Минусы
            oly_teams.add(name)

    # Проверка: все ли команды из основного списка есть в олимпиаде?
    main_teams_set = set(teams_dict.keys())
    missing_in_oly = main_teams_set - oly_teams
    if missing_in_oly:
        raise ValueError(f"В файле олимпиады отсутствуют команды из основного списка: {', '.join(missing_in_oly)}")

    # 3. Парсим прошедшие бои (если есть)
    if matches_file:
        raw_matches = matches_file.read()
        try:
            decoded_matches = raw_matches.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded_matches = raw_matches.decode('windows-1251')
            
        reader = csv.reader(io.StringIO(decoded_matches), delimiter=';')
        next(reader, None)
        for row in reader:
            if len(row) >= 7:
                tour = int(row[2].strip()) if row[2].strip().isdigit() else 1
                t1, t2 = row[3].strip(), row[5].strip()
                s1_str, s2_str = row[4].strip(), row[6].strip()

                if not s1_str or not s2_str:
                    ignored_matches += 1
                    continue

                if t1 not in teams_dict or t2 not in teams_dict:
                    # Тут просто логируем или игнорируем, так как это история
                    continue

                s1, s2 = float(s1_str.replace(',', '.')), float(s2_str.replace(',', '.'))
                if s1 > s2:
                    result, p1_add, p2_add = 1, 2, 0
                elif s1 < s2:
                    result, p1_add, p2_add = -1, 0, 2
                else:
                    result, p1_add, p2_add = 0, 1, 1

                match_history.append((t1, t2, result, tour))
                teams_dict[t1][2] += p1_add
                teams_dict[t2][2] += p2_add

    return teams_dict, dict(leagues_dict), match_history, ignored_matches

@require_POST
def run_simulation_api(request):
    """Запускает метод Монте-Карло"""
    try:
        t_id = int(request.POST.get('tournament_id', 0))
        sim_count = min(int(request.POST.get('sim_count', 10)), 100)
        code = request.POST.get('code', '')
        
        TournamentClass = TOURNAMENTS[t_id]
        win_func = FromPythonCode(code)

        # Парсим файлы (matches забираем через get, так как он может быть None)
        base_teams, leagues, base_history, ignored = parse_constructor_files(
            request.FILES['teams'], 
            request.FILES['olympiad'], 
            request.FILES.get('matches')
        )

        temp_tournament = TournamentClass(base_teams, leagues, win_func)
        total_tours_dict = temp_tournament.get_total_tours()
        calculated_max = max(total_tours_dict.values()) if total_tours_dict else 0

        # Если с фронта пришло число - берем его, иначе берем подсчитанное (или 0)
        max_tours_str = request.POST.get('max_tours', '')
        max_tours = int(max_tours_str) if max_tours_str.isdigit() and int(max_tours_str) > 0 else calculated_max

        stats = {team: {'places': [], 'points': [], 'league': data[3]} for team, data in base_teams.items()}
        current_tour = max([m[3] for m in base_history], default=0)

        for _ in range(sim_count):
            sim_teams = copy.deepcopy(base_teams)
            sim_history = copy.deepcopy(base_history)
            
            tournament = TournamentClass(sim_teams, leagues, win_func)
            tournament.match_history = sim_history
            tournament.tour_counter = current_tour
            
            # Крутим цикл ровно до указанного количества туров
            while tournament.tour_counter < max_tours:
                try:
                    pairs = tournament.generate_next_tour()
                    if not pairs: 
                        break
                    tournament.simulate_tour(pairs)
                except Exception:
                    break # Если зашли в тупик жеребьевки, обрываем конкретно эту ветку симуляции

            # Снимаем итоговые места после завершения симуляции
            ladder = tournament.count_ladder()
            for league_name, standings in ladder.items():
                for team_name, pts, place in standings:
                    stats[team_name]['places'].append(place)
                    stats[team_name]['points'].append(pts)

        # Считаем средние значения
        results_list = []
        for team, data in stats.items():
            avg_place = sum(data['places']) / len(data['places']) if data['places'] else 0
            avg_pts = sum(data['points']) / len(data['points']) if data['points'] else 0
            results_list.append({
                'team': team, 
                'league': data['league'], 
                'avg_place': round(avg_place, 2), 
                'avg_pts': round(avg_pts, 2)
            })

        # Сортируем: сначала по лиге, затем по среднему месту
        results_list.sort(key=lambda x: (x['league'], x['avg_place']))

        return JsonResponse({
            'status': 'success', 
            'results': results_list, 
            'ignored_matches': ignored
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    

@require_POST
def generate_pairing_api(request):
    """Выдает CSV файл с жеребьевкой следующего тура"""
    try:
        t_id = int(request.POST.get('tournament_id', 0))
        code = request.POST.get('code', '')
        
        TournamentClass = TOURNAMENTS[t_id]
        win_func = FromPythonCode(code)

        base_teams, leagues, base_history, ignored = parse_constructor_files(
            request.FILES['teams'], request.FILES['olympiad'], request.FILES.get('matches')
        )
        
        tournament = TournamentClass(base_teams, leagues, win_func)
        tournament.match_history = base_history
        tournament.tour_counter = max([m[3] for m in base_history], default=0)
        
        pairs = tournament.generate_next_tour()
        
        response = HttpResponse(content_type='text/csv')
        response.headers['Content-Disposition'] = 'attachment; filename="next_tour.csv"'
        response.write('\ufeff'.encode('utf8')) 
        writer = csv.writer(response, delimiter=';')
        
        writer.writerow(['Лига', 'Тур', 'Команда 1', 'Команда 2'])
        next_tour_num = tournament.tour_counter + 1
        
        for t1, t2 in pairs:
            league = base_teams[t1][3]
            writer.writerow([league, next_tour_num, t1, t2])
            
        return response
    except Exception as e:
        return HttpResponse(f'Ошибка генерации: {str(e)}', status=400)
    
@require_POST
def calculate_tours_api(request):
    """Спрашивает у класса турнира дефолтное количество туров"""
    try:
        t_id = int(request.POST.get('tournament_id', 0))
        teams_file = request.FILES.get('teams')
        
        if not teams_file:
            return JsonResponse({'tours': 0}) # Нет файла - ноль туров

        leagues_dict = defaultdict(int)
        reader = csv.reader(io.StringIO(teams_file.read().decode('utf-8-sig')), delimiter=';')
        next(reader, None)
        for row in reader:
            if len(row) >= 4:
                league = row[3].strip()
                leagues_dict[league] += 1

        TournamentClass = TOURNAMENTS[t_id]
        tournament = TournamentClass(teams={}, leagues=dict(leagues_dict), win_function=None)
        
        total_tours_dict = tournament.get_total_tours()
        # Если словарь не пустой, берем максимум, иначе ноль
        calculated_max = max(total_tours_dict.values()) if total_tours_dict else 0

        return JsonResponse({'tours': calculated_max})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)