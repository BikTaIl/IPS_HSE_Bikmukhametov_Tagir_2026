from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from core.models import User, Tournament, FAQ

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class FrontendUITests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if SELENIUM_AVAILABLE:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless') # Запуск без визуального окна браузера
            cls.selenium = webdriver.Chrome(options=options)
            cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        if not SELENIUM_AVAILABLE:
            self.skipTest("Selenium не установлен. Пропуск E2E тестов фронтенда.")
            
        self.tournament = Tournament.objects.create(tournament_number=99, start_date='2025-01-01', end_date='2025-01-02')
        self.faq = FAQ.objects.create(tournament=self.tournament, question="Тестовый вопрос?", answer="Тестовый ответ.")
        self.admin = User.objects.create_user(username='admin_ui', password='123', role=User.Role.ADMIN)

    def test_info_page_displays_content_for_guests(self):
        """Изолированный тест фронтенда: гость должен видеть ЧаВО, но не видеть админ-панель JS"""
        self.selenium.get(f"{self.live_server_url}/info/")
        
        body_text = self.selenium.find_element(By.TAG_NAME, 'body').text
        self.assertIn("Информация о турнире №99", body_text)
        self.assertIn("Тестовый вопрос?", body_text)
        self.assertIn("Тестовый ответ.", body_text)
        
        # Проверяем отсутствие фронтенд-панели управления для гостя
        admin_panels = self.selenium.find_elements(By.CLASS_NAME, 'admin-panel')
        self.assertEqual(len(admin_panels), 0)

        # Проверка, что кнопка удаления (btn-danger) скрыта JS/HTML логикой
        delete_buttons = self.selenium.find_elements(By.CLASS_NAME, 'btn-danger')
        self.assertEqual(len(delete_buttons), 0)
