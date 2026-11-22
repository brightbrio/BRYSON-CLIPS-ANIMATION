import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8')
key = '13ec145850334064a6f7d598b23d6b34.AGEy2ByquB1Xzfri'
# Try different endpoints
endpoints = [
    ('CN', 'https://open.bigmodel.cn/api/paas/v4/chat/completions'),
    ('Intl', 'https://open.bigmodel.yahooapis.com/api/paas/v4/chat/completions'),
]
for label, url in endpoints:
    print(f'Testing {label} endpoint...')
    try:
        r = requests.post(url, headers={'Authorization': f'Bearer {key}'},
            json={'model': 'glm-4.5-flash', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 10},
            timeout=15)
        print(f'  {label}: {r.status_code} {r.text[:200]}')
    except Exception as e:
        print(f'  {label}: ERROR {e}')
