import os
import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "hl": "zh_CN",
    "origin": "https://dida365.com",
    "priority": "u=1, i",
    "referer": "https://dida365.com/",
    "sec-ch-ua": '"Chromium";v="141", "Google Chrome";v="141", "Not?A_Brand";v="8"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "traceid": "6721a893b8de3a0431a1548c",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "x-csrftoken": "GpesKselqEa9oKJQRM3bj8tkdT2kJVNSNaZ9eM0i3Q-1730258339",
    "x-device": '{"platform":"web","os":"macOS 10.15.7","device":"Chrome 141.0.0.0","name":"","version":6101,"id":"689e9fa68d521b4a0abec2cb","channel":"website","campaign":"","websocket":""}',
    "x-tz": "Asia/Shanghai",
}


def login(username, password):
    session = requests.Session()
    login_url = "https://api.dida365.com/api/v2/user/signon?wc=true&remember=true"
    payload = {"username": username, "password": password}
    response = session.post(login_url, json=payload, headers=HEADERS)
    if response.status_code == 200:
        print("登录成功")
        return session
    else:
        print(f"登录失败，状态码: {response.status_code}")
        return None
