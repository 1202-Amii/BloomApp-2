# Базовый образ
FROM python:3.9-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install "python-telegram-bot[webhooks]"

# Копируем все файлы проекта в контейнер
COPY . .

# Указываем порт, который будет использовать приложение
EXPOSE 8443

# Команда для запуска приложения
CMD ["python", "bot.py"]