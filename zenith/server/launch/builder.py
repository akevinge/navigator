from __future__ import annotations
import os

from .launch_file import LaunchFileBuffer, LaunchFileNode, Metadata
from .template import LAUNCH_FILE_TEMPLATE


class InitException(Exception):
    pass


class BuildException(Exception):
    pass


class UnableToOverwrite(Exception):
    pass


class LaunchFileBuilder:
    def __init__(self, path: str, overwrite: bool = False):
        self.path = path

        try:
            if not os.path.exists(path):
                self.buffer = LaunchFileBuffer(LAUNCH_FILE_TEMPLATE)
                self.metadata = Metadata()
                self.nodes = []
            else:
                if not overwrite:
                    raise UnableToOverwrite(
                        "Launch already exists, consider using an overwriteable method"
                    )
                file = open(path, "r")
                self.buffer = LaunchFileBuffer(file.read())
                self.metadata = self.buffer._read_metadata()
                self.nodes = self.buffer._read_launch_list()
                file.close()
        except UnableToOverwrite as e:
            raise e
        except Exception as e:
            raise InitException(
                f"Failed to initialize launch file from path: {path}"
            ) from e

    def set_metadata(self, metadata: Metadata) -> LaunchFileBuilder:
        self.metadata = metadata
        return self

    def add_node(self, node: LaunchFileNode) -> LaunchFileBuilder:
        self.nodes.append(node)
        return self

    def remove_node(self, node: LaunchFileNode) -> LaunchFileBuilder:
        self.nodes.remove(node)
        return self

    def set_nodes(self, nodes: list[LaunchFileNode]) -> LaunchFileBuilder:
        self.nodes = nodes
        return self

    def build(self) -> None:
        try:
            file = open(self.path, "wt")
            file.write(self.buffer.generate_file(self.metadata, self.nodes))
            file.close()
        except Exception as e:
            raise BuildException("Failed to build launch file") from e
