from PIL import Image, ImageDraw, ImageFont
from cryptography.fernet import Fernet
import yaml
import io
import os

def getToken():
    key = bytes(os.getenv('KEY'), 'utf-8')
    encrypted = bytes(os.getenv('SECRET_TELEGRAM'), 'utf-8')
    return Fernet(key).decrypt(encrypted).decode()

def updateSecretsEnv():
    with open('secrets.yaml', 'r') as file:
        data = {k: str(v) for k,v in yaml.safe_load(file).items()}
    tmpEnv = os.environ.copy()
    return {**tmpEnv, **data}

def drawTable(result, chatId):
    img_width, img_height = 800, 400
    img = Image.new('RGB', (img_width, img_height), color='white')
    font = ImageFont.truetype('font/CONSOLA.TTF', size=12)
    draw = ImageDraw.Draw(img)
    text_width = draw.textlength(result.split('\n')[0], font=font)
    text_height = len(result.split('\n')) * (12+1)
    img = Image.new('RGB', (int(text_width)+1, text_height), color='black')
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), result, fill='white', font=font)

    output = io.BytesIO()
    img.save(output, format='PNG')
    imagePath = f'work/{chatId}.png'
    img.save(imagePath)
    return output.getvalue()