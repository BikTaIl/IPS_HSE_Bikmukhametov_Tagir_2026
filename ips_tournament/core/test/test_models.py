from django.test import TestCase
from core.models import User

class RoleHierarchyTests(TestCase):
    def setUp(self):
        # Строим дерево иерархии пользователей
        self.superadmin = User.objects.create(username='sa', role=User.Role.SUPERADMIN)
        
        self.admin_boss = User.objects.create(username='admin_boss', role=User.Role.ADMIN, granted_by=self.superadmin)
        self.admin_sub = User.objects.create(username='admin_sub', role=User.Role.ADMIN, granted_by=self.admin_boss)
        
        self.admin_independent = User.objects.create(username='admin_indep', role=User.Role.ADMIN, granted_by=self.superadmin)
        
        self.editor = User.objects.create(username='editor1', role=User.Role.EDITOR, granted_by=self.admin_independent)
        self.user = User.objects.create(username='user1', role=User.Role.USER)

    def test_superadmin_omnipotence(self):
        """Суперадмин должен иметь возможность управлять любым пользователем"""
        self.assertTrue(self.superadmin.can_manage(self.admin_boss))
        self.assertTrue(self.superadmin.can_manage(self.editor))

    def test_admin_can_manage_subordinate_admin(self):
        """Администратор может управлять админом, которому он сам выдал права (или по цепочке ниже)"""
        self.assertTrue(self.admin_boss.can_manage(self.admin_sub))
        
    def test_admin_cannot_manage_superior_or_parallel_admin(self):
        """Администратор НЕ может управлять своим 'начальником' или админом из другой ветки"""
        self.assertFalse(self.admin_sub.can_manage(self.admin_boss))
        self.assertFalse(self.admin_boss.can_manage(self.admin_independent))

    def test_admin_can_manage_any_editor(self):
        """Любой администратор может управлять любым редактором, независимо от ветки"""
        self.assertTrue(self.admin_boss.can_manage(self.editor))

    def test_user_powerlessness(self):
        """Обычный пользователь не имеет прав управления"""
        self.assertFalse(self.user.can_manage(self.editor))
        self.assertFalse(self.user.can_manage(self.user))
