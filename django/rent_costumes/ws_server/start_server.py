import uvicorn
from decouple import config

if __name__ == '__main__':
    uvicorn.run('main:app', host=config('WS_HOST'), port=config('WS_PORT', cast=int), reload=True, workers=4)