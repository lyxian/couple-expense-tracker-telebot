from PIL import Image, ImageDraw, ImageFont
from cryptography.fernet import Fernet
import argparse
import yaml
import io
import os

def getToken():
    key = bytes(os.getenv('KEY'), 'utf-8')
    encrypted = bytes(os.getenv('SECRET_TELEGRAM'), 'utf-8')
    return Fernet(key).decrypt(encrypted).decode()

def encrypt(text, key=None):
    if key is None:
        key = bytes(os.getenv('KEY'), 'utf-8')
    else:
        key = bytes(key, 'utf-8')
    return Fernet(key).encrypt(text.encode()).decode()

def decrypt(value, key=None):
    if key is None:
        key = bytes(os.getenv('KEY'), 'utf-8')
    else:
        key = bytes(key, 'utf-8')
    if os.getenv(f'SECRET_{value.upper()}'):
        encrypted = bytes(os.getenv(f'SECRET_{value.upper()}'), 'utf-8')
    else:
        encrypted = bytes(value, 'utf-8')
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

if __name__ == '__main__':
    mainParser = argparse.ArgumentParser()
    choices = ['decrypt', 'encrypt']
    arg_template = {
        'required': True,
        'type': str
    }
    mainParser.add_argument('--action', choices=choices, help='cryptography utility', **arg_template)
    mainParser.add_argument('--value', help='argument', **arg_template)
    mainParser.add_argument('--key', help='argument', type=str)
    args = mainParser.parse_args()
    if args.action == 'encrypt':
        if args.key:
            print(encrypt(args.value, args.key))
        else:
            print(encrypt(args.value))
    elif args.action == 'decrypt':
        if args.key:
            print(decrypt(args.value, args.key))
        else:
            print(decrypt(args.value))