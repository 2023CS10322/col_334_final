#!/usr/bin/env python3
import socket
import select
import collections
import threading
import time


def load_config(filename="config.json"):
    cfg = {}
    with open(filename) as f:
        for line in f:
            line = line.strip().strip(",")
            if not line or line[0] in "{}":
                continue
            k, v = line.split(":", 1)
            cfg[k.strip().strip('"')] = v.strip().strip('"')
    return cfg


config = load_config()
SERVER_IP   = config.get("server_ip", "10.0.0.100")
SERVER_PORT = int(config.get("port", 8887))
FILENAME    = config.get("filename", "words.txt")
PROC_MS     = int(config.get("proc_ms", 0))        
REPEAT      = int(config.get("repeat_words", 1))  


with open(FILENAME) as f:
    base = f.read().strip().split(",")
words = base * max(1, REPEAT)

def handle_request(req: str) -> str:

    try:
        p, k = map(int, req.split(","))
    except Exception:
        return "EOF\n"

    if p >= len(words):
        return "EOF\n"

    slice_words = words[p:p+k]
    if p + k >= len(words):
        slice_words.append("EOF")

    if PROC_MS > 0:
        time.sleep(PROC_MS / 1000.0)  

    return ",".join(slice_words) + "\n"


rq = collections.deque()          
rq_lock = threading.Lock()

inputs = []                       
inputs_lock = threading.Lock()

buffers = {}                      
buffers_lock = threading.Lock()

def receiver_thread(listener: socket.socket):

    listener.setblocking(False)

    while True:
    
        with inputs_lock:
            current_inputs = inputs[:]

        try:
            readable, _, _ = select.select([listener] + current_inputs, [], [], 0.005)
        except Exception:
            continue

        for sock in readable:
            if sock is listener:
                try:
                    conn, _ = listener.accept()
                    conn.setblocking(False)
                    with inputs_lock:
                        inputs.append(conn)
                    with buffers_lock:
                        buffers[conn] = ""
                except Exception:
                    continue
            else:
                try:
                    data = sock.recv(4096)
                except Exception:
                    data = b""

                if not data:

                    with inputs_lock:
                        if sock in inputs:
                            inputs.remove(sock)
                    with buffers_lock:
                        buffers.pop(sock, None)
                    try:
                        sock.close()
                    except:
                        pass
                    continue


                with buffers_lock:
                    buffers[sock] += data.decode()
                    buf = buffers[sock]

                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            with rq_lock:
                                rq.append((sock, line))
                    buffers[sock] = buf  

def worker_thread():

    while True:
        csock, line = None, None
        with rq_lock:
            if rq:
                csock, line = rq.popleft()

        if csock is None:

            time.sleep(0.0005)
            continue

        try:
            resp = handle_request(line)
            csock.sendall(resp.encode())
        except Exception:

            with inputs_lock:
                if csock in inputs:
                    inputs.remove(csock)
            with buffers_lock:
                buffers.pop(csock, None)
            try:
                csock.close()
            except:
                pass

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ls:
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((SERVER_IP, SERVER_PORT))
        ls.listen()
        print(f"Server listening on {SERVER_IP}:{SERVER_PORT} (threaded FCFS)")

        t_recv = threading.Thread(target=receiver_thread, args=(ls,), daemon=True)
        t_work = threading.Thread(target=worker_thread, daemon=True)
        t_recv.start()
        t_work.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Server shutting down...")

if __name__ == "__main__":
    main()
