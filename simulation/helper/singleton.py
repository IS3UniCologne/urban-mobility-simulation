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

    _instances = {}  # noqa: RUF012

    def __call__(cls, *args, **kwargs):  # noqa: ANN002, ANN003, ANN204
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)  # noqa: UP008
        return cls._instances[cls]
