import socket
import struct
import argparse
import time
from datetime import datetime

def receive_looking_status(port):
    # Set up UDP socket for receiving looking status
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    print(f"[Looking Status Receiver] Listening on UDP port {port}")
    
    last_status = None
    
    try:
        while True:
            # Receive looking status data
            data, addr = sock.recvfrom(1024)
            
            # Unpack boolean status and timestamp
            looking_at_camera, timestamp = struct.unpack('?q', data)
            
            # Only print status when it changes
            if last_status != looking_at_camera:
                status_text = "LOOKING AT CAMERA" if looking_at_camera else "NOT LOOKING AT CAMERA"
                current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{current_time}] Status: {status_text}")
                last_status = looking_at_camera
                
                # You can add your custom actions here based on looking status
                # For example:
                # if looking_at_camera:
                #     print("User is paying attention!")
                # else:
                #     print("User's attention is elsewhere")
                
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Looking Status Receiver")
    parser.add_argument("--port", type=int, default=65433, 
                        help="UDP port to listen for looking status (default: 65433)")
    args = parser.parse_args()
    
    receive_looking_status(args.port)