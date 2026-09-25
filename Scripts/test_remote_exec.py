import socket
import json
import time

def test_remote_exec():
    # Unreal Python Remote Execution uses UDP broadcast/multicast
    MULTICAST_GROUP = "239.0.0.1"
    MULTICAST_PORT = 6766
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(1.0)
    
    # Discovery message
    msg = json.dumps({
        "version": 1,
        "magic": "ue_py",
        "type": "open_connection"
    }).encode("utf-8")
    
    try:
        sock.sendto(msg, (MULTICAST_GROUP, MULTICAST_PORT))
        print("Sent discovery broadcast to Unreal Editor")
    except Exception as e:
        print(f"Broadcast failed: {e}")

test_remote_exec()
