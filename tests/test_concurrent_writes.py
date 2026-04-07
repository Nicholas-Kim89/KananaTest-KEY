import requests
import threading

URL = 'http://127.0.0.1:5000/api/add-progress'

def add_progress(session, user_id, password, item_id, content):
    session.post('http://127.0.0.1:5000/login', data={'user_id': user_id, 'password': password})
    response = session.post(URL, data={'item_id': item_id, 'content': content})
    if response.status_code == 200:
        print(f"Success for {user_id}")
    else:
        print(f"Failed for {user_id}: {response.status_code}")

def run_concurrent():
    threads = []
    users = [
        ('rosynante', 'rosynante'),
        ('kimeunyong', 'kimeunyong'),
        ('oshznim', 'oshznim'),
        ('jooheuison', 'jooheuison')
    ]
    for i in range(20):
        user_id, pwd = users[i % 4]
        session = requests.Session()
        t = threading.Thread(target=add_progress, args=(session, user_id, pwd, 1, f"Test {i}"))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

if __name__ == '__main__':
    run_concurrent()
