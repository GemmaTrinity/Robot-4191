# General imports
import numpy as np
import time
import math
# Ros imports
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Path, Odometry
from std_msgs.msg import Int16, Bool


# Script imports
from Utils.utils import from_odometry
from Utils.utils import Motor


class CONTROLLER(Node):
    '''
    Aim:
    - Travel to waypoints by getting pose and path and driving motors
    Subscribes:
    - /robot/odom: Odometry
    - (Path): Added later
    Publishes:
    - ... Nothing?
    '''

    def __init__(self):
        super().__init__('controller')
        #Publish that first waypoint has been reached
        self.publisher_1 = self.create_publisher(Bool, '/Controller/msg', 10)
        timer_period = 0.05  # 0.05 seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)

        # Instantiate objects
        self.sub_odom = self.create_subscription(Odometry, '/robot/odom', self.listener_callback, 10)
        self.sub_odom  # prevent unused variable warning
        self.sub_map = self.create_subscription(Path, '/SAM/path', self.get_path, 10)
        self.sub_map
        # self.sub_turn = self.create_subscription(Int16, '/SAM/turn', self.turn_callback, 10)
        # self.sub_turn
        self.sub_goal = self.create_subscription(Path, '/Controller/goal', self.get_goal, 10)
        self.sub_goal
        self.motor_right = Motor(22, 23)
        self.motor_left = Motor(27, 24)

        # Functions
        self.dist_between_points = lambda pose, goal: math.dist(pose, goal)
        self.angle_between_points = lambda pose, goal: np.arctan2(goal[1] - pose[1], goal[0] - pose[0])

        # Variables
        self.pose = [0., 0., 0.]  # x, y, theta
        self.goal = [0., 0.]  # x, y
        self.state = {'Turn': 0}
        #self.waypoints = [[0.2, 0.2], [0.2 ,0.45], [0.40, 0.45], [0.2, 0.2], [0.4, 0.2], [0.3, 0.45], [0.3, 0], [0, 0]]
        self.waypoints = []

        # Params
        self.dist_from_goal = 0.05
        self.max_angle = np.pi / 18  # Maximum offset angle from goal before correction
        self.min_angle = self.max_angle * 0.5  # Maximum offset angle from goal after correction
        self.look_ahead = 0.4 # How far ahead to look before finding a waypoint
        self.i = 0
        self.turn = 0
        self.waypoint_reached = False

    def timer_callback(self):
        #message turns to True when waypoint_reached is True
        msg = self.waypoint_reached
        self.publisher_1.publish(msg)

    def turn_callback(self, msg):
        self.turn = msg.data
        
    def read_waypoints(self, msg):
        self.waypoints = []
        for waypoint in msg.poses:
            self.waypoints.append([waypoint.pose.position.x, waypoint.pose.position.y])
            
    def get_path(self, msg):
        #goal_x, goal_y = input('Enter destination: x, y').split()
        #goal_x, goal_y = [float(goal_x),float(goal_y)]
        #testing multiple waypoints now, then waypoints will be individually found via ROS
        self.read_waypoints(msg)
        while(len(self.waypoints) > 1 and self.dist_between_points(self.pose[:2], self.waypoints[0]) < self.look_ahead):
            print('way len', len(self.waypoints))
            self.waypoints.pop(0)    

        self.goal = self.waypoints[0]
    def get_goal(self, msg):
        self.goal = [msg.pose.position.x, pose.position.y]

    def main(self):
        '''
        Aim: take in waypoint, travel to waypoint
        '''
        #while True:
        
        angle_to_rotate = self.calculate_angle_from_goal()
        dist_to_goal = self.dist_between_points(self.pose[:2], self.goal)
        print(self.pose[0], self.pose[1], math.degrees(self.pose[2]))
        print('Dist2Goal: {:.3f} || Ang2Goal: {:.3f}'.format(dist_to_goal, math.degrees(angle_to_rotate)))
        if dist_to_goal > self.dist_from_goal:
            # Check if we need to rotate or drive straight
            if (self.state['Turn'] == 0 and abs(angle_to_rotate) > self.max_angle) or self.state['Turn'] == 1:
                # Drive curvy
                self.state['Turn'] = 1
                if abs(angle_to_rotate) < self.min_angle:
                    self.state['Turn'] = 0
                self.drive(ang_to_rotate=angle_to_rotate)
            elif self.state['Turn'] == 0:
                # Drive straight
                self.drive(ang_to_rotate=0)
            else:
                print('BOI YO DRIVING BE SHITE', self.state['Turn'], angle_to_rotate)
        else:
            # Waypoint reached
            if len(self.waypoints) == 1 or len(self.waypoints) == 0:
                # Destination reached
                print('Goal achieved')
                self.drive(0, 0)  # Stops robot
                #10 second pause until next waypoint
                time.sleep(10)
                self.waypoint_reached = True
            else:
                #look for next waypoint
                self.waypoints.pop(0)
                self.goal = self.waypoints[0]

    def listener_callback(self, msg):
        odom = from_odometry(msg)
        self.pose = [odom['x'], odom['y'], odom['theta']]
        self.main()

    def calculate_angle_from_goal(self):
        angle_to_rotate = self.angle_between_points(self.pose, self.goal) - self.pose[2]
        # Ensures minimum rotation
        if angle_to_rotate < -np.pi:
            angle_to_rotate += 2 * np.pi
        if angle_to_rotate > np.pi:
            angle_to_rotate -= 2 * np.pi
        return angle_to_rotate

    def drive(self, ang_to_rotate=0, value=0.5):
        curve = 0.1
        direction = np.sign(ang_to_rotate)
        if self.turn != 0 and abs(ang_to_rotate) > 1.5 and self.turn != direction:
            direction = direction *-1
        if value == 0:
            # Stop the robot
            self.motor_left.stop()
            self.motor_right.stop()
        elif direction == 1:
            # Turn right
            if abs(ang_to_rotate) < curve:
                self.motor_left.forward(value)
                self.motor_right.forward(0)
            else:
                self.motor_left.backward(value)
                self.motor_right.forward(value)
        elif direction == -1:
            # Turn left
            if abs(ang_to_rotate) < curve:
                self.motor_left.forward(0)
                self.motor_right.forward(value)
            else:
                self.motor_left.forward(value)
                self.motor_right.backward(value)
        elif direction == 0:
            # Drive forwards
            self.motor_left.forward(value)
            self.motor_right.forward(value)
        else:
            print('BOI YO TURNING IS SHITE', direction)

def main(args=None):
    rclpy.init(args=args)

    controller = CONTROLLER()
    rclpy.spin(controller)

    controller.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
