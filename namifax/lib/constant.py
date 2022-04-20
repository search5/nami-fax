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
        stored_keys = list(self.constant_dict.keys())
        merge_keys = stored_keys[:]

        for item in self.local_config:
            if item not in stored_keys:
                merge_keys.append(item)

        return merge_keys
