class Logger:
    def __init__(self):
        return

    def log(self, level: str, message: str):
        match level:
            case "error":
                color = "\033[91m"
            case "info":
                color = "\033[94m"
            case "debug":
                color = "\033[92m"
            case "warning":
                color = "\033[93m"
            case _:
                color = "\033[90m"
        print(f"{color}[{level.upper()}]\033[0m: {message}")

    def error(self, message: str):
        self.log("error", message)

    def info(self, message: str):
        self.log("info", message)

    def debug(self, message: str):
        self.log("debug", message)

    def warning(self, message: str):
        self.log("warning", message)


logging = Logger()