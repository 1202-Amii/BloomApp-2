from datetime import datetime, timedelta
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackContext,
)
# Импортируем дополнительные модули для планирования задач
from telegram.ext import JobQueue
from datetime import datetime, time, timedelta

# Функция для отправки ежедневных уведомлений пользователю
async def send_daily_notification(context: CallbackContext):
    """Отправляет ежедневные уведомления с рекомендациями."""
    job = context.job
    user_id = job.data['user_id']
    
    # Проверяем, существуют ли данные пользователя
    if user_id not in user_data_dict:
        logger.error(f"Данные пользователя {user_id} не найдены для отправки уведомления")
        return
    
    user_data = user_data_dict[user_id]
    current_day = calculate_cycle_day(user_data)
    current_phase = determine_phase(current_day, user_data)
    
    recommendations = RECOMMENDATIONS[current_phase]
    name = user_data.get('name', 'Пользователь')
    
    # Создаем сообщение с рекомендациями на день
    message = (
        f"🌸 Доброе утро, {name}!\n\n"
        f"Сегодня день {current_day} твоего цикла - {PHASES[current_phase]['description'].lower()} фаза.\n\n"
        f"Рекомендации на сегодня:\n\n"
        f"🍽️ Питание:\n{recommendations['питание']}\n\n"
        f"🏃‍♀️ Физическая активность:\n{recommendations['физическая_нагрузка']}\n\n"
        f"🧠 Ментальное состояние:\n{recommendations['ментальное_состояние']}"
    )
    
    # Добавляем специальные уведомления в зависимости от фазы цикла
    if current_phase == "менструальная" and current_day == 1:
        message += "\n\n⚠️ Сегодня первый день твоих месячных. Будь готова и позаботься о себе."
    elif current_phase == "овуляторная" and current_day == user_data['ovulation_day']:
        message += "\n\n🥚 Сегодня день твоей овуляции."
    elif current_phase == "лютеиновая" and user_data['cycle_length'] - current_day <= 2:
        message += f"\n\n⚠️ Твои месячные начнутся примерно через {user_data['cycle_length'] - current_day + 1} дня. Не забудь подготовиться!"
    
    # Напоминание об отметке уровня энергии
    message += "\n\n🔋 Не забудь отметить свой уровень энергии сегодня!"
    
    # Отправляем сообщение пользователю
    await context.bot.send_message(user_id, message)
    
    logger.info(f"Отправлено ежедневное уведомление пользователю {user_id}")

# Функция для планирования ежедневных уведомлений
def schedule_daily_notifications(user_id, context):
    """Планирует ежедневные уведомления для пользователя."""
    # Отменяем предыдущие запланированные уведомления для этого пользователя
    current_jobs = context.job_queue.get_jobs_by_name(f"daily_notification_{user_id}")
    for job in current_jobs:
        job.schedule_removal()
    
    # Устанавливаем время для ежедневных уведомлений (например, 9:00 утра)
    notification_time = time(9, 0, 0)  # 9:00 AM
    
    # Вычисляем, когда отправить первое уведомление
    now = datetime.now()
    target_time = datetime.combine(now.date(), notification_time)
    
    # Если текущее время уже после времени уведомления, запланируем на завтра
    if now.time() >= notification_time:
        target_time = target_time + timedelta(days=1)
    
    # Вычисляем задержку до первого уведомления в секундах
    first_delay = (target_time - now).total_seconds()
    
    # Планируем ежедневные уведомления
    context.job_queue.run_repeating(
        send_daily_notification,
        interval=timedelta(days=1).total_seconds(),  # Интервал в 24 часа
        first=first_delay,
        data={'user_id': user_id},
        name=f"daily_notification_{user_id}"
    )
    
    logger.info(f"Запланированы ежедневные уведомления для пользователя {user_id}, первое уведомление через {first_delay/3600:.2f} часов")

