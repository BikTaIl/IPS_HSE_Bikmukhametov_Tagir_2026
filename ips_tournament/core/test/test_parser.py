from django.test import TestCase
from core.constructor.python_parser import FromPythonCode

class SecurityParserTests(TestCase):

    def test_valid_safe_code(self):
        """Проверка корректно написанной функции вероятностей"""
        code = "return (m + p + 10, n + k, 5)"
        func = FromPythonCode(code)
        
        res = func.match_probabilities(10, 5, 5, 2)
        self.assertEqual(len(res), 3)
        self.assertAlmostEqual(sum(res), 1.0)

    def test_import_blocking(self):
        """Любые импорты должны быть заблокированы AST-парсером"""
        code = "import os\nreturn (1, 1, 1)"
        with self.assertRaises(ValueError) as context:
            FromPythonCode(code)
        self.assertIn("Импорты модулей запрещены", str(context.exception))

    def test_loops_blocking(self):
        """Циклы (while/for) должны блокироваться, чтобы избежать зависаний (Time Limit)"""
        code = "while True: pass\nreturn (1, 1, 1)"
        with self.assertRaises(ValueError):
            FromPythonCode(code)

    def test_negative_probability_blocking(self):
        """Парсер должен пресекать возвращение отрицательных вероятностей"""
        code = "return (-1, 5, 5)"
        func = FromPythonCode(code)
        with self.assertRaises(ValueError) as context:
            func.match_probabilities(0, 0, 0, 0)
        self.assertIn("не может быть отрицательной", str(context.exception))

    def test_all_zero_probability_blocking(self):
        """Парсер должен запрещать возвращение (0, 0, 0), так как на это нельзя поделить"""
        code = "return (0, 0, 0)"
        func = FromPythonCode(code)
        with self.assertRaises(ValueError):
            func.match_probabilities(0, 0, 0, 0)
            
    def test_allowed_builtins_work(self):
        """Разрешенные встроенные функции (max, min, abs) должны работать"""
        code = "return (max(m, p), min(n, k), abs(m - p))"
        func = FromPythonCode(code)
        res = func.match_probabilities(10, 5, 2, 1)
        self.assertEqual(len(res), 3)
        self.assertAlmostEqual(sum(res), 1.0)
