from launch import LaunchDescription

"""THIS SECTION WAS GENERATED BY zenith/shim. DO NOT MODIFY."""
# ---metadata
# name: my-launch
# ---
"""END OF GENERATED SECTION"""


from launch.actions import RegisterEventHandler, LogInfo
from launch.event_handlers import OnProcessStart
from launch_ros.actions import Node

from launch_node_definitions import map_manager_carla

"""THIS SECTION WAS GENERATED BY zenith/shim. DO NOT MODIFY."""
# ---launch_list
LAUNCH_LIST = [
    Node(package="p1", executable="e1"),
]
# ---
"""END OF GENERATED SECTION"""


def generate_launch_description():
    return LaunchDescription(
        [
            map_manager_carla,
            RegisterEventHandler(
                OnProcessStart(
                    target_action=map_manager_carla,
                    on_start=[
                        LogInfo(
                            msg="Map Manager Started... launching the rest of Navigator..."
                        ),
                        """THIS SECTION WAS GENERATED BY zenith/shim. DO NOT MODIFY."""
                        # ---launch__list_insert
                        * LAUNCH_LIST,
                        # ---
                        """END OF GENERATED SECTION""",
                    ],
                )
            ),
        ]
    )
