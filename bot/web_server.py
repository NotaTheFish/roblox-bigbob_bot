from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

# Здесь позже можно добавить API для Roblox или телеграм-команды
