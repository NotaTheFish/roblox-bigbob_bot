import requests


def get_roblox_profile(username: str):
    # Получить ID пользователя по нику
    search_url = "https://users.roblox.com/v1/usernames/users"
    resp = requests.post(search_url, json={"usernames": [username]})
    
    try:
        user_data = resp.json()["data"][0]
        user_id = str(user_data["id"])
    except Exception:
        return None, None, None
    
    # Получить данные профиля
    profile_url = f"https://users.roblox.com/v1/users/{user_id}"
    data = requests.get(profile_url).json()

    description = data.get("description", "") or ""
    status = data.get("status", "") or ""
    
    return description, status, user_id
