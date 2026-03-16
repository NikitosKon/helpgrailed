import json
from datetime import datetime

def format_datetime(dt_str):
    """Форматирование даты для отображения"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return dt_str

def safe_json_loads(data, default=None):
    """Безопасная загрузка JSON"""
    try:
        return json.loads(data) if data else default
    except:
        return default