# Обновленная функция для включения/выключения уведомлений
async def toggle_notifications(update: Update, context: CallbackContext) -> int:
    """Включает или выключает ежедневные уведомления."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return MAIN_MENU
    
    # Проверяем текущий статус уведомлений
    notifications_enabled = user_data_dict[user_id].get('notifications_enabled', False)
    
    if notifications_enabled:
        # Отключаем уведомления
        current_jobs = context.job_queue.get_jobs_by_name(f"daily_notification_{user_id}")
        for job in current_jobs:
            job.schedule_removal()
            
        user_data_dict[user_id]['notifications_enabled'] = False
        await update.message.reply_text(
            "Ежедневные уведомления отключены. Вы можете включить их снова в любое время.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Включаем уведомления
        schedule_daily_notifications(user_id, context)
        user_data_dict[user_id]['notifications_enabled'] = True
        await update.message.reply_text(
            "Ежедневные уведомления включены! Вы будете получать рекомендации каждое утро в 9:00.",
            reply_markup=get_main_menu_keyboard()
        )
    
    return MAIN_MENU

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
NAME, AGE, LAST_PERIOD_DATE, PERIOD_DURATION, MAIN_MENU, ENERGY_LEVEL = range(6)

# Словарь для хранения данных пользователей
user_data_dict = {}

# Фазы цикла (будут вычисляться динамически)
PHASES = {
    "менструальная": {"description": "Менструальная фаза"},
    "фолликулярная": {"description": "Фолликулярная фаза"},
    "овуляторная": {"description": "Овуляция"},
    "лютеиновая": {"description": "Лютеиновая фаза"}
}

# Рекомендации по фазам
RECOMMENDATIONS = {
    "менструальная": {
        "питание": "Увеличьте потребление железа (красное мясо, шпинат, чечевица). Избегайте соленой пищи, которая может усилить вздутие.",
        "физическая_нагрузка": "Предпочтение легкой активности: йога, пилатес, прогулки. Избегайте интенсивных тренировок.",
        "ментальное_состояние": "Уделите время себе, практикуйте медитацию и глубокое дыхание. Хорошее время для планирования."
    },
    "фолликулярная": {
        "питание": "Сосредоточьтесь на свежих фруктах, овощах и белках. Хорошее время для введения новых продуктов в рацион.",
        "физическая_нагрузка": "Увеличивайте интенсивность - кардио, силовые тренировки. Энергия повышается, воспользуйтесь этим.",
        "ментальное_состояние": "Хорошее время для новых начинаний, обучения и творчества. Ваш мозг более восприимчив к новой информации."
    },
    "овуляторная": {
        "питание": "Включите продукты, богатые антиоксидантами. Ешьте больше зелени, орехов и семян.",
        "физическая_нагрузка": "Пик энергии - идеальное время для высокоинтенсивных тренировок, групповых занятий и новых физических вызовов.",
        "ментальное_состояние": "Используйте повышенную коммуникабельность для важных переговоров, презентаций и социальных мероприятий."
    },
    "лютеиновая": {
        "питание": "Увеличьте потребление магния и кальция (тёмный шоколад, орехи, листовая зелень). Следите за тягой к сладкому.",
        "физическая_нагрузка": "По мере приближения к менструации снижайте интенсивность. Хорошо подходит йога и плавание.",
        "ментальное_состояние": "Уделите внимание самоанализу, рефлексии. Будьте готовы к возможным перепадам настроения."
    }
}

async def start(update: Update, context: CallbackContext) -> int:
    """Начало разговора и запрос имени пользователя."""
    await update.message.reply_text(
        "Привет! Я бот-помощник для отслеживания менструального цикла. "
        "Я помогу тебе отслеживать фазы цикла и дам персонализированные рекомендации. "
        "Для начала, как я могу к тебе обращаться?"
    )
    return NAME

async def get_name(update: Update, context: CallbackContext) -> int:
    """Сохраняет имя и запрашивает возраст."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        user_data_dict[user_id] = {}
    
    user_data_dict[user_id]['name'] = update.message.text
    
    await update.message.reply_text(
        f"Приятно познакомиться, {user_data_dict[user_id]['name']}! "
        "Сколько тебе лет? (пожалуйста, введи число)"
    )
    return AGE

async def get_age(update: Update, context: CallbackContext) -> int:
    """Сохраняет возраст и запрашивает дату последних месячных."""
    user_id = update.message.from_user.id
    
    try:
        age = int(update.message.text)
        if age < 8 or age > 60:
            await update.message.reply_text(
                "Пожалуйста, введи корректный возраст (от 8 до 60 лет)."
            )
            return AGE
        
        user_data_dict[user_id]['age'] = age
        
        await update.message.reply_text(
            "Спасибо! Когда начались твои последние месячные? "
            "Пожалуйста, введи дату в формате ДД.ММ.ГГГГ (например, 15.03.2025)"
        )
        return LAST_PERIOD_DATE
    
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введи свой возраст числом."
        )
        return AGE

