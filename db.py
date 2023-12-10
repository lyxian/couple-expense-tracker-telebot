from utils import updateSecretsEnv
import subprocess

class DB:
    def __init__(self, dbName=None, outputRaw=True, logFile=None):
        self.env = updateSecretsEnv()
        self.logFile = logFile
        self.dbName = dbName
        self.output = None
        self.outputLast = None
        self.cmd = None
        if outputRaw:
            self.connString = ['mysql', '-h', self.env['DATABASE_HOST'], '-u', self.env['DATABASE_USER'], \
                '-p{}'.format(self.env['DATABASE_PASS']) , self.dbName, '--show-warnings', '-se']
        else:
            self.connString = ['mysql', '-h', self.env['DATABASE_HOST'], '-u', self.env['DATABASE_USER'], \
                '-p{}'.format(self.env['DATABASE_PASS']) , self.dbName, '--show-warnings', '-tvve']

        self.testConnection()

    def logOutput(self):
        with open(self.logFile, 'w') as f:
            if self.output:
                self.output = f'{self.output}'
            else:
                self.output = f'--- no output ---'
            f.write(self.output)
        self.outputLast = self.output
        self.output = None
        self.cmd = None

    def executeCommand(self):
        print(self.cmd)
        p = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env)
        self.output = p.stdout.read().decode().strip()
        self.logOutput()

    def testConnection(self):
        cmd = 'status'
        self.cmd = self.connString + [cmd]
        self.executeCommand()

    def runSelect(self, tableName, column=None, joinType=None, joinTable=None, joinOn=None, condition=None, 
                  orderBy=None, groupBy=None, count=None, showColumn=False, showTable=False):
        if showTable:
            connString = self.connString[:-1] + ['-te']
        else:
            if showColumn:
                connString = ['-e' if i == '-se' else i for i in self.connString]
            else:
                connString = self.connString
        if column is None and condition is None and count is None:
            cmd = f'SELECT * FROM {tableName}'
        else:
            if joinType and joinOn and joinTable:
                tableName += f' {joinType} {joinTable} ON {tableName}.{joinOn[0]} = {joinTable}.{joinOn[1]}'
            if column:
                cmd = f'SELECT {column} FROM {tableName} '
            else:
                cmd = f'SELECT * FROM {tableName} '
            if condition:
                cmd += f'WHERE {condition} '
            if count:
                cmd += f'LIMIT {count} '
            if orderBy:
                if isinstance(orderBy, tuple):
                    cmd += 'ORDER BY {} '.format(', '.join([f'{col} DESC' if col[0] == '-' else f'{col} ASC' for col in orderBy]))
                else:
                    if orderBy[0] == '-':
                        cmd += f'ORDER BY {orderBy[1:]} DESC '
                    else:
                        cmd += f'ORDER BY {orderBy} ASC '
            if groupBy:
                if isinstance(groupBy, tuple):
                    cmd += 'GROUP BY {} '.format(', '.join(groupBy))
                else:
                    cmd += f'GROUP BY {groupBy} '
        self.cmd = connString + [f'{cmd};']
        self.executeCommand()

    # INSERT INTO Students(name, address, grades, phone) VALUES ('Harry', 'Potter', 31, 'USA');
    def runInsert(self, tableName, payload):
        if isinstance(payload, list):
            cmdStr = []
            for item in payload:
                newPayload = DB._formatPayload(item)
                cmdStr += [f'INSERT IGNORE INTO {tableName} ({newPayload[0]}) VALUES ({newPayload[1]});']
            cmd = '\n'.join(cmdStr)
        elif isinstance(payload, dict):
            newPayload = DB._formatPayload(payload)
            cmd = f'INSERT IGNORE INTO {tableName} ({newPayload[0]}) VALUES ({newPayload[1]});'
        else:
            raise Exception('invalid payload type')
        self.cmd = self.connString + [cmd]
        self.executeCommand()

    def runInsertUpdate(self, tableName, payload, condition):
        # INSERT INTO messages (id, status, lastCallbackId) VALUES (1, 2, 3) ON DUPLICATE KEY UPDATE `status` = 3;
        newPayload = DB._formatPayload(payload)
        cmd = f'INSERT INTO {tableName} ({newPayload[0]}) VALUES ({newPayload[1]}) ON DUPLICATE KEY UPDATE {condition};'
        self.cmd = self.connString + [cmd]
        self.executeCommand()

    def runUpdate(self, tableName, payload, condition):
        # UPDATE table_name SET column1 = value1, column2 = value2, ... WHERE condition;
        newPayload = ', '.join([f'{k} = "{v}"' for k,v in payload.items()])
        cmd = f'UPDATE {tableName} SET {newPayload} WHERE {condition};'
        self.cmd = self.connString + [cmd]
        self.executeCommand()

    def runDelete(self):
        self.executeCommand()

    def runCustom(self, cmd):
        self.cmd = self.connString + [cmd]
        self.executeCommand()

    @staticmethod
    def _formatPayload(payload):
        columns = []
        values = []
        for k, v in payload.items():
            columns += [k]
            if isinstance(v, int):
                values += [f'{v}']
            else:
                values += [f"'{v}'"]
        return ','.join(columns), ','.join(values)

    @staticmethod
    def _resultToJson(resultStr):
        columns, *rows = resultStr.split('\n')
        columns = columns.split('\t')
        rows = [row.split('\t') for row in rows]
        return {(int(row[0]) if row[0].isnumeric() else row[0]): dict(zip(columns[1:], row[1:])) for row in rows}