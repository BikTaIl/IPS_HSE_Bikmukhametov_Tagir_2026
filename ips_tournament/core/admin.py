from django.contrib import admin
from .models import User, Tournament, Team, Fight

# Регистрируем кастомную модель пользователя
admin.site.register(User)

# Регистрируем модели турнира, чтобы ими можно было управлять из админки
@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('tournament_number', 'start_date', 'end_date')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('child_name', 'school_class', 'league', 'current_points', 'tournament')
    list_filter = ('school_class', 'league', 'tournament')

@admin.register(Fight)
class FightAdmin(admin.ModelAdmin):
    list_display = ('tour_number', 'team_one', 'team_two', 'ended')
    list_filter = ('tour_number', 'ended')