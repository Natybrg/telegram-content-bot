"""
Handlers לטיפול בהודעות מהמשתמש
קובץ זה טוען את כל ה-handlers מהקבצים הנפרדים
"""
# טעינת כל ה-handlers מהקבצים הנפרדים
from . import photo_handler
from . import audio_handler
from . import text_handlers
from . import callback_handler
from . import other_files_handler

# כל ה-handlers ייטענו אוטומטית דרך ה-imports
