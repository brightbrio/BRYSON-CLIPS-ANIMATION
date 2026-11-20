@echo off
cd /d "%~dp0"
python -c "
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get('/')
async def root():
    return {'message': 'Hello World'}

import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

config = uvicorn.Config(app, host='127.0.0.1', port=8081, log_level='info', loop='asyncio')
server = uvicorn.Server(config)
server.run()
"