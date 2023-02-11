from setuptools import setup
from glob import glob
import os

package_name = 'mcu_interface'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name), glob('launch/*.launch.py'))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nova at UT Dallas',
    maintainer_email='project.nova@utdallas.edu',
    description='See package.xml',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mcu_interface_node = mcu_interface.mcu_interface_node:main'
        ],
    },
)
