from django.contrib.auth.models import AbstractUser
from django.db import models
import datetime

class User(AbstractUser):
    # Определяем доступные роли
    class Role(models.TextChoices):
        USER = 'USER', 'Пользователь'
        EDITOR = 'EDITOR', 'Редактор'
        ADMIN = 'ADMIN', 'Администратор'
        SUPERADMIN = 'SUPERADMIN', 'Суперадминистратор'

    role = models.CharField(max_length=15, choices=Role.choices, default=Role.USER)
    
    # Ссылка на пользователя, который выдал права (для построения дерева иерархии)
    granted_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='granted_users'
    )

    def is_strictly_below(self, target_admin):
        """
        Проверяет, находится ли текущий пользователь строго ниже target_admin по иерархии.
        Идет вверх по цепочке granted_by.
        """
        current = self.granted_by
        while current is not None:
            if current == target_admin:
                return True
            current = current.granted_by
        return False

    def can_manage(self, target_user):
        """Проверяет, имеет ли право self удалить права у target_user."""
        # Суперадмин может всё
        if self.role == self.Role.SUPERADMIN or self.is_superuser:
            return True
        
        # Только админы могут управлять другими
        if self.role != self.Role.ADMIN:
            return False
            
        # Админ может удалить любого редактора (независимо от того, кто выдал права)
        if target_user.role == self.Role.EDITOR:
            return True
            
        # Админ может удалить другого админа, только если тот строго ниже по иерархии
        if target_user.role == self.Role.ADMIN:
            return target_user.is_strictly_below(self)
            
        return False
    
class Tournament(models.Model):
    tournament_number = models.IntegerField(verbose_name="Номер турнира")
    start_date = models.DateField(verbose_name="Дата старта")
    end_date = models.DateField(verbose_name="Дата окончания")
    rules_file = models.FileField(upload_to='tournament_docs/', null=True, blank=True, verbose_name="Свод правил")
    info_letter_file = models.FileField(upload_to='tournament_docs/', null=True, blank=True, verbose_name="Информационное письмо")

    class Meta:
        verbose_name = "Турнир"
        verbose_name_plural = "Турниры"

    def __str__(self):
        return f"Турнир №{self.tournament_number}"


class Team(models.Model):
    tournament = models.ForeignKey(
        Tournament, 
        on_delete=models.CASCADE,
        related_name='teams', 
        verbose_name="Турнир"
    )
    work_name = models.CharField(max_length=255, verbose_name="Рабочее название")
    child_name = models.CharField(max_length=255, verbose_name="Детское название")
    
    players_quantity = models.IntegerField(null=False, blank=True, verbose_name="Количество участников") 
    
    komol_points = models.IntegerField(null=True, blank=True, verbose_name="Баллы на комоле")
    komol_minuses = models.IntegerField(null=True, blank=True, verbose_name="Минусы на комоле")
    current_points = models.IntegerField(default=0, verbose_name="Текущие очки")
    league = models.CharField(max_length=100, null=True, blank=True, verbose_name="Лига")
    
    school_class = models.IntegerField(null=True, blank=True, verbose_name="Класс") 
    in_league_number = models.IntegerField(null=True, blank=True, verbose_name="Номер внутри лиги")

    class Meta:
        verbose_name = "Команда"
        verbose_name_plural = "Команды"

    def __str__(self):
        return f"{self.child_name} ({self.school_class} класс)"


class Fight(models.Model):
    team_one = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='fights_team_one')
    team_two = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='fights_team_two')
    team_one_points = models.IntegerField(null=True, blank=True)
    team_two_points = models.IntegerField(null=True, blank=True)
    
    judge_first = models.CharField(max_length=255, default="Не назначен")
    judge_second = models.CharField(max_length=255, blank=True, default="")
    place = models.CharField(max_length=255, default="ТВА") 
    solution_place = models.CharField(max_length=255, default="ТВА")
    
    value_day = models.DateField(default=datetime.date.today) 
    fight_time = models.TimeField(default=datetime.time(23, 59)) 
    solution_ts = models.TimeField(default=datetime.time(23, 59))
    
    tour_number = models.IntegerField(default=0)
    ended = models.BooleanField(default=False)

    def __str__(self):
        return f"Тур {self.tour_number}: {self.team_one.child_name} vs {self.team_two.child_name}"
    
class Olympiad(models.Model):
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='olympiad')
    plus_count = models.IntegerField(default=0)
    minus_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Комол: {self.team.work_name} (+{self.plus_count} / -{self.minus_count})"

class FAQ(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='faqs', verbose_name="Турнир")
    question = models.TextField(verbose_name="Вопрос")
    answer = models.TextField(verbose_name="Ответ")

    class Meta:
        verbose_name = "Частый вопрос"
        verbose_name_plural = "Частые вопросы"

    def __str__(self):
        return self.question