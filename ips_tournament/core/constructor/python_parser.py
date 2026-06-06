import ast
import textwrap
from typing import Tuple
from .abstract import WinFunction

class SecurityNodeVisitor(ast.NodeVisitor):
    """
    Проходится по дереву кода и жестко блокирует любые потенциально опасные конструкции.
    """
    allowed_functions = {'abs', 'min', 'max', 'round'}

    def visit_Import(self, node):
        raise ValueError("Импорты модулей запрещены!")

    def visit_ImportFrom(self, node):
        raise ValueError("Импорты модулей запрещены!")

    def visit_Attribute(self, node):
        raise ValueError("Доступ к атрибутам (через точку) запрещен для безопасности!")

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id not in self.allowed_functions:
                raise ValueError(f"Вызов функции '{node.func.id}()' запрещен!")
        else:
            raise ValueError("Сложные вызовы функций запрещены!")
        self.generic_visit(node)

    def visit_While(self, node):
        raise ValueError("Циклы (while) запрещены!")
        
    def visit_For(self, node):
        raise ValueError("Циклы (for) запрещены!")


def FromPythonCode(code_str: str) -> WinFunction:
    """
    Принимает строку с Python-кодом, проверяет её на безопасность через AST,
    и возвращает объект WinFunction.
    """
    
    indented_code = textwrap.indent(code_str.strip(), '    ')
    if not indented_code:
        raise ValueError("Код не может быть пустым.")
        
    full_code = f"def _user_win_func(m, n, p, k):\n{indented_code}"

    try:
        tree = ast.parse(full_code)
        validator = SecurityNodeVisitor()
        validator.visit(tree)
    except SyntaxError as e:
        raise ValueError(f"Синтаксическая ошибка в вашем коде: {e.msg} (строка {e.lineno})")
    
    safe_globals = {
        '__builtins__': {
            'abs': abs, 'min': min, 'max': max, 'round': round
        }
    }
    safe_locals = {}
    
    try:
        exec(full_code, safe_globals, safe_locals)
        user_func = safe_locals['_user_win_func']
    except Exception as e:
        raise ValueError(f"Ошибка компиляции: {str(e)}")

    def safe_wrapper(m: int, n: int, p: int, k: int) -> Tuple[float, float, float]:
        try:
            res = user_func(m, n, p, k)
        except Exception as e:
            raise RuntimeError(f"Ошибка при выполнении функции: {str(e)}")
        
        if not isinstance(res, (tuple, list)) or len(res) != 3:
            raise ValueError(f"Код должен возвращать 3 числа (win, draw, loss). Получено: {res}")
            
        w, d, l = float(res[0]), float(res[1]), float(res[2])
        
        # 1. Строгая проверка на отрицательные числа
        if w < 0 or d < 0 or l < 0:
            raise ValueError("Вероятность не может быть отрицательной")
            
        total = w + d + l
        
        # 2. Строгая проверка на все нули
        if total == 0:
            raise ValueError("Хотя бы одна из вероятностей должна быть положительной")
            
        # Нормализуем, чтобы сумма всегда была ровно 1.0
        # (Например, если юзер вернул 70, 20, 10 вместо 0.7, 0.2, 0.1)
        return (w/total, d/total, l/total)

    return WinFunction(safe_wrapper)