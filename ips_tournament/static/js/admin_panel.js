// Конфигурация эндпоинтов
const API_URLS = {
    getUsersByRole: '/api/roles/users/', // GET: ?role=admin или ?role=editor
    addRole: '/api/roles/add/',          // POST
    removeRole: '/api/roles/remove/'     // POST или DELETE
};

// Функция для получения CSRF токена в Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Загрузка списков при открытии страницы
document.addEventListener('DOMContentLoaded', () => {
    loadUsers('admin', 'admins-list');
    loadUsers('editor', 'editors-list');
});

// Загрузка пользователей определенной роли
async function loadUsers(role, tableBodyId) {
    try {
        const response = await fetch(`${API_URLS.getUsersByRole}?role=${role}`);
        const data = await response.json();
        
        const tbody = document.getElementById(tableBodyId);
        tbody.innerHTML = ''; 

        data.users.forEach(user => {
            const tr = document.createElement('tr');
            
            const deleteBtn = user.can_delete 
                ? `<button class="delete-btn" onclick="removeRole('${user.login}', '${role}')">Отозвать права</button>` 
                : `<span class="text-muted">Нет прав для удаления</span>`;

            tr.innerHTML = `
                <td>${user.login}</td>
                <td>${user.granted_by || 'Суперадминистратор'}</td>
                <td>${deleteBtn}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error(`Ошибка при загрузке ${role}:`, error);
    }
}

// Добавление новой роли пользователю
async function addRole(role) {
    const inputId = role === 'admin' ? 'new-admin-login' : 'new-editor-login';
    const loginInput = document.getElementById(inputId);
    const login = loginInput.value.trim();

    if (!login) {
        alert('Пожалуйста, введите логин пользователя.');
        return;
    }

    try {
        const response = await fetch(API_URLS.addRole, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ login: login, role: role })
        });

        const result = await response.json();

        if (response.ok) {
            alert('Права успешно выданы.');
            loginInput.value = '';
            // Обновляем нужную таблицу
            loadUsers(role, role === 'admin' ? 'admins-list' : 'editors-list');
        } else {
            alert(`Ошибка: ${result.error || 'Пользователь не найден или уже имеет роль.'}`);
        }
    } catch (error) {
        console.error('Ошибка добавления:', error);
    }
}

// Удаление роли (проверка иерархии должна быть строго на бэкенде!)
async function removeRole(login, role) {
    if (!confirm(`Вы уверены, что хотите отозвать права "${role}" у пользователя ${login}?`)) {
        return;
    }

    try {
        const response = await fetch(API_URLS.removeRole, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ login: login, role: role })
        });

        const result = await response.json();

        if (response.ok) {
            // Обновляем нужную таблицу
            loadUsers(role, role === 'admin' ? 'admins-list' : 'editors-list');
        } else {
            alert(`Ошибка: ${result.error || 'Недостаточно прав для удаления этого пользователя.'}`);
        }
    } catch (error) {
        console.error('Ошибка удаления:', error);
    }
}