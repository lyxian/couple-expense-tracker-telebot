from cryptography.fernet import Fernet
import yaml
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