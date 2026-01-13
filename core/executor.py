"""
Executor Manager
Global ThreadPool executor for the application
"""
from concurrent.futures import ThreadPoolExecutor
import atexit


class ExecutorManager:
    """
    מנהל ThreadPool גלובלי - Singleton
    מספק executor משותף לכל האפליקציה
    """
    _instance = None
    _executor = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExecutorManager, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get_executor(cls, max_workers: int = 4) -> ThreadPoolExecutor:
        """
        קבלת executor (יוצר אם לא קיים)
        
        Args:
            max_workers: מספר workers מקסימלי
            
        Returns:
            ThreadPoolExecutor instance
        """
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=max_workers)
            # רישום לסגירה אוטומטית
            atexit.register(cls.shutdown)
        return cls._executor
    
    @classmethod
    def shutdown(cls):
        """סגירת executor"""
        if cls._executor is not None:
            cls._executor.shutdown(wait=True)
            cls._executor = None


# יצירת מופע גלובלי
executor_manager = ExecutorManager()
