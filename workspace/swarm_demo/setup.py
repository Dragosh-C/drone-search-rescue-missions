import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'swarm_demo'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*.urdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='Simple ROS 2 drone swarm demo',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'swarm_controller = swarm_demo.swarm_controller:main',
            'drone_mission = swarm_demo.drone_mission:main',
	    'zigzag_mission = swarm_demo.zigzag_mission:main',
	    'target_detector = swarm_demo.target_detector:main',
	    'yolo_detector = swarm_demo.yolo_detector:main',
        ],
    },
)
