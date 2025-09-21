import socket
import threading
import json
from collections import deque, defaultdict


with open('config.json', 'r') as f:
    config = json.load(f)

HOST = config['server_ip']
PORT = config['port']


with open('words.txt', 'r') as f:
    words = f.read().strip().split(',')


client_queues = defaultdict(deque)
active_clients = set()
queue_lock = threading.Lock()
condition = threading.Condition(queue_lock)

def handle_client(conn, addr):
    print(f"Connected by {addr}")
    client_id = addr[0]  
    
    try:
        data = conn.recv(1024).decode().strip()
        if not data:
            return
        

        with condition:
            client_queues[client_id].append((conn, data))
            active_clients.add(client_id)
            condition.notify()
            
    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        pass

def process_requests():

    current_client_idx = 0
    client_list = []
    
    while True:
        with condition:

            while not active_clients:
                condition.wait()
            

            if set(client_list) != active_clients:
                client_list = list(active_clients)
                

            if not client_list:
                continue
                

            attempts = 0
            while attempts < len(client_list):
                current_client_idx = (current_client_idx) % len(client_list)
                client_id = client_list[current_client_idx]
                
                if client_queues[client_id]:

                    conn, data = client_queues[client_id].popleft()
                    

                    if not client_queues[client_id]:
                        active_clients.remove(client_id)
                        

                    current_client_idx = (current_client_idx + 1) % len(client_list)
                    break
                else:
 
                    current_client_idx = (current_client_idx + 1) % len(client_list)
                    attempts += 1
            

            if attempts == len(client_list):
                continue
        
        try:

            parts = data.split(',')
            if len(parts) != 2:
                conn.send("Invalid request format. Use: p,k\\n".encode())
                conn.close()
                continue
                
            p = int(parts[0])
            k = int(parts[1])
            

            if p >= len(words):
                conn.send("EOF\n".encode())
                conn.close()
                continue
                

            end_idx = min(p + k, len(words))
            response_words = words[p:end_idx]
            

            if end_idx == len(words):
                response_words.append("EOF")
                

            response = ','.join(response_words) + '\n'
            conn.send(response.encode())
            
        except ValueError:
            conn.send("Invalid parameters. Use integers: p,k\\n".encode())
        except Exception as e:
            print(f"Error processing request: {e}")
        finally:
            conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        

        worker = threading.Thread(target=process_requests, daemon=True)
        worker.start()
        

        while True:
            conn, addr = s.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()

if __name__ == "__main__":
    start_server()