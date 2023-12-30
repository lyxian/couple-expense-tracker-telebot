from cryptography.fernet import Fernet
import traceback
import requests
import logging
import telebot
import time
import re
import os

from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
import subprocess
import pendulum

from markups import createMarkupCalendar, createMarkupCategory, createMarkupUndoCancel, createMarkupPayor, createMarkupRatio, createMarkupConfirm, \
    createMarkupDue, statusMap, categoryMap
from utils import getToken, drawTable
from db import DB


def callTelegramAPI(method, params):
    url = 'https://api.telegram.org/bot{}/{}'.format(getToken(), method)
    response = requests.post(url=url, params=params)
    print(response.json())
    return response

def createBot():
    db = DB(dbName='test_1', logFile='tmp.log')
    TOKEN = getToken()
    bot = telebot.TeleBot(token=TOKEN)

    validCallbacks = ['date', 'category', 'comment', 'payor', 'ratio', 'confirm']

    @bot.message_handler(commands=['start', 'help'])
    def _start(message):
        text = [
            "Welcome to expense-tracker-bot! Here's a list of commands to get started:",
            '/help - show this message',
            '/join - register user in DB',
            '/add - add new expense record',
            '/due - check/settle outstanding',
            '/query - <TBD>',
        ]
        bot.send_message(message.chat.id, '\n'.join(text))
        return

    @bot.message_handler(commands=['join'])
    def _join(message):
        # query user in users
        db.runSelect('users', column='count(id)', condition=f'id = "{message.chat.id}"')
        output = db.outputLast
        if int(output):
            text = 'You have already joined expense-tracker!'
        else:
            db.runInsert('users', {
                'username': message.chat.username,
                'id': message.chat.id
            })
            text = 'You have successfully joined expense-tracker!'
        bot.send_message(message.chat.id, text)
        return

    @bot.message_handler(commands=['add'])
    def _add(message):
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        db.runSelect('users', column='id, username', condition=f'id = "{message.chat.id}"', showColumn=True)
        d = DB._resultToJson(db.outputLast)
        if message.chat.id in d:
            bot.send_message(message.chat.id, 'Choose Date', reply_markup=createMarkupCalendar())
            # insert/update last callback id
            db.runInsertUpdate('messages', {
                'id': message.chat.id,
                'status': statusMap['done'],   # or DELETE row
                'message': '',
                'lastCallbackId': message.message_id,
            }, 'status = {}, lastCallbackId = {}, message = ""'.format(statusMap['done'], message.message_id))
        else:
            bot.send_message(message.chat.id, 'You have not joined expense-tracker, please /join first')
        return
    
    def checkValidCallback(callback):
        return callback.data[0] == '/' or callback.data.split(':')[0] in validCallbacks

    @bot.callback_query_handler(func=checkValidCallback) 
    def _callback(callback):
        print('callback:', callback.data)
        currentCommand = callback.data.split(':')[0]
        if ':' in callback.data:
            currentValues = dict([i.split(':') for i in callback.data.split(';') if i])
            print(currentValues)

        if currentCommand == '/cancel':
            bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
            # insert/update last callback id
            db.runInsertUpdate('messages', {
                'id': callback.message.chat.id,
                'status': statusMap['done'],   # or DELETE row
                'message': '',
                'lastCallbackId': callback.message.message_id,
            }, 'status = {}, lastCallbackId = {}, message = ""'.format(statusMap['done'], callback.message.message_id))
        elif currentCommand == '/undo': 
            db.runSelect('messages', column='id, lastCallbackId, statuses.status, message', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
            d = DB._resultToJson(db.outputLast)
            currentStatus = d[callback.message.chat.id]['status']
            # retrieve message from DB
            # db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
            # output = db.outputLast
            # markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor'], output.split(' @ '))])
            # currentValues = dict([i.split(':') for i in markupData.split(';') if i])
            print(currentValues)
            if currentStatus == 'done':   # -
                bot.edit_message_text(
                    text=f'Choose Date',
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupCalendar()
                )
            elif currentStatus == 'awaitAmount':   # date
                bot.edit_message_text(
                    text=f'Choose Category @ {currentValues["date"]}',
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupCategory(f'date:{currentValues["date"]}')
                )
            elif currentStatus == 'awaitPayor':   # date & category
                messsage = '{} @ {}'.format(currentValues['category'], currentValues['date'])
                markupData = ';'.join([':'.join(i) for i in zip(['category', 'date'], messsage.split(' @ '))])
                print(currentValues, markupData, messsage)
                bot.edit_message_text(
                    text='{}\nHow much was it?'.format(messsage),
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupUndoCancel(markupData)
                )
                # insert/update last callback id
                db.runInsertUpdate('messages', {
                    'id': callback.message.chat.id,
                    'status': statusMap['awaitAmount'],
                    'message': '{}'.format(messsage),
                    'lastCallbackId': callback.message.message_id,
                }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitAmount'], callback.message.message_id, messsage))
            elif currentStatus == 'awaitRatio':   # date & category & amount & payor
                # retrieve message from DB
                db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
                output = db.outputLast
                markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date'], output.split(' @ '))])
                currentValues = dict([i.split(':') for i in markupData.split(';') if i])
                messsage = '{} @ {} @ {}'.format(*currentValues.values())
                print(currentValues, markupData, messsage)
                bot.edit_message_text(
                    text='${}\nWho paid?'.format(messsage),
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupPayor(markupData)
                )
                # insert/update last callback id
                db.runInsertUpdate('messages', {
                    'id': callback.message.chat.id,
                    'status': statusMap['awaitPayor'],
                    'message': '{}'.format(messsage),
                    'lastCallbackId': callback.message.message_id,
                }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitPayor'], callback.message.message_id, messsage))
            elif currentStatus == 'awaitComment':   # date & category & amount & payor & ratio
                # retrieve message from DB
                db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
                output = db.outputLast
                markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor'], output.split(' @ '))])
                currentValues = dict([i.split(':') for i in markupData.split(';') if i])
                messsage = '{} @ {} @ {}\nPayor: {}\nWhat is the ratio?'.format(*currentValues.values())
                print(currentValues, markupData, messsage)
                messagePayload = ' @ '.join(currentValues.values())
                bot.edit_message_text(
                    text=messsage,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupRatio()
                )
                # insert/update last callback id
                db.runInsertUpdate('messages', {
                    'id': callback.message.chat.id,
                    'status': statusMap['awaitRatio'],
                    'message': messagePayload,
                    'lastCallbackId': callback.message.message_id,
                }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitRatio'], callback.message.message_id, messagePayload))
            elif currentStatus == 'awaitConfirm':   # date & category & amount & payor & ratio & comment
                # retrieve message from DB
                db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
                output = db.outputLast
                markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor', 'ratio'], output.split(' @ '))])
                currentValues = dict([i.split(':') for i in markupData.split(';') if i])
                messsage = '${} {} @ {}\nPayor: {}\nRatio: {}\nAny comments?'.format(*currentValues.values())
                print(currentValues, markupData, messsage)
                messagePayload = ' @ '.join(currentValues.values())
                bot.edit_message_text(
                    text=messsage,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupUndoCancel('')
                )
                # insert/update last callback id
                db.runInsertUpdate('messages', {
                    'id': callback.message.chat.id,
                    'status': statusMap['awaitComment'],
                    'message': messagePayload,
                    'lastCallbackId': callback.message.message_id,
                }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitComment'], callback.message.message_id, messagePayload))
            else:
                err = 'ERROR: invalid undo status'
                print(err)
                raise Exception(err)
        elif currentCommand == '/test':
            bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
            bot.send_message(callback.message.chat.id, callback.data)
        elif currentCommand == '/date':
            n = eval(currentValues['/date'])
            bot.edit_message_text(
                text=f'Choose Date',
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=createMarkupCalendar(n)
            )
        elif currentCommand == 'date':
            bot.edit_message_text(
                text=f'Choose Category @ {currentValues["date"]}',
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=createMarkupCategory(callback.data)
            )
        elif currentCommand == 'category':
            messsage = '{} @ {}'.format(currentValues['category'], currentValues['date'])
            # insert/update last callback id
            db.runInsertUpdate('messages', {
                'id': callback.message.chat.id,
                'status': statusMap['awaitAmount'],
                'message': '{}'.format(messsage),
                'lastCallbackId': callback.message.message_id,
            }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitAmount'], callback.message.message_id, messsage))
            bot.edit_message_text(
                text='{}\nHow much was it?'.format(messsage),
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=createMarkupUndoCancel(callback.data)
            )
        elif currentCommand == 'payor':
            messsage = '{} @ {} @ {}'.format(currentValues['amount'], currentValues['category'], currentValues['date'])
            payor = currentValues['payor']
            print(currentValues)
            messagePayload = '{} @ {}'.format(messsage, payor)
            # insert/update last callback id
            db.runInsertUpdate('messages', {
                'id': callback.message.chat.id,
                'status': statusMap['awaitRatio'],
                'message': messagePayload,
                'lastCallbackId': callback.message.message_id,
            }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitRatio'], callback.message.message_id, messagePayload))
            bot.edit_message_text(
                text='${}\nPayor: {}\nWhat is the ratio?'.format(messsage, payor),
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=createMarkupRatio()
            )
        elif currentCommand == 'ratio':
            ratio = currentValues['ratio']
            if ratio == '50/50':
                # retrieve message from DB
                db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
                output = db.outputLast
                markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor'], output.split(' @ '))])
                currentValues = dict([i.split(':') for i in markupData.split(';') if i])
                print(currentValues)
                messagePayload = '{} @ {}'.format(output, 0.5)
                # insert/update last callback id
                db.runInsertUpdate('messages', {
                    'id': callback.message.chat.id,
                    'status': statusMap['awaitComment'],
                    'message': messagePayload,
                    'lastCallbackId': callback.message.message_id,
                }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitComment'], callback.message.message_id, messagePayload))
                bot.edit_message_text(
                    text='${} {} @ {}\nPayor: {}\nRatio: {}\nAny comments?'.format(*currentValues.values(), ratio),
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=createMarkupUndoCancel('')
                )
            elif ratio == 'custom':
                # retrieve message from DB
                db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
                output = db.outputLast
                markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor'], output.split(' @ '))])
                currentValues = dict([i.split(':') for i in markupData.split(';') if i])
                # insert/update last callback id
                # db.runInsertUpdate('messages', {
                #     'id': callback.message.chat.id,
                #     'status': statusMap['awaitRatio'],
                #     'message': '{}'.format(messsage),
                #     'lastCallbackId': callback.message.message_id,
                # }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitRatio'], callback.message.message_id, messsage))
                bot.edit_message_text(
                    text='${} {} @ {}\nPayor: {}\nWhat is the ratio?'.format(*currentValues.values()),
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                )
        elif currentCommand == 'confirm':
            # retrieve message from DB
            db.runSelect('messages', column='message', condition=f'id = "{callback.message.chat.id}"')
            output = db.outputLast
            markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor', 'ratio', 'comment'], output.split(' @ '))])
            currentValues = dict([i.split(':') for i in markupData.split(';') if i])
            print(currentValues)
            # insert new record
            db.runInsert('records', {
                'id': callback.message.chat.id,
                'category': categoryMap[currentValues['category']],
                'amount': currentValues['amount'],
                'payor': currentValues['payor'],
                'ratio': currentValues['ratio'],
                'comment': currentValues['comment'],
                'settled': 'N',
                'timestamp': currentValues['date']
            })
            # insert/update last callback id
            db.runInsertUpdate('messages', {
                'id': callback.message.chat.id,
                'status': statusMap['done'],   # or DELETE row
                'message': '',
                'lastCallbackId': callback.message.message_id,
            }, 'status = {}, lastCallbackId = {}, message = ""'.format(statusMap['done'], callback.message.message_id))
            bot.edit_message_text(
                text="--- {} ---\nNew record created successfully\nYou may /add again".format(pendulum.now(tz='Asia/Singapore').to_datetime_string()),
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
            ) 
        return

    def awaitAmount(message):
        db.runSelect('messages', column='id, lastCallbackId, statuses.status', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
        d = DB._resultToJson(db.outputLast)
        return message.chat.id in d and d[message.chat.id]['status'] == 'awaitAmount'
        
    @bot.message_handler(func=awaitAmount)
    def _awaitAmount(message):
        print('awaitAmount', message.text)
        db.runSelect('messages', column='id, lastCallbackId, statuses.status', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
        d = DB._resultToJson(db.outputLast)
        
        db.runSelect('messages', column='message', condition=f'id = "{message.chat.id}"')
        output = db.outputLast
        markupData = ';'.join([':'.join(i) for i in zip(['category', 'date', 'amount'], f'{output} @ {message.text}'.split(' @ '))])
        currentValues = dict([i.split(':') for i in markupData.split(';') if i])
        print(currentValues)
        messagePayload = '{} @ {}'.format(output, message.text)
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        # insert/update last callback id
        db.runInsertUpdate('messages', {
            'id': message.chat.id,
            'status': statusMap['awaitPayor'],
            'message': messagePayload,
            'lastCallbackId': d[message.chat.id]['lastCallbackId'],
        }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitPayor'], d[message.chat.id]['lastCallbackId'], messagePayload))
        bot.edit_message_text(
            text='${} {}\nWho paid?'.format(message.text, output),
            chat_id=message.chat.id,
            message_id=d[message.chat.id]['lastCallbackId'],
            # reply_markup=createMarkupConfirm('', mode='confirm')   # max 64 bytes/char
            reply_markup=createMarkupPayor(markupData)   # max 64 bytes/char
        )

    def awaitRatio(message):
        db.runSelect('messages', column='id, lastCallbackId, statuses.status', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
        d = DB._resultToJson(db.outputLast)
        return message.chat.id in d and d[message.chat.id]['status'] == 'awaitRatio'
        
    @bot.message_handler(func=awaitRatio)
    def _awaitRatio(message): 
        print('awaitRatio', message.text)
        db.runSelect('messages', column='id, lastCallbackId, statuses.status', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
        d = DB._resultToJson(db.outputLast)
        
        # retrieve message from DB
        db.runSelect('messages', column='message', condition=f'id = "{message.chat.id}"')
        output = db.outputLast
        markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor'], output.split(' @ '))])
        currentValues = dict([i.split(':') for i in markupData.split(';') if i])
        print(currentValues)
        messagePayload = '{} @ {}'.format(output, message.text)
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        # insert/update last callback id
        db.runInsertUpdate('messages', {
            'id': message.chat.id,
            'status': statusMap['awaitComment'],
            'message': messagePayload,
            'lastCallbackId': d[message.chat.id]['lastCallbackId'],
        }, 'status = {}, lastCallbackId = {}, message = "{}"'.format(statusMap['awaitComment'], d[message.chat.id]['lastCallbackId'], messagePayload))
        bot.edit_message_text(
            text='${} {} @ {}\nPayor: {}\nRatio: {}\nAny comments?'.format(*currentValues.values(), message.text),
            chat_id=message.chat.id,
            message_id=d[message.chat.id]['lastCallbackId'],
            reply_markup=createMarkupUndoCancel('')
            # reply_markup=createMarkupConfirm('', mode='confirm')
        )

    def awaitComment(message):
        db.runSelect('messages', column='id, lastCallbackId, statuses.status', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
        d = DB._resultToJson(db.outputLast)
        return message.chat.id in d and d[message.chat.id]['status'] == 'awaitComment'
        
    @bot.message_handler(func=awaitComment)
    def _awaitComment(message): 
        print('awaitComment', message.text)
        db.runSelect('messages', column='id, lastCallbackId, statuses.status', joinType='LEFT JOIN', joinTable='statuses', joinOn=('status', 'num'), showColumn=True)
        d = DB._resultToJson(db.outputLast)
        
        db.runSelect('messages', column='message', condition=f'id = "{message.chat.id}"')
        output = db.outputLast
        markupData = ';'.join([':'.join(i) for i in zip(['amount', 'category', 'date', 'payor', 'ratio'], f'{output} @ {message.text}'.split(' @ '))])
        currentValues = dict([i.split(':') for i in markupData.split(';') if i])
        print(currentValues)

        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        comment = message.text.lower()
        bot.edit_message_text(
            text='${} {} @ {}\nPayor: {}\nRatio: {}\nComment: {}\n--- Please confirm ---'.format(*currentValues.values(), comment),
            chat_id=message.chat.id,
            message_id=d[message.chat.id]['lastCallbackId'],
            reply_markup=createMarkupConfirm('', mode='confirm')   # max 64 bytes/char
        )

        messagePayload = '{} @ {}'.format(output, comment)
        # insert/update last callback id
        db.runInsertUpdate('messages', {
            'id': message.chat.id,
            'status': statusMap['awaitConfirm'],
            'message': messagePayload,
            'lastCallbackId': d[message.chat.id]['lastCallbackId'],
        }, 'status = {}, message = "{}"'.format(statusMap['awaitConfirm'], messagePayload))

    @bot.message_handler(commands=['due'])
    def _due(message):
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        db.runSelect('users', column='id, username', condition=f'id = "{message.chat.id}"', showColumn=True)
        d = DB._resultToJson(db.outputLast)
        if message.chat.id in d:
            bot.send_message(message.chat.id, 'Choose command', reply_markup=createMarkupDue())
        else:
            bot.send_message(message.chat.id, 'You have not joined expense-tracker, please /join first')
        return
    
    def checkValidCallbackDue(callback):
        return 'due.' in callback.data

    @bot.callback_query_handler(func=checkValidCallbackDue) 
    def _callbackDue(callback):
        print('callbackO:', callback.data)
        currentCommand = callback.data.split('.')[1]
        if currentCommand == 'show':
            # ..
            # UPDATE records SET payor = 'She' WHERE num IN ('5','6');
            # UPDATE records SET payor = 'He' WHERE num IN ('5','6');
            # UPDATE records SET settled = 'Y' WHERE settled = 'N';
            # UPDATE records SET settled = 'N' WHERE settled = 'Y';

            # SELECT categories.category, amount, payor, ratio, comment, settled, timestamp FROM records LEFT JOIN categories ON records.category = categories.num WHERE records.id = "6122662956" AND records.settled = "N" ORDER BY timestamp ASC;
            # SELECT categories.category, amount, payor, ratio, CAST(amount * (1-ratio) AS decimal(10, 2)) AS owe_payor, timestamp, comment FROM records LEFT JOIN categories ON records.category = categories.num WHERE records.id = "6122662956" AND records.settled = "N" ORDER BY timestamp ASC;
            db.runSelect('records', column='categories.category, amount, payor, ratio, CAST(amount * (1-ratio) AS decimal(10, 2)) AS debt, timestamp, comment', joinType='LEFT JOIN', joinTable='categories', joinOn=('category', 'num'), \
                showTable=True, condition=f'records.id = "{callback.message.chat.id}" AND records.settled = "N"', orderBy=('timestamp', 'payor'))
            result = db.outputLast
            if 'no output' in result:
                bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
                bot.send_message(callback.message.chat.id, 'No outstanding amount')
            else:
                image = drawTable(result, callback.message.chat.id)
                # SELECT payor, CAST(SUM(amount * (1-ratio)) AS decimal(10, 2)) AS debt FROM records GROUP BY payor;
                db.runSelect('records', column='payor, CAST(SUM(amount * (1-ratio)) AS decimal(10, 2)) AS debt', condition=f'id = "{callback.message.chat.id}" AND settled = "N"', groupBy='payor', showColumn=True)
                d = DB._resultToJson(db.outputLast)
                message = '--- Summary ---\n' + '\n'.join(['{} paid ${}'.format(payor, d[payor]['debt']) for payor in d])
                difference = None
                if len(d) > 1:
                    difference = eval('{} - {}'.format(d['He']['debt'], d['She']['debt']))
                    if difference > 0:
                        message += '\nShe → He : ${:.2f}'.format(difference)
                    elif difference < 0:
                        message += '\nHe → She : ${:.2f}'.format(-difference)
                bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
                # bot.send_photo(chat_id=callback.message.chat.id, photo=image)
                bot.send_photo(chat_id=callback.message.chat.id, photo=image, caption=message)
        elif currentCommand == 'settle':
            bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
            db.runUpdate('records', {
                'settled': 'Y',
            }, condition=f'id = "{callback.message.chat.id}" AND settled = "N"')
            bot.send_message(callback.message.chat.id, 'Cleared all outstanding')
        return
    
    return bot
          