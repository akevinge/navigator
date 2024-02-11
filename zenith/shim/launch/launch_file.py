from __future__ import annotations
import json

from . import edit_buffer

IMPORT_LIST = [
    "from launch import LaunchDescription",
    "from launch.actions import RegisterEventHandler, LogInfo",
    "from launch.event_handlers import OnProcessStart",
    "from launch_ros.actions import Node",
]
GENERATED_SECTION_HEADER = "\"\"\"THIS SECTION WAS GENERATED BY zenith/shim. DO NOT MODIFY.\"\"\""
END_OF_GENERATED_SECTION = "\"\"\"END OF GENERATED SECTION\"\"\""
MARKER = "# ---"
METADATA_MARKER = "metadata"
LAUNCH_LIST_MARKER = "launch_list"
LAUNCH_LIST_INSERT_MARKER = "launch__list_insert"

class LaunchFileNode:
    def __init__(self, package: str, executable: str):
        self.package = package
        self.executable = executable
    
    def __eq__(self, o: object) -> bool:
        return o.package == self.package and o.executable == self.executable

    def __hash__(self) -> int:
        return hash(self.package + self.executable)
    
    def __str__(self):
        return f"Node(package='{self.package}', executable='{self.executable}')"
    
    @staticmethod
    def help() -> str:
        return "LaunchFileNode JSON format: { \"package\": \"control\", \"executable\": \"some_executable\" }"
    
    @classmethod
    def from_json(cls, data: dict[str, str]) -> LaunchFileNode | None:
        """Attempts to create LaunchFileNode from JSON object. JSON object should have all properties of class."""
        return cls(data["package"], data["executable"])
    
    @classmethod
    def from_string(cls, str: str) -> LaunchFileNode | None:
        """Attempts to parse a LaunchFileNode from a string. If the string is invalid, returns None.
        
        Example input:
        Node(package='joy_translation', executable='joy_translation_node')
        """
        try:
            package_arg, executable_arg = str.split(",")
            package = package_arg.split("=")[1].strip("'\"\n() ")
            executable = executable_arg.split("=")[1].strip("'\"\n() ")
            return cls(package, executable)
        except (IndexError, ValueError):
            return None
    
class Metadata:
    def __init__(self, name: str = "") -> None:
        self.name = name
    
    def set_name(self, name: str):
        self.name = name
    
    @staticmethod
    def help() -> str:
        return "Metadata json format: { \"name\": \"my_launch_file\" }"
    
    @classmethod
    def from_json(cls, data: dict[str, str]):
        return cls(name=data["name"])
    
    @classmethod
    def from_string(cls, str: str) -> Metadata | None:
        """Attempts to parse metadata section from a string.

        If metadata section is invalid, returns an empty Metadata object.
        
        Example input:
        name: my_launch_file
        """

        value_map: dict[str, str] = dict()

        for line in str.split("\n"):
            if line.strip() == "":
                continue
            try:
                key, value = line.split(":")
            except ValueError: # If the line is malformed. 
                continue
            value_map[key.strip()] = value.strip()

        try:
            obj = cls(name=value_map["name"])
            return obj
        except KeyError:
            return None
        


