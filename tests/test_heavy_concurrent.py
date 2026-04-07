import requests
import threading

def do_work():
    session = requests.Session()
    # Login
    resp = session.post('http://127.0.0.1:5000/login', data={'user_id': 'rosynante', 'password': 'password'})
    # ai-summary
    session.get('http://127.0.0.1:5000/ai-summary')
    # add progress
    resp = session.post('http://127.0.0.1:5000/api/add-progress', data={'item_id': 1, 'content': 'Load test'})
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
    else:
        print("Success")

threads = []
for _ in range(50):
    t = threading.Thread(target=do_work)
    threads.append(t)
    t.start()

for t in threads:
    t.join()