async def get_last_period_date(update: Update, context: CallbackContext) -> int:
    """Сохраняет дату последних месячных и запрашивает продолжительность."""
    user_id = update.message.from_user.id
    
    try:
        date_str = update.message.text
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        
        if date_obj > datetime.now():
            await update.message.reply_text(
                "Дата не может быть в будущем. Пожалуйста, введи корректную дату."
            )
            return LAST_PERIOD_DATE
        
        user_data_dict[user_id]['last_period_date'] = date_obj
        
        await update.message.reply_text(
            "Сколько дней обычно длятся твои месячные? (введи число от 1 до 10)"
        )
        return PERIOD_DURATION
    
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введи дату в формате ДД.ММ.ГГГГ (например, 15.03.2025)"
        )
        return LAST_PERIOD_DATE

async def get_period_duration(update: Update, context: CallbackContext) -> int:
    """Сохраняет продолжительность месячных и запрашивает общую длину цикла."""
    user_id = update.message.from_user.id
    
    try:
        duration = int(update.message.text)
        if duration < 1 or duration > 10:
            await update.message.reply_text(
                "Пожалуйста, введи число от 1 до 10."
            )
            return PERIOD_DURATION
        
        user_data_dict[user_id]['period_duration'] = duration
        
        # Добавляем запрос общей длины цикла
        await update.message.reply_text(
            "Какова общая длина твоего цикла (от первого дня месячных до первого дня следующих)? "
            "Обычно это от 21 до 35 дней. Если не знаешь точно, введи 28."
        )
        
        # Добавляем новое состояние для получения длины цикла
        return CYCLE_LENGTH
    
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введи продолжительность числом."
        )
        return PERIOD_DURATION

# Добавляем новое состояние для длины цикла
CYCLE_LENGTH = 6  # Новый индекс состояния

async def get_cycle_length(update: Update, context: CallbackContext) -> int:
    """Сохраняет общую длину цикла и переходит в главное меню."""
    user_id = update.message.from_user.id
    
    try:
        cycle_length = int(update.message.text)
        if cycle_length < 21 or cycle_length > 45:
            await update.message.reply_text(
                "Пожалуйста, введи число от 21 до 45. "
                "Средняя длина цикла обычно 28 дней."
            )
            return CYCLE_LENGTH
        
        user_data_dict[user_id]['cycle_length'] = cycle_length
        user_data_dict[user_id]['energy_logs'] = []
        
        # Рассчитываем следующие месячные
        next_period = user_data_dict[user_id]['last_period_date'] + timedelta(days=cycle_length)
        user_data_dict[user_id]['next_period_date'] = next_period
        
        # Вычисляем день овуляции
        ovulation_day = cycle_length - 14
        user_data_dict[user_id]['ovulation_day'] = ovulation_day
        
        # Предлагаем включить уведомления
        keyboard = [
            ['✅ Да, включить уведомления'],
            ['❌ Нет, позже']
        ]
        notification_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        # Отправляем сообщение с данными
        await update.message.reply_text(
            f"Спасибо за информацию, {user_data_dict[user_id]['name']}!\n\n"
            f"Возраст: {user_data_dict[user_id]['age']}\n"
            f"Дата последних месячных: {user_data_dict[user_id]['last_period_date'].strftime('%d.%m.%Y')}\n"
            f"Продолжительность месячных: {user_data_dict[user_id]['period_duration']} дней\n"
            f"Длина цикла: {cycle_length} дней\n"
            f"Овуляция: примерно {ovulation_day}-й день цикла\n"
            f"Ожидаемая дата следующих месячных: {next_period.strftime('%d.%m.%Y')}\n\n"
            "Теперь я могу отслеживать твой цикл и давать рекомендации!\n\n"
            "Хочешь получать ежедневные уведомления с персонализированными рекомендациями?",
            reply_markup=notification_markup
        )
        
        # Добавляем новое состояние для обработки ответа на предложение включить уведомления
        return NOTIFICATION_SETUP
    
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введи длину цикла числом."
        )
        return CYCLE_LENGTH
    # Добавляем новое состояние
NOTIFICATION_SETUP = 7  # Новый индекс состояния

async def setup_notifications(update: Update, context: CallbackContext) -> int:
    """Обрабатывает ответ на предложение включить уведомления."""
    user_id = update.message.from_user.id
    message_text = update.message.text
    
    if message_text == '✅ Да, включить уведомления':
        # Включаем уведомления
        user_data_dict[user_id]['notifications_enabled'] = True
        schedule_daily_notifications(user_id, context)
        
        await update.message.reply_text(
            "Отлично! Ты будешь получать ежедневные уведомления с рекомендациями каждое утро в 9:00.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Уведомления отключены
        user_data_dict[user_id]['notifications_enabled'] = False
        
        await update.message.reply_text(
            "Хорошо, ты можешь включить уведомления позже через меню 'Уведомления'.",
            reply_markup=get_main_menu_keyboard()
        )
    
    return MAIN_MENU  
        

def get_main_menu_keyboard():
    """Создает клавиатуру главного меню."""
    keyboard = [
        ['📊 Моя текущая фаза', '🔋 Отметить уровень энергии'],
        ['📝 Получить рекомендации', '📅 Статистика цикла'],
        ['⚙️ Изменить настройки', '🔔 Уведомления']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_energy_level_keyboard():
    """Создает клавиатуру для оценки уровня энергии."""
    keyboard = [
        ['🔥 1', '🔥🔥 2', '🔥🔥🔥 3', '🔥🔥🔥🔥 4', '🔥🔥🔥🔥🔥 5'],
        ['↩️ Вернуться в главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def calculate_cycle_day(user_data):
    """Рассчитывает текущий день цикла."""
    today = datetime.now()
    days_since_period = (today - user_data['last_period_date']).days % user_data['cycle_length']
    return days_since_period + 1  # +1 чтобы первый день был 1, а не 0

def determine_phase(day, user_data):
    """Определяет текущую фазу цикла на основе дня цикла и персональных данных."""
    period_duration = user_data['period_duration']
    cycle_length = user_data['cycle_length']
    ovulation_day = user_data['ovulation_day']
    
    # Менструальная фаза: с 1-го дня до окончания месячных
    if 1 <= day <= period_duration:
        return "менструальная"
    
    # Овуляторная фаза: день овуляции и день до/после (примерно 3 дня)
    elif ovulation_day - 1 <= day <= ovulation_day + 1:
        return "овуляторная"
    
    # Фолликулярная фаза: после месячных до овуляции
    elif period_duration < day < ovulation_day - 1:
        return "фолликулярная"
    
    # Лютеиновая фаза: после овуляции до конца цикла
    else:
        return "лютеиновая"

def get_phase_info(user_data):
    """Возвращает информацию о днях всех фаз цикла для конкретного пользователя."""
    period_duration = user_data['period_duration']
    cycle_length = user_data['cycle_length']
    ovulation_day = user_data['ovulation_day']
    
    phases_info = {
        "менструальная": f"1-{period_duration} день цикла",
        "фолликулярная": f"1-{ovulation_day-1} день цикла",
        "овуляторная": f"{ovulation_day-1}-{ovulation_day+1} день цикла",
        "лютеиновая": f"{ovulation_day+2}-{cycle_length} день цикла"
    }
    
    return phases_info

async def show_current_phase(update: Update, context: CallbackContext) -> int:
    """Показывает информацию о текущей фазе цикла."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    user_data = user_data_dict[user_id]
    current_day = calculate_cycle_day(user_data)
    current_phase = determine_phase(current_day, user_data)
    phases_info = get_phase_info(user_data)
    
    days_to_next_period = user_data['cycle_length'] - current_day + 1
    
    # Предупреждение о скорых месячных
    warning_message = ""
    if days_to_next_period <= 3 and current_phase == "лютеиновая":
        warning_message = "\n\n⚠️ Твои месячные начнутся примерно через " + \
                         f"{days_to_next_period} {'день' if days_to_next_period == 1 else 'дня' if 2 <= days_to_next_period <= 4 else 'дней'}. " + \
                         "Не забудь взять с собой прокладки или тампоны!"
    
    # Информация о предстоящей овуляции
    ovulation_message = ""
    ovulation_day = user_data['ovulation_day']
    days_to_ovulation = ovulation_day - current_day
    
    if current_phase == "фолликулярная" and 1 <= days_to_ovulation <= 3:
        ovulation_message = f"\n\n🥚 Овуляция ожидается через {days_to_ovulation} " + \
                           f"{'день' if days_to_ovulation == 1 else 'дня' if 2 <= days_to_ovulation <= 4 else 'дней'}."
    
    await update.message.reply_text(
        f"📊 Твой текущий статус цикла:\n\n"
        f"🗓️ День цикла: {current_day} из {user_data['cycle_length']}\n"
        f"🌀 Фаза: {PHASES[current_phase]['description']}\n"
        f"ℹ️ Фазы твоего цикла:\n"
        f"- Менструальная: {phases_info['менструальная']}\n"
        f"- Фолликулярная: {phases_info['фолликулярная']}\n"
        f"- Овуляция: {phases_info['овуляторная']}\n"
        f"- Лютеиновая: {phases_info['лютеиновая']}\n\n"
        f"📅 Следующие месячные ожидаются через {days_to_next_period} " + 
        f"{'день' if days_to_next_period == 1 else 'дня' if 2 <= days_to_next_period <= 4 else 'дней'}" +
        warning_message + ovulation_message,
        reply_markup=get_main_menu_keyboard()
    )
    
    return MAIN_MENU

async def start_energy_log(update: Update, context: CallbackContext) -> int:
    """Запрашивает уровень энергии у пользователя."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Оцени свой уровень энергии сегодня от 1 до 5 огоньков:",
        reply_markup=get_energy_level_keyboard()
    )
    
    return ENERGY_LEVEL

async def log_energy_level(update: Update, context: CallbackContext) -> int:
    """Записывает уровень энергии пользователя."""
    user_id = update.message.from_user.id
    message_text = update.message.text
    
    if message_text == '↩️ Вернуться в главное меню':
        await update.message.reply_text(
            "Возвращаемся в главное меню",
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU
    
    # Обработка ввода уровня энергии
    energy_mapping = {
        '🔥 1': 1,
        '🔥🔥 2': 2,
        '🔥🔥🔥 3': 3,
        '🔥🔥🔥🔥 4': 4,
        '🔥🔥🔥🔥🔥 5': 5
    }
    
    if message_text in energy_mapping:
        energy_level = energy_mapping[message_text]
        today = datetime.now().date()
        current_day = calculate_cycle_day(user_data_dict[user_id])
        
        # Сохраняем данные
        user_data_dict[user_id]['energy_logs'].append({
            'date': today,
            'cycle_day': current_day,
            'energy_level': energy_level
        })
        
        current_phase = determine_phase(current_day, user_data_dict[user_id])
        
        await update.message.reply_text(
            f"Спасибо! Я записал твой уровень энергии: {message_text}\n"
            f"Текущая фаза: {PHASES[current_phase]['description']}\n"
            "Эти данные помогут проанализировать твой цикл!",
            reply_markup=get_main_menu_keyboard()
        )
        
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "Пожалуйста, выбери уровень энергии от 1 до 5 огоньков из предложенных вариантов.",
            reply_markup=get_energy_level_keyboard()
        )
        
        return ENERGY_LEVEL

async def show_recommendations(update: Update, context: CallbackContext) -> int:
    """Показывает рекомендации на основе текущей фазы цикла."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    user_data = user_data_dict[user_id]
    current_day = calculate_cycle_day(user_data)
    current_phase = determine_phase(current_day, user_data)
    
    recommendations = RECOMMENDATIONS[current_phase]
    
    await update.message.reply_text(
        f"📝 Рекомендации для {PHASES[current_phase]['description'].lower()} (день {current_day}):\n\n"
        f"🍽️ Питание:\n{recommendations['питание']}\n\n"
        f"🏃‍♀️ Физическая активность:\n{recommendations['физическая_нагрузка']}\n\n"
        f"🧠 Ментальное состояние:\n{recommendations['ментальное_состояние']}",
        reply_markup=get_main_menu_keyboard()
    )
    
    return MAIN_MENU

async def show_cycle_statistics(update: Update, context: CallbackContext) -> int:
    """Показывает статистику цикла пользователя."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    user_data = user_data_dict[user_id]
    energy_logs = user_data.get('energy_logs', [])
    
    if not energy_logs:
        await update.message.reply_text(
            "У тебя пока нет записей об уровне энергии. "
            "Отмечай свой уровень энергии каждый день, чтобы видеть статистику!",
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU
    
    # Анализ данных об энергии
    avg_energy = sum(log['energy_level'] for log in energy_logs) / len(energy_logs)
    
    # Группировка по фазам
    phase_energy = {phase: [] for phase in PHASES.keys()}
    for log in energy_logs:
        day = log['cycle_day']
        phase = determine_phase(day, user_data)
        phase_energy[phase].append(log['energy_level'])
    
    # Вычисление средней энергии по фазам
    phase_avg_energy = {}
    for phase, levels in phase_energy.items():
        if levels:
            phase_avg_energy[phase] = sum(levels) / len(levels)
        else:
            phase_avg_energy[phase] = "Нет данных"
    
    # Формирование ответа
    phase_info = ""
    for phase, avg in phase_avg_energy.items():
        if avg != "Нет данных":
            fire_emoji = "🔥" * round(avg)
            phase_info += f"{PHASES[phase]['description']}: {fire_emoji} ({avg:.1f}/5)\n"
        else:
            phase_info += f"{PHASES[phase]['description']}: Нет данных\n"
    
    await update.message.reply_text(
        f"📊 Статистика твоего цикла:\n\n"
        f"Всего записей: {len(energy_logs)}\n"
        f"Средний уровень энергии: {avg_energy:.1f}/5\n\n"
        f"Энергия по фазам:\n{phase_info}",
        reply_markup=get_main_menu_keyboard()
    )
    
    return MAIN_MENU

async def change_settings(update: Update, context: CallbackContext) -> int:
    """Позволяет изменить настройки цикла."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "⚙️ Настройки:\n\n"
        "Для изменения настроек используйте следующие команды:\n\n"
        "/update_period - Обновить дату последних месячных\n"
        "/update_duration - Изменить продолжительность месячных\n"
        "/update_cycle - Изменить общую длину цикла",
        reply_markup=get_main_menu_keyboard()
    )
    
    return MAIN_MENU

async def handle_menu_selection(update: Update, context: CallbackContext) -> int:
    """Обрабатывает выбор пункта главного меню."""
    user_id = update.message.from_user.id
    message_text = update.message.text
    
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    if message_text == '📊 Моя текущая фаза':
        return await show_current_phase(update, context)
    elif message_text == '🔋 Отметить уровень энергии':
        return await start_energy_log(update, context)
    elif message_text == '📝 Получить рекомендации':
        return await show_recommendations(update, context)
    elif message_text == '📅 Статистика цикла':
        return await show_cycle_statistics(update, context)
    elif message_text == '⚙️ Изменить настройки':
        return await change_settings(update, context)
    elif message_text == '🔔 Уведомления':
        return await toggle_notifications(update, context)
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из пунктов меню:",
            reply_markup=get_main_menu_keyboard()
        )
        return MAIN_MENU

async def cancel(update: Update, context: CallbackContext) -> int:
    """Отменяет и завершает разговор."""
    await update.message.reply_text(
        "Действие отменено. Для начала работы используйте /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Обработчики для изменения настроек
async def update_period_command(update: Update, context: CallbackContext) -> int:
    """Обрабатывает команду обновления даты последних месячных."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Когда начались твои последние месячные? "
        "Пожалуйста, введи дату в формате ДД.ММ.ГГГГ (например, 15.03.2025)"
    )
    return LAST_PERIOD_DATE

async def update_duration_command(update: Update, context: CallbackContext) -> int:
    """Обрабатывает команду изменения продолжительности месячных."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Сколько дней обычно длятся твои месячные? (введи число от 1 до 10)"
    )
    return PERIOD_DURATION

async def update_cycle_command(update: Update, context: CallbackContext) -> int:
    """Обрабатывает команду изменения общей длины цикла."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Какова общая длина твоего цикла (от первого дня месячных до первого дня следующих)? "
        "Обычно это от 21 до 35 дней."
    )
    return CYCLE_LENGTH

def main() -> None:
    """Запускает бота."""
    # Создаем приложение и передаем ему токен вашего бота
    application = Application.builder().token("7712191325:AAFeVf-Vk2tm0Zfm6D9EeSKsGlZ04H2QN9c").build()

    # Создаем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            LAST_PERIOD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_period_date)],
            PERIOD_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_period_duration)],
            CYCLE_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cycle_length)],
            NOTIFICATION_SETUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_notifications)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_selection)],
            ENERGY_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_energy_level)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавляем обработчики команд для изменения настроек
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("update_period", update_period_command))
    application.add_handler(CommandHandler("update_duration", update_duration_command))
    application.add_handler(CommandHandler("update_cycle", update_cycle_command))
    
    # Добавляем команду для включения/выключения уведомлений
    application.add_handler(CommandHandler("notifications", toggle_notifications))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()