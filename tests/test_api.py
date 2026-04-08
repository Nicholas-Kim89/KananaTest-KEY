import requests
res = requests.post(
    'http://127.0.0.1:5000/api/chat',
    json={'message': '오승환책임에 대해 알려줘', 'history': []},
    headers={'Cookie': 'session=dummy'}
)
print("Status:", res.status_code)
# This will fail unless we construct a proper Flask session
