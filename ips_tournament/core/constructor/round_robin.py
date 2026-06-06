from functools import cmp_to_key
from typing import List, Tuple, Dict
from .abstract import BaseTournamentSystem, PairingError

class RoundRobinTournamentSystem(BaseTournamentSystem):

    name = "Круговая система"

    def __str__(self) -> str:
        return "Круговая система"
    
    def get_total_tours(self) -> Dict[str, int]:
        """N-1 туров при четном количестве команд, N туров при нечетном"""
        res = {}
        for league, count in self.leagues.items():
            if count <= 1:
                res[league] = 0
            elif count % 2 == 0:
                res[league] = count - 1
            else:
                res[league] = count
        return res
    
    def _head_to_head_score(self, t1: str, t2: str) -> int:
        score = 0
        for m in self.match_history:
            if m[0] == t1 and m[1] == t2:
                if m[2] == 1: score += 2
                elif m[2] == 0: score += 1
            elif m[0] == t2 and m[1] == t1:
                if m[2] == -1: score += 2
                elif m[2] == 0: score += 1
        return score

    def _get_ladder_for_league(self, league: str) -> List[Tuple[str, int, int]]:
        league_teams = [t for t, data in self.teams.items() if data[3] == league]
        
        def compare(t1: str, t2: str) -> int:
            pts1, pts2 = self.teams[t1][2], self.teams[t2][2]
            if pts1 != pts2:
                return pts2 - pts1
            
            h2h_1, h2h_2 = self._head_to_head_score(t1, t2), self._head_to_head_score(t2, t1)
            if h2h_1 != h2h_2:
                return h2h_2 - h2h_1
            
            diff1 = self.teams[t1][0] - self.teams[t1][1]
            diff2 = self.teams[t2][0] - self.teams[t2][1]
            return diff2 - diff1

        sorted_teams = sorted(league_teams, key=cmp_to_key(compare))
        return [(t, self.teams[t][2], idx + 1) for idx, t in enumerate(sorted_teams)]

    def count_ladder(self) -> Dict[str, List[Tuple[str, int, int]]]:
        return {league: self._get_ladder_for_league(league) for league in self.leagues}

    def generate_next_tour(self) -> List[Tuple[str, str]]:
        upcoming_matches = []
        
        for league, count in self.leagues.items():
            league_teams = sorted([t for t, data in self.teams.items() if data[3] == league])
            n = len(league_teams)
            
            max_tours = n - 1 if n % 2 == 0 else n
            if self.tour_counter >= max_tours:
                raise PairingError(f"В лиге '{league}' все команды уже сыграли друг с другом.")

            # Если команд нечетное число, добавляем виртуальную команду (bye)
            teams_cycle = list(league_teams)
            if n % 2 != 0:
                teams_cycle.append(None)
                n += 1

            fixed = teams_cycle[0]
            others = teams_cycle[1:]
            
            shift = self.tour_counter % (n - 1)
            rotated = others[-shift:] + others[:-shift]
            current_teams = [fixed] + rotated
            
            for i in range(n // 2):
                t1, t2 = current_teams[i], current_teams[n - 1 - i]
                if t1 is not None and t2 is not None:
                    upcoming_matches.append((t1, t2))
                    
        return upcoming_matches