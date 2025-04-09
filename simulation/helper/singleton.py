class Singleton(type):
    """
    Metaclass that implements the singleton pattern.
    This allows direct access thorugh SingletonClass() instead of SingletonClass().getInstance().

    Usage:
    ```
    class MyClass(metaclass=Singleton):
        pass
    ```
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
