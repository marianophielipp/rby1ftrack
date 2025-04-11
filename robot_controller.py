import argparse
import socket
import struct
import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtWidgets, QtCore
import rby1_sdk as rby
import math

# Function to control the physical robot
def control_robot(ip, port):
    robot = rby.create_robot(f"{ip}:50051", "a")
    robot.connect()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))

    print(f"[Robot Controller] Listening on UDP port {port}")
    print(f"[Robot Controller] Connected to RB-Y1 at {ip}")

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            pan_angle, tilt_angle = struct.unpack('ff', data)
            print(f"[RECV] PAN: {pan_angle:.2f}°, TILT: {tilt_angle:.2f}°")
            robot.set_joint_position("head_0", pan_angle)
            robot.set_joint_position("head_1", tilt_angle)
        except Exception as e:
            print(f"[ERROR] {e}")

# Function to visualize the virtual head
def visualize_head(port):
    # Create the application and view
    app = QtWidgets.QApplication([])
    view = gl.GLViewWidget()
    view.setWindowTitle('Virtual Head Visualization')
    view.setGeometry(100, 100, 800, 600)
    view.setCameraPosition(distance=5, elevation=15, azimuth=30)
    view.show()

    # Add a grid for reference
    grid = gl.GLGridItem()
    view.addItem(grid)

    # ---- Head (a sphere of radius 1) ----
    head = gl.GLMeshItem(
        meshdata=gl.MeshData.sphere(rows=20, cols=40, radius=1.0),
        smooth=True, color=(1, 0.8, 0.7, 1), shader='shaded'
    )
    view.addItem(head)

    # ---- Neck (a cylinder) ----
    # We keep the neck fixed (vertical) by only translating it downward.
    neck = gl.GLMeshItem(
        meshdata=gl.MeshData.cylinder(rows=10, cols=20, radius=[0.3, 0.3], length=1.5),
        smooth=True, color=(0.7, 0.7, 0.7, 1), shader='shaded'
    )
    neck.resetTransform()
    neck.translate(0, 0, -1.5)
    view.addItem(neck)

    # ---- Eyes ----
    # First, we compute eye offsets using spherical coordinates.
    # Original values: theta = arccos(0.8) ~36.87° would put the eyes near the top.
    # To lower the eyes, we use theta = 45°.
    theta = math.radians(30)        # 45°: sin(45)=0.7071, cos(45)=0.7071.
    phi_left = math.radians(150)      # left eye (should yield a negative x, positive y)
    phi_right = math.radians(30)      # right eye
    r_val = 1.0
    left_eye_offset = np.array([
        r_val * math.sin(theta) * math.cos(phi_left),
        r_val * math.sin(theta) * math.sin(phi_left),
        r_val * math.cos(theta)
    ])
    right_eye_offset = np.array([
        r_val * math.sin(theta) * math.cos(phi_right),
        r_val * math.sin(theta) * math.sin(phi_right),
        r_val * math.cos(theta)
    ])
    # For reference, these should be roughly:
    #   left_eye_offset  ≈ [ -0.612,  0.354,  0.707 ]
    #   right_eye_offset ≈ [  0.612,  0.354,  0.707 ]
    eye_offsets = np.array([left_eye_offset, right_eye_offset])
    eye_radius = 0.07

    left_eye = gl.GLMeshItem(
        meshdata=gl.MeshData.sphere(rows=10, cols=20, radius=eye_radius),
        color=(0, 0, 0, 1), smooth=True, shader='shaded'
    )
    right_eye = gl.GLMeshItem(
        meshdata=gl.MeshData.sphere(rows=10, cols=20, radius=eye_radius),
        color=(0, 0, 0, 1), smooth=True, shader='shaded'
    )
    view.addItem(left_eye)
    view.addItem(right_eye)

    # ---- UDP Socket Setup ----
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)  # non-blocking so update() can be called repeatedly
    sock.bind(("0.0.0.0", port))

    # ---- Update Function ----
    def update():
        try:
            data, _ = sock.recvfrom(1024)
            pan_angle, tilt_angle = struct.unpack('ff', data)
            # Convert angles to radians
            pan = np.radians(pan_angle)
            tilt = np.radians(tilt_angle)
            print(f"[UPDATE] PAN: {pan_angle:.2f}°, TILT: {tilt_angle:.2f}°")

            # Compute combined rotation matrix: R = Ry * Rx
            Rx = np.array([
                [1, 0, 0],
                [0, np.cos(tilt), -np.sin(tilt)],
                [0, np.sin(tilt), np.cos(tilt)]
            ])
            Ry = np.array([
                [np.cos(pan), 0, np.sin(pan)],
                [0, 1, 0],
                [-np.sin(pan), 0, np.cos(pan)]
            ])
            R = Ry @ Rx

            # Reset transforms for head and eyes
            head.resetTransform()
            left_eye.resetTransform()
            right_eye.resetTransform()

            # ---- Transform Head ----
            head.rotate(np.degrees(tilt), 1, 0, 0)
            head.rotate(np.degrees(pan), 0, 1, 0)

            # ---- Position Eyes ----
            head_pos = np.array([0.0, 0.0, 0.0])  # head center at origin
            for eye_obj, local_pos in zip([left_eye, right_eye], eye_offsets):
                eye_obj.resetTransform()
                # Apply the head rotation matrix to the local eye offset
                rotated = R @ local_pos + head_pos
                eye_obj.translate(*rotated)

        except BlockingIOError:
            pass  # No data received; that's fine.
        except Exception as e:
            print(f"[ERROR] {e}")

    # ---- Key Handler for Exit ----
    def handle_key(event):
        key = event.key()
        if key in (QtCore.Qt.Key_Escape, QtCore.Qt.Key_Q):
            print("Exiting...")
            app.quit()

    view.keyPressEvent = handle_key

    # ---- Timer to update visualization ----
    timer = QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(30)  # update every 30 ms

    app.exec_()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robot Controller with Virtual Head Visualization")
    parser.add_argument("--mode", choices=["robot", "virtual"], required=True,
                        help="Mode: 'robot' to control the physical robot, 'virtual' to visualize the head")
    parser.add_argument("--ip", default="192.168.0.100", help="IP address of the robot (default: 192.168.0.100)")
    parser.add_argument("--port", type=int, default=65432, help="UDP port to listen on (default: 65432)")
    args = parser.parse_args()

    if args.mode == "robot":
        control_robot(args.ip, args.port)
    elif args.mode == "virtual":
        visualize_head(args.port)