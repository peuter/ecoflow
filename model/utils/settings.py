class Settings:
    __conf = {
        "args": {}
    }
    __setters = ["args"]

    @staticmethod
    def config(name):
        return Settings.__conf[name]
    
    def arg(arg):
        args = Settings.__conf["args"]
        return getattr(args, arg)

    @staticmethod
    def set(name, value):
        if name in Settings.__setters:
            Settings.__conf[name] = value
        else:
            raise NameError("Name not accepted in set() method")