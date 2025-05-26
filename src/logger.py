from date_time_utils import formatted_cet_date_time


FILE_PATH = "./log.txt"
MAX_LOGGED_LINES = 1000


class Logger:
    def __init__(self) -> None:
        # Read existing lines from log file so the log
        # content can be restored after the file is
        # opened, which clears the content
        lines: list[str] = []
        try:
            with open(FILE_PATH, "r") as file:
                print("Found exisiting log file")
                lines = file.readlines()
        except OSError:
            print("No log file found, starting new one")

        self.__open_file_with_lines(lines)
        if self.__logged_lines == 0:
            self.log("Logger initialised a new log file")
        else:
            self.log(
                f"Logger intialised an existing file with {self.__logged_lines} lines"
            )

    def log(self, msg: str) -> None:
        msg_line_count = msg.count("\n") + 1

        if msg_line_count == 1:
            msg = f"{formatted_cet_date_time()} {msg}\n"
        else:
            msg = f"{formatted_cet_date_time()} ========\n{msg}\n--------\n"
            msg_line_count += 2

        self.__file.write(msg)
        self.__file.flush()
        self.__logged_lines += msg_line_count

        if self.__logged_lines >= MAX_LOGGED_LINES:
            self.__clean_log_file()

    def __clean_log_file(self) -> None:
        self.__file.seek(0)
        lines = self.__file.readlines()
        lines_length = len(lines)
        cleaned_lines = ["~~~ Log truncated to reduce log file size ~~~\n"]
        cleaned_lines_length = int(MAX_LOGGED_LINES / 2) - 1
        for i in range(lines_length - cleaned_lines_length, lines_length):
            cleaned_lines.append(lines[i])
        self.__file.close()
        self.__open_file_with_lines(cleaned_lines)

    def __open_file_with_lines(self, lines) -> None:
        self.__file = open(FILE_PATH, "w")
        self.__logged_lines = len(lines)
        for line in lines:
            self.__file.write(str(line))
