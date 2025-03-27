import os
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

# Фазы цикла (примерные длительности)
PHASES = {
    "менструальная": {"min_day": 1, "max_day": 5, "description": "Менструальная фаза"},
    "фолликулярная": {"min_day": 6, "max_day": 13, "description": "Фолликулярная фаза"},
    "овуляторная": {"min_day": 14, "max_day": 16, "description": "Овуляторная фаза"},
    "лютеиновая": {"min_day": 17, "max_day": 28, "description": "Лютеиновая фаза"}
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

# Ежедневные рекомендации по питанию для каждого дня цикла
DAILY_NUTRITION_TIPS = {
   # День 1-7 (Фолликулярная фаза: Восстановление энергии)
    1: "Не забудь включить в завтрак овсянку с ягодами и орехами. Это отличный источник клетчатки.",
    2: "Включай в обед зеленые овощи, чтобы пополнить запас магния.",
    3: "Не забывай об источниках железа, таких как мясо или шпинат, чтобы поддерживать уровень железа.",
    4: "Вечером съешь порцию лосося — он поможет поддержать уровень омега-3.",
    5: "Утром добавь в рацион ягоды, они помогут твоему иммунитету.",
    6: "Попробуй добавить в обед зелёные смузи с апельсином, для витамина C и антиоксидантов.",
    7: "Вечером ешь курицу с брокколи и картофелем — это отличный баланс белков и витаминов.",
    
    # День 8-14 (Овуляция: Поддержка энергии и иммунитета)
    8: "Начни утро с яичницы с авокадо — полезные жиры и белок для твоего тела.",
    9: "Включи в полдник апельсин с миндалем. Он даст тебе заряд витаминов и энергии.",
    10: "Постарайся съесть больше темных листовых овощей, чтобы поддерживать уровень фолата.",
    11: "Ужин будет легче перевариваться, если ты добавишь киноа — хороший источник углеводов.",
    12: "Сделай акцент на белок в обеде: куриная грудка с овощами.",
    13: "Утром пей смузи с ягодами — они помогают стабилизировать уровень сахара в крови.",
    14: "Вечером выбери рыбу, такую как лосось или тунец — они обеспечат твоё тело полезными омега-3 жирными кислотами.",
    
    # День 15-21 (Лютеиновая фаза: Перед ПМС)
    15: "Утром съешь смузи с бананом и шпинатом — это даст тебе энергию на весь день.",
    16: "Включи в обед орехи и сухофрукты — они обеспечат тебя полезными жирами.",
    17: "Ужин с индейкой — она богата витамином B6, который поможет снизить симптомы ПМС.",
    18: "Добавь в обед больше продуктов с клетчаткой, чтобы поддерживать стабильный уровень сахара в крови.",
    19: "Не забывай пить воду и травяные чаи для увлажнения организма.",
    20: "Вечером съешь рыбу, чтобы поддержать уровень омега-3 и витамина D.",
    21: "Включи в рацион зелёные овощи, чтобы поддерживать баланс минералов.",
    
    # День 22-28 (ПМС: Поддержка нервной системы и уменьшение воспалений)
    22: "Сегодня утром попробуй чиа-пудинг с ягодами и орехами. Омега-3 улучшат настроение.",
    23: "Уменьшай потребление сахара и кофеина, чтобы избежать нервозности.",
    24: "Пей много воды, чтобы уменьшить вздутие живота и удержание жидкости.",
    25: "Ужин с рыбой, особенно с жирными сортами, такими как лосось, для борьбы с воспалениями.",
    26: "Включи в обед банан — он поможет снизить уровень стресса и улучшить настроение.",
    27: "Сегодня можно побаловать себя темным шоколадом. Он богат магнием, который поможет справиться с ПМС.",
    28: "Заверши день лёгким ужином с овощами и белком, чтобы не перегружать пищеварение."
}

def main():
    """Запуск бота."""
    # Получаем токен из переменных окружения
    token = '7712191325:AAFeVf-Vk2tm0Zfm6D9EeSKsGlZ04H2QN9c'
    
    if not token:
        logger.error("Токен Telegram бота не найден. Установите переменную окружения TELEGRAM_BOT_TOKEN")
        return
    
    # Создаем Application и передаем токен
    application = Application.builder().token(token).build()
    
    # Настройка обработчика разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            LAST_PERIOD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_period_date)],
            PERIOD_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_period_duration)],
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_selection)
            ],
            ENERGY_LEVEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_energy_level)
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda update, context: ConversationHandler.END)],
    )
    
    # Добавляем обработчики команд
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('show_phase', show_current_phase))
    application.add_handler(CommandHandler('recommendations', show_recommendations))
    application.add_handler(CommandHandler('nutrition_tip', show_today_nutrition_tip))
    application.add_handler(CommandHandler('energy_stats', show_cycle_statistics))
    application.add_handler(CommandHandler('settings', change_settings))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    # Выбор между polling и webhook
    webhook_url = "https://bloom-app-6dm1.onrender.com/bot7712191325:AAFeVf-Vk2tm0Zfm6D9EeSKsGlZ04H2QN9c"
    if webhook_url:
        # Настройка webhook
        logger.info(f"Запуск бота с webhook на {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=f"bot{token}",
            webhook_url=f"{webhook_url}/bot{token}"
        )
    else:
        # Запуск в режиме polling (как сейчас)
        logger.info("Бот запущен в режиме polling. Нажмите Ctrl+C для остановки.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def error_handler(update: object, context: CallbackContext):
    """Обработчик ошибок."""
    logger.error(f"Произошла ошибка: {context.error}")
    
    # Если есть обновление и это сообщение, пытаемся отправить сообщение об ошибке
    if update and hasattr(update, 'message'):
        try:
            update.message.reply_text(
                "Упс! Что-то пошло не так. Попробуйте снова или перезапустите бота командой /start"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

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
    """Сохраняет продолжительность и переходит в главное меню."""
    user_id = update.message.from_user.id
    
    try:
        duration = int(update.message.text)
        if duration < 1 or duration > 10:
            await update.message.reply_text(
                "Пожалуйста, введи число от 1 до 10."
            )
            return PERIOD_DURATION
        
        user_data_dict[user_id]['period_duration'] = duration
        user_data_dict[user_id]['cycle_length'] = 28  # Средняя длина цикла по умолчанию
        user_data_dict[user_id]['energy_logs'] = []
        
        # Рассчитываем следующие месячные
        next_period = user_data_dict[user_id]['last_period_date'] + timedelta(days=user_data_dict[user_id]['cycle_length'])
        user_data_dict[user_id]['next_period_date'] = next_period
        
        # Отправляем сообщение с данными и переходим в главное меню
        await update.message.reply_text(
            f"Спасибо за информацию, {user_data_dict[user_id]['name']}!\n\n"
            f"Возраст: {user_data_dict[user_id]['age']}\n"
            f"Дата последних месячных: {user_data_dict[user_id]['last_period_date'].strftime('%d.%m.%Y')}\n"
            f"Продолжительность: {user_data_dict[user_id]['period_duration']} дней\n"
            f"Ожидаемая дата следующих месячных: {next_period.strftime('%d.%m.%Y')}\n\n"
            "Теперь я могу отслеживать твой цикл и давать рекомендации!",
            reply_markup=get_main_menu_keyboard()
        )
        
        # Отправляем первую ежедневную рекомендацию
        current_day = calculate_cycle_day(user_data_dict[user_id])
        await send_daily_nutrition_tip(update, context, user_id, current_day)
        
        return MAIN_MENU
    
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введи продолжительность числом."
        )
        return PERIOD_DURATION

def get_main_menu_keyboard():
    """Создает клавиатуру главного меню."""
    keyboard = [
        ['📊 Моя текущая фаза', '🔋 Отметить уровень энергии'],
        ['📝 Получить рекомендации', '🍎 Совет по питанию на сегодня'],
        ['📅 Статистика цикла', '⚙️ Изменить настройки']
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

def determine_phase(day, period_duration):
    """Определяет текущую фазу цикла."""
    if 1 <= day <= period_duration:
        return "менструальная"
    elif period_duration < day <= 13:
        return "фолликулярная"
    elif 14 <= day <= 16:
        return "овуляторная"
    else:
        return "лютеиновая"

async def show_current_phase(update: Update, context: CallbackContext) -> int:
    """Показывает информацию о текущей фазе цикла."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    user_data = user_data_dict[user_id]
    current_day = calculate_cycle_day(user_data)
    current_phase = determine_phase(current_day, user_data['period_duration'])
    
    days_to_next_period = user_data['cycle_length'] - current_day + 1
    
    # Предупреждение о скорых месячных
    warning_message = ""
    if days_to_next_period <= 3 and current_phase == "лютеиновая":
        warning_message = "\n\n⚠️ Твои месячные начнутся примерно через " + \
                         f"{days_to_next_period} {'день' if days_to_next_period == 1 else 'дня' if 2 <= days_to_next_period <= 4 else 'дней'}. " + \
                         "Не забудь взять с собой прокладки или тампоны!"
    
    await update.message.reply_text(
        f"📊 Твой текущий статус цикла:\n\n"
        f"🗓️ День цикла: {current_day} из {user_data['cycle_length']}\n"
        f"🌀 Фаза: {PHASES[current_phase]['description']}\n"
        f"📅 Следующие месячные ожидаются через {days_to_next_period} " + 
        f"{'день' if days_to_next_period == 1 else 'дня' if 2 <= days_to_next_period <= 4 else 'дней'}" +
        warning_message,
        reply_markup=get_main_menu_keyboard()
    )
    
    return MAIN_MENU

async def send_daily_nutrition_tip(update: Update, context: CallbackContext, user_id, day=None):
    """Отправляет ежедневный совет по питанию."""
    if day is None:
        day = calculate_cycle_day(user_data_dict[user_id])
    
    # Получаем совет для текущего дня цикла
    cycle_day = (day - 1) % 28 + 1  # Преобразуем день в диапазон 1-28
    nutrition_tip = DAILY_NUTRITION_TIPS.get(cycle_day, "Ешь больше свежих фруктов и овощей сегодня!")
    
    current_phase = determine_phase(day, user_data_dict[user_id]['period_duration'])
    phase_name = PHASES[current_phase]['description']
    
    await update.message.reply_text(
        f"🍎 Твой совет по питанию на сегодня (день {day}, {phase_name.lower()}):\n\n"
        f"{nutrition_tip}",
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
        
        await update.message.reply_text(
            f"Спасибо! Я записал твой уровень энергии: {message_text}\n"
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
    current_phase = determine_phase(current_day, user_data['period_duration'])
    
    recommendations = RECOMMENDATIONS[current_phase]
    
    await update.message.reply_text(
        f"📝 Рекомендации для {PHASES[current_phase]['description'].lower()} (день {current_day}):\n\n"
        f"🍽️ Питание:\n{recommendations['питание']}\n\n"
        f"🏃‍♀️ Физическая активность:\n{recommendations['физическая_нагрузка']}\n\n"
        f"🧠 Ментальное состояние:\n{recommendations['ментальное_состояние']}",
        reply_markup=get_main_menu_keyboard()
    )
    
    return MAIN_MENU

async def show_today_nutrition_tip(update: Update, context: CallbackContext) -> int:
    """Показывает совет по питанию на сегодня."""
    user_id = update.message.from_user.id
    if user_id not in user_data_dict:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь, используя команду /start")
        return ConversationHandler.END
    
    return await send_daily_nutrition_tip(update, context, user_id)

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
        phase = determine_phase(day, user_data['period_duration'])
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
        "/update_cycle - Изменить общую длину цикла (по умолчанию 28 дней)",
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
    elif message_text == '🍎 Совет по питанию на сегодня':
        return await show_today_nutrition_tip(update, context)
    elif message_text == '📅 Статистика цикла':
        return await show_cycle_statistics(update, context)
    elif message_text == '⚙️ Изменить настройки':
        return await change_settings(update, context)
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из пунктов меню:",
            reply_markup=get_main_menu_keyboard()
        )
        return
# - start
# - get_name
# - get_age
# - get_last_period_date
# - get_period_duration
# - get_main_menu_keyboard
# - get_energy_level_keyboard
# - calculate_cycle_day
# - determine_phase
# - show_current_phase
# - send_daily_nutrition_tip
# - start_energy_log
# - log_energy_level
# - show_recommendations
# - show_today_nutrition_tip
# - show_cycle_statistics
# - change_settings
# - handle_menu_selection

# Копируем все эти функции из оригинального кода без каких-либо изменений
# Функции остаются точно такими же, как в оригинальном файле telbot.py

if __name__ == '__main__':
    main()