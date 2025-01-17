class SpotifyException(Exception):
    def __init__(self, msg: str, code: int = 500):
        self.code = code
        self.msg = msg
        super().__init__(self.msg)