class EditBuffer:
    def __init__(self, contents: str):
        self.contents = contents 
        self.position = 0
    
    def get_position(self) -> int:
        return self.position

    def set_position(self, cursor: int):
        self.position = cursor
    
    def write(self, str: str):
        """Writes a string to the buffer at the current position. If the position is at the end of the buffer, the string is appended."""
        if self.position == len(self.contents):
            self.contents += str
        else:
            self.contents = self.contents[:self.position] + str + self.contents[self.position:]

        self.position += len(str)

    def delete_until(self, str: str):
        """Deletes from the current position in the buffer until the first occurrence of str. If str is not found, the buffer is not modified."""
        try:
            index = self.position + self.contents[self.position:].index(str)
        except ValueError:
            return

        self.contents = self.contents[:self.position] + self.contents[index:]
    
    def read_until(self, str: str) -> str:
        """Reads from the current position in the buffer until the first occurrence of str. If str is not found, the buffer is not modified."""
        try:
            index = self.position + self.contents[self.position:].index(str)
        except ValueError:
            return ""
        
        result = self.contents[self.position:index]
        self.position = index
        return result
    
    def skip_lines(self, n: int):
        """Skips n lines in the buffer. If the buffer is at the end, the position is not changed."""
        for _ in range(n):
            if not self.eof():
                self.skip_line()
    
    def skip_line(self):
        """Skips the current line in the buffer. If the buffer is at the end, the position is not changed."""
        while not self.eof() and self.contents[self.position] != "\n":
            self.position += 1
        self.position += 1
    
    def skip_line_back(self):
        """Skips the current line in the buffer and moves backwards. If the buffer is at the start, the position is not changed."""
        while self.position > 0 and self.contents[self.position] != "\n":
            self.position -= 1
        self.position -= 1
    
    def jump_to_start(self):
        self.position = 0
    
    def eof(self) -> bool:
        return self.position >= len(self.contents)
    
    def new_line(self, str: str = ""):
        self.contents = self.contents[:self.position] + str + "\n" + self.contents[self.position:]
        self.position += len(str) + 1
    
    def jump_to(self, str: str):
        try:
            self.position = self.contents.index(str)
        except ValueError:
            return
    
    def jump_to_relative(self, str: str):
        try:
            self.position += self.contents[self.position:].index(str)
        except ValueError:
            return
    
    def __contains__(self, str: str):
        return str in self.contents
    
    def __str__(self) -> str:
        return self.contents
    