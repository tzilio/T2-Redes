#!/usr/bin/env python3
import socket, json

NODES = [("127.0.0.1", 10000 + i) for i in range(4)]

def setup_socket(bind_addr):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(bind_addr)
    return sock

def inject_token(sock, local_addr):
    sock.sendto(json.dumps({"type": "TOKEN"}).encode(), local_addr)
    print("[Node 0] Token INJETADO — começa o PASS aqui.")
