from functools import cmp_to_key
from typing import List, Tuple, Dict
from .abstract import BaseTournamentSystem, PairingError
import math

class SwitzTournamentSystem(BaseTournamentSystem):

    name = "Швейцарская система"

    def __str__(self) -> str:
        return "Швейцарская система"
    
    def get_total_tours(self) -> Dict[str, int]:
        """Классическая швейцарка: потолок от логарифма по основанию 2 от числа команд"""
        res = {}
        for league, count in self.leagues.items():
            res[league] = math.ceil(math.log2(count)) if count > 0 else 0
        return res
    
    def _have_played(self, t1: str, t2: str) -> bool:
        """Проверяет, играли ли уже эти две команды"""
        for match in self.match_history:
            if (match[0] == t1 and match[1] == t2) or (match[0] == t2 and match[1] == t1):
                return True
        return False

    def _get_opponents(self, team: str) -> List[str]:
        """Возвращает список всех соперников, с которыми играла команда"""
        opponents = []
        for match in self.match_history:
            if match[0] == team:
                opponents.append(match[1])
            elif match[1] == team:
                opponents.append(match[0])
        return opponents

    def _head_to_head_score(self, t1: str, t2: str) -> int:
        """Считает очки, которые t1 заработала в играх против t2"""
        score = 0
        for match in self.match_history:
            if match[0] == t1 and match[1] == t2:
                if match[2] == 1: score += 2
                elif match[2] == 0: score += 1
            elif match[0] == t2 and match[1] == t1:
                if match[2] == -1: score += 2
                elif match[2] == 0: score += 1
        return score

    def _get_buchholz(self, team: str) -> int:
        """Считает коэффициент Бухгольца (сумма очков всех соперников)"""
        return sum(self.teams[opp][2] for opp in self._get_opponents(team))

    def _get_ladder_for_league(self, league: str) -> List[Tuple[str, int, int]]:
        """Формирует турнирную таблицу для конкретной лиги"""
        league_teams = [t for t, data in self.teams.items() if data[3] == league]
        
        def compare(t1: str, t2: str) -> int:
            pts1 = self.teams[t1][2]
            pts2 = self.teams[t2][2]
            if pts1 != pts2:
                return pts2 - pts1
            
            h2h_1 = self._head_to_head_score(t1, t2)
            h2h_2 = self._head_to_head_score(t2, t1)
            if h2h_1 != h2h_2:
                return h2h_2 - h2h_1
            
            bhz1 = self._get_buchholz(t1)
            bhz2 = self._get_buchholz(t2)
            if bhz1 != bhz2:
                return bhz2 - bhz1
                
            return 0 

        sorted_teams = sorted(league_teams, key=cmp_to_key(compare))
        return [(t, self.teams[t][2], idx + 1) for idx, t in enumerate(sorted_teams)]

    def count_ladder(self) -> Dict[str, List[Tuple[str, int, int]]]:
        """Считает порядок мест во всех лигах"""
        ladder = {}
        for league in self.leagues:
            ladder[league] = self._get_ladder_for_league(league)
        return ladder

    def generate_next_tour(self) -> List[Tuple[str, str]]:
        """Генерирует расписание по швейцарской системе"""
        upcoming_matches = []
        is_first_tour = len(self.match_history) == 0

        # === ЛОГИКА ПЕРВОГО ТУРА ===
        if is_first_tour:
            for league in self.leagues:
                league_teams = [t for t, data in self.teams.items() if data[3] == league]
                league_teams.sort(key=lambda t: (self.teams[t][0] - self.teams[t][1], self.teams[t][0]), reverse=True)
                
                half = len(league_teams) // 2
                top_half = league_teams[:half]
                bottom_half = league_teams[half:]

                for i in range(half):
                    upcoming_matches.append((top_half[i], bottom_half[i]))
                    
            return upcoming_matches

        # === ЛОГИКА ПОСЛЕДУЮЩИХ ТУРОВ ===
        ladder = self.count_ladder()

        for league, standings in ladder.items():
            sorted_teams = [t[0] for t in standings]
            paired = set()

            for i in range(len(sorted_teams)):
                t1 = sorted_teams[i]
                if t1 in paired:
                    continue
                
                match_found = False
                for j in range(i + 1, len(sorted_teams)):
                    t2 = sorted_teams[j]
                    if t2 not in paired and not self._have_played(t1, t2):
                        upcoming_matches.append((t1, t2))
                        paired.add(t1)
                        paired.add(t2)
                        match_found = True
                        break
                
                if not match_found:
                    raise PairingError(
                        f"Ошибка жеребьевки в лиге '{league}': невозможно подобрать соперника для команды '{t1}'. "
                        f"Все доступные варианты уже сыграны."
                    )
                            
        return upcoming_matches