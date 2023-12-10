# expense-tracker

Description: This app will store different expenses into MySQL DB for future retrievel

TODO:

- .

Requirements:

- start DB connection
  - via mysql/mariadb client in dynamic shell script
- DB commands :
  - select
  - insert
  - update
  - delete
- App (telebot) :
  - commands (\* = auto-generated)
    - /start,help
    - /join
      - add user to DB << username\*, id\*
    - /add
      - add record to DB << id\*, date, category, amount, payor, ratio, comment
    - /edit
    - /query
      - output as table screenshot (matplotlib)
    - /settle

RDBMS:

- records
  - num, id, category, amount, payor, ratio, comment, settled, timestamp, created
- users
  - num (pk), username, id (fk), created
- categories
  - id (pk), category
- statuses
  - id, status
- messages
  - num (pk), id (fk), status, message, lastCallbackId, lastUpdated

Issues

- is varchar(50) enough for messages.message?
  > use varchar(70)
- .

Done

- add undo to return to previous status
- add custom ratio functionality
- upd undo to return to previous status
- .

```
##Packages (list required packages & run .scripts/python-pip.sh)
cryptography==37.0.4
requests==2.28.1
pendulum==2.1.2
flask==2.2.2
Werkzeug==2.2.2
pyyaml==6.0
pytest==7.1.2

pyTelegramBotAPI==4.4.0
Pillow==10.1.0
##Packages
```
