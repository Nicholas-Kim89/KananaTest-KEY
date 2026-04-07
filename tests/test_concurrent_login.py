import requests
import threading

URL = 'http://127.0.0.1:5000/login'
errors = []

def login(user_id, password):
    try:
        session = requests.Session()
        response = session.post(URL, data={'user_id': user_id, 'password': password})
        if response.status_code != 200:
            errors.append(f"Failed for {user_id}: status {response.status_code}")
    except Exception as e:
        errors.append(f"Exception for {user_id}: {str(e)}")

def run_concurrent_logins():
    threads = []
    users = [
        ('rosynante', 'rosynante'),
        ('kimeunyong', 'kimeunyong'),
        ('oshznim', 'oshznim'),
        ('jooheuison', 'jooheuison')
    ]
    for user_id, pwd in users * 25: # 100 logins
        t = threading.Thread(target=login, args=(user_id, pwd))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

if __name__ == '__main__':
    run_concurrent_logins()
    if errors:
        print(f"Errors found: {len(errors)}")
        print(errors[:5])
    else:
        print("All logins successful!")