class LaunchFileBuffer:
    def __init__(self, contents: str):
        self.buffer = edit_buffer.EditBuffer(contents)

    def valid(self) -> bool:
        """Validates the file to ensure it is a valid launch file.
        All valid launch files must contain the following:
        - Valid imports
        - A metadata section
        - A launch list
        - A launch list insert
        """

        return all(imp in self.buffer for imp in IMPORT_LIST) and all(
            marker in self.buffer
            for marker in [
                METADATA_MARKER,
                LAUNCH_LIST_MARKER,
                LAUNCH_LIST_INSERT_MARKER,
            ]
        )

    def generate_file(self, metadata: Metadata, nodes: list[LaunchFileNode]) -> str:
        self._ensure_metadata(metadata)
        self._ensure_imports()
        self._inject_launch_list(nodes)
        self._inject_launch_list_insert()
        return str(self.buffer)
    
    def _ensure_metadata(self, metadata: Metadata):
        """Ensures that the metadata section is present in the launch file. If the metadata section is missing, it is created. If the metadata section is present, it is updated.
        """
        if METADATA_MARKER not in self.buffer:
            self.buffer.jump_to_start()
            self.buffer.skip_lines(2)
            self.buffer.new_line(GENERATED_SECTION_HEADER)
            self.buffer.new_line(MARKER + METADATA_MARKER)
            # Insert the metadata.
            for k, v in metadata.__dict__.items():
                self.buffer.new_line(f"# {k}: {v}")
            self.buffer.new_line(MARKER)
            self.buffer.new_line(END_OF_GENERATED_SECTION)
        else:
            self.buffer.jump_to(METADATA_MARKER)
            self.buffer.skip_line() # Skip the marker line.
            self.buffer.delete_until(MARKER) # Delete the old metadata.
             # Insert the new metadata.
            for k, v in metadata.__dict__.items():
                self.buffer.new_line(f"# {k}: {v}")

    def _ensure_imports(self):
        """Ensures that all necessary imports are present in the launch file."""
        self.buffer.jump_to_start()
        # Jump to end of first generated section, which should be
        # the metadata section.
        self.buffer.jump_to_relative(END_OF_GENERATED_SECTION)
        # Skip this line and create a new empty line.
        self.buffer.skip_line()
        self.buffer.new_line()

        # Save the current position to write the section header later.
        write_start = self.buffer.get_position()
        inserted_line = False
        for imp in IMPORT_LIST:
            if imp not in self.buffer:
                self.buffer.new_line(imp)
                inserted_line = True
        
        # If no lines were inserted, skip header/footer generation.
        if not inserted_line:
            return

        # Insert the generated section header and footer.
        self.buffer.new_line(END_OF_GENERATED_SECTION)
        section_end = self.buffer.get_position()

        self.buffer.set_position(write_start)
        self.buffer.new_line(GENERATED_SECTION_HEADER)

        # Restore the position to the end of the section.
        self.buffer.set_position(section_end + len(GENERATED_SECTION_HEADER))

    def _inject_launch_list(self, nodes: list[LaunchFileNode]):
        if LAUNCH_LIST_MARKER in self.buffer:
            self.buffer.jump_to(LAUNCH_LIST_MARKER)
            # Skip the marker.
            self.buffer.skip_line()
            # Delete old launch list by deleting until the closing marker.
            self.buffer.delete_until(MARKER)
            # Insert new launch list.
            launch_list = self.generate_launch_list(nodes)
            self.buffer.new_line(launch_list)
        else:
            self.buffer.jump_to("generate_launch_description")
            self.buffer.skip_line_back()

            self.buffer.new_line()
            self.buffer.new_line()
            self.buffer.new_line(GENERATED_SECTION_HEADER)
            self.buffer.new_line(MARKER + LAUNCH_LIST_MARKER)

            launch_list = self.generate_launch_list(nodes)
            self.buffer.new_line(launch_list)

            self.buffer.new_line(MARKER)
            self.buffer.new_line(END_OF_GENERATED_SECTION)
    
    def _inject_launch_list_insert(self):
        if LAUNCH_LIST_INSERT_MARKER in self.buffer:
            self.buffer.jump_to(LAUNCH_LIST_INSERT_MARKER)
            # Skip the marker.
            self.buffer.skip_line()
            # Delete old launch list by deleting until the closing marker.
            self.buffer.delete_until(MARKER)
            # Insert new launch list.
            self.buffer.new_line("*LAUNCH_LIST,")
        else:
            # Jump to the end of the ProcessStart event handler on_start array.
            self.buffer.jump_to("on_start")
            self.buffer.jump_to_relative("]")

            self.buffer.new_line(GENERATED_SECTION_HEADER)
            self.buffer.new_line(MARKER + LAUNCH_LIST_INSERT_MARKER)

            self.buffer.new_line("*LAUNCH_LIST,")

            self.buffer.new_line(MARKER)
            self.buffer.new_line(END_OF_GENERATED_SECTION)

    def generate_launch_list(self, nodes: list[LaunchFileNode]):
        code = "LAUNCH_LIST = [\n"

        for node in nodes:
            code += f"""    {node},\n"""
        code += "]"
        return code

    def __str__(self):
        return str(self.buffer)
    


class LaunchFileFromExisting(LaunchFileBuffer):
    def __init__(self, contents: str) -> None:
        super().__init__(contents)
        self.metadata = self.read_metadata()
        self.nodes = self.read_launch_list()
    
    def generate_file(self):
        return super().generate_file(self.metadata, self.nodes)

    def read_metadata(self) -> Metadata | None:
        """Reads the metadata section from the launch file. If the metadata section is invalid (i.e missing or malformed), returns None.
        """
        try:
            self.buffer.jump_to(METADATA_MARKER)
            self.buffer.skip_line() # Skip marker line
            raw_metadata = self.buffer.read_until(MARKER) # Read until the end of the metadata section.
            raw_metadata = raw_metadata.strip("#") # Strip the comment character.
            return Metadata.from_string(raw_metadata)
        except ValueError:
            return None
    
    def read_launch_list(self) -> list[LaunchFileNode] | None:
        """Reads the launch list from the launch file. If the launch list is invalid (i.e missing or malformed), returns None.
        """
        try:
            self.buffer.jump_to(LAUNCH_LIST_MARKER)
            self.buffer.skip_line() # Skip marker line.
            self.buffer.jump_to("[")
            raw_launch_list = self.buffer.read_until(MARKER) # Read until the end of the launch list.
            raw_launch_list = raw_launch_list.strip("[]\n ") # Strip brackets and whitespace.
            raw_nodes = raw_launch_list.split(")")
            return [LaunchFileNode.from_string(raw_node) for raw_node in raw_nodes if raw_node.strip() != ""]
        except ValueError:
            return None
        
    def to_json(self) -> str:
        data = { 
            "metadata": self.metadata.__dict__,
            "nodes": [{
                "package": node.package,
                "executable": node.executable
            } for node in self.nodes]
        }
        return json.dumps(data, indent=4)
    
class LaunchFileBuilder(LaunchFileBuffer):
    def __init__(self, contents: str) -> None:
        super().__init__(contents)
        self.metadata: Metadata | None = None
        self.nodes: list[LaunchFileNode] | None = None
    
    def set_metadata(self, metadata: Metadata) -> LaunchFileBuilder:
        self.metadata = metadata
        return self
    
    def set_nodes(self, nodes: list[LaunchFileNode]) -> LaunchFileBuilder:
        self.nodes = nodes
        return self
    
    def generate_file(self):
        return super().generate_file(self.metadata, self.nodes)
    
    
class LaunchFile(LaunchFileBuffer):
    def __init__(self, contents: str) -> None:
        super().__init__(contents)
    
    def edit(self) -> type[LaunchFileBuilder] | type[LaunchFileFromExisting]:
        if self.valid():
            return LaunchFileFromExisting
        else:
            return LaunchFileBuilder
