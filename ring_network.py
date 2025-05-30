#!/usr/bin/env python3
import socket, json

NODES = [
    ('10.254.223.80', 10000),  # h52
    ('10.254.223.81', 10001),  # h53
    ('10.254.223.82', 10002),  # h54
    ('10.254.223.83', 10003),  # h55
]

def setup_socket(bind_addr):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(bind_addr)
    return sock

def inject_token(sock, local_addr):
    sock.sendto(json.dumps({"type": "TOKEN"}).encode(), local_addr)
    print("[Node 0] Token INJETADO — começa o PASS aqui.")
