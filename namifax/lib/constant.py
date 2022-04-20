class Constants:
    constant_dict = {}
    local_config = None

    def add(self, name, value):
        if name not in self.constant_dict:
            self.constant_dict[name] = self.local_config.get(name, value)

    def __getattr__(self, item):
        if item in self.constant_dict.keys():
            return self.constant_dict.get(item)
        else:
            return self.local_config.get(item)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Constants, cls).__new__(cls)
            cls.instance.local_config = args[0] if args else {}

        return cls.instance

    def __dir__(self):
        return tuple(self.constant_dict.keys())
