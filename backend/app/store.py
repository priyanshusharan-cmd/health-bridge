"""Explicit persistence operations shared by SQLite and MongoDB.

MongoDB uses transactions for record/file/audit consistency. Uploads are capped
at 10 MiB, below MongoDB's 16 MiB document limit, and stored in a separate collection.
"""
import os
from functools import lru_cache

FIELDS = {
    'organizations': 'id name created_at',
    'memberships': 'id user_id organization_id',
    'invitations': 'id token organization_id clinician_id email expires accepted_by',
    'users': 'id name email password role language age initials',
    'sessions': 'token user_id expires',
    'assignments': 'clinician_id patient_id',
    'appointments': 'id patient_id clinician specialty location starts_at',
    'records': 'id patient_id title kind date provider text filename media_type created_at status deleted_at',
    'intakes': 'id patient_id reason duration medications allergies questions language created_at',
    'briefs': 'id patient_id content status engine created_at reviewed_by reviewed_at',
    'instructions': 'id patient_id original plain translated language author created_at brief_id source_revision reviewer_id reviewer_name status withdrawal_reason version previous_version_id content_language reviewed_at acknowledged_at acknowledgement_status override_reason',
    'audit': 'id patient_id actor action detail created_at',
    'files': 'id data',
    'upload_jobs': 'id patient_id user_id idempotency_key filename file_hash state progress error_code error_message record_id created_at updated_at',
    'record_extractions': 'id record_id version pages_json method ocr_lang warnings created_at',
    'record_corrections': 'id record_id version kind date provider text reason reviewer_id reviewer_name created_at previous_version',
    'clarifications': 'id patient_id brief_id question originating_uncertainty_id creator_id creator_name assigned_owner status resolution_reason created_at resolved_at resolved_by',
    'clarification_messages': 'id clarification_id author_id author_name role text created_at',
    'brief_reviews': 'id brief_id expected_source_revision reviewer_id reviewer_name outcome note reviewed_uncertainties created_at',
}

class Store:
    def insert_row(self, table, values):
        cols = FIELDS[table].split()[:len(values)]
        self.insert(table, dict(zip(cols, values)))

    def insert_rows(self, table, rows):
        for row in rows:
            self.insert_row(table, row)

    def one(self, table, filters=None, sort=None):
        rows = self.find(table, filters, sort=sort, limit=1)
        return rows[0] if rows else None

    def invalidate(self, patient_id):
        self.update('briefs', {'patient_id': patient_id, 'status': {'$in': ['pending', 'approved', 'flagged']}}, {'status': 'outdated'})

    def clinical_revision(self, patient_id):
        import hashlib
        records = [r for r in self.find('records', {'patient_id': patient_id}, sort=[('created_at', -1)]) if r.get('status') != 'withdrawn' and not r.get('deleted_at')]
        intake = self.one('intakes', {'patient_id': patient_id}, sort=[('created_at', -1)])
        appts = self.find('appointments', {'patient_id': patient_id})
        corr_count = 0
        latest_corr = ""
        for r in records:
            corrs = self.find('record_corrections', {'record_id': r['id']}, sort=[('created_at', -1)])
            if corrs:
                corr_count += len(corrs)
                if not latest_corr or corrs[0]['created_at'] > latest_corr:
                    latest_corr = corrs[0]['created_at']
        intake_time = intake['created_at'] if intake else "none"
        latest_rec_time = records[0]['created_at'] if records else "none"
        digest = hashlib.sha256(
            f"{len(records)}:{latest_rec_time}:{intake_time}:{corr_count}:{latest_corr}:{len(appts)}".encode()
        ).hexdigest()[:16]
        return f"rev-{digest}"

    def revision(self, patient_id):
        row = self.one('audit', {'patient_id': patient_id}, sort=[('id', -1)])
        return row['id'] if row else 0

class SQLiteStore(Store):
    def __init__(self, raw):
        self.raw = raw

    def execute(self, *args):
        # Kept for maintenance of the existing local SQLite database.
        return self.raw.execute(*args)

    def field(self, table, key):
        if key not in FIELDS[table].split():
            raise ValueError('Unknown database field')
        return key

    def where(self, table, filters):
        clauses, params = [], []
        for key, value in (filters or {}).items():
            key = self.field(table, key)
            if isinstance(value, dict):
                for op, item in value.items():
                    if op == '$in':
                        if not item:
                            clauses.append('0=1')
                        else:
                            clauses.append(f'{key} IN ({",".join("?" for _ in item)})')
                            params.extend(item)
                    else:
                        clauses.append(key + {'$gt':'>', '$lt':'<'}[op] + '?')
                        params.append(item)
            else:
                clauses.append(f'{key}=?')
                params.append(value)
        return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), params

    def find(self, table, filters=None, sort=None, limit=None):
        FIELDS[table]
        clause, params = self.where(table, filters)
        sql = f'SELECT * FROM {table}' + clause
        if sort:
            sql += ' ORDER BY ' + ','.join(self.field(table,k) + (' DESC' if d == -1 else ' ASC') for k,d in sort)
        if limit is not None:
            sql += ' LIMIT ?'
            params.append(limit)
        return [dict(r) for r in self.raw.execute(sql, params)]

    def insert(self, table, row):
        keys = [self.field(table,k) for k in row]
        self.raw.execute(f'INSERT INTO {table}({",".join(keys)}) VALUES({",".join("?" for _ in keys)})', list(row.values()))

    def update(self, table, filters, values):
        clause, params = self.where(table, filters)
        columns = ','.join(self.field(table,k) + '=?' for k in values)
        self.raw.execute(f'UPDATE {table} SET {columns}' + clause, list(values.values()) + params)

    def delete(self, table, filters):
        clause, params = self.where(table, filters)
        self.raw.execute(f'DELETE FROM {table}' + clause, params)

    def count(self, table, filters):
        clause, params = self.where(table, filters)
        return self.raw.execute(f'SELECT COUNT(*) FROM {table}' + clause, params).fetchone()[0]

    def add_audit(self, row):
        self.insert('audit', row)

class MongoStore(Store):
    def __init__(self, database, session):
        self.database, self.session = database, session

    def find(self, table, filters=None, sort=None, limit=None):
        cursor = self.database[table].find(filters or {}, {'_id': 0}, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)

    def insert(self, table, row):
        self.database[table].insert_one(dict(row), session=self.session)

    def update(self, table, filters, values):
        self.database[table].update_many(filters, {'$set': values}, session=self.session)

    def delete(self, table, filters):
        self.database[table].delete_many(filters, session=self.session)

    def count(self, table, filters):
        return self.database[table].count_documents(filters, session=self.session)

    def add_audit(self, row):
        from pymongo import ReturnDocument
        counter = self.database.counters.find_one_and_update(
            {'_id': 'audit'}, {'$inc': {'value': 1}}, upsert=True,
            return_document=ReturnDocument.AFTER, session=self.session)
        self.insert('audit', {'id': counter['value'], **row})

@lru_cache(maxsize=1)
def mongo_client():
    from pymongo import MongoClient
    return MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=10000, connectTimeoutMS=10000, socketTimeoutMS=20000)

def initialize_mongo():
    database = mongo_client()[os.getenv('MONGODB_DATABASE', 'healthbridge')]
    database.command('ping')
    for table in FIELDS:
        if table == 'assignments':
            database[table].create_index([('clinician_id',1), ('patient_id',1)], unique=True)
        elif table == 'upload_jobs':
            database[table].create_index('id', unique=True)
            database[table].create_index([('patient_id',1), ('idempotency_key',1)])
        elif table in ('record_extractions', 'record_corrections'):
            database[table].create_index('id', unique=True)
            database[table].create_index([('record_id',1), ('version',1)])
        elif table == 'clarifications':
            database[table].create_index('id', unique=True)
            database[table].create_index([('patient_id',1), ('created_at',-1)])
        elif table == 'clarification_messages':
            database[table].create_index('id', unique=True)
            database[table].create_index([('clarification_id',1), ('created_at',1)])
        elif table == 'brief_reviews':
            database[table].create_index('id', unique=True)
            database[table].create_index([('brief_id',1), ('created_at',-1)])
        else:
            database[table].create_index('token' if table == 'sessions' else 'id', unique=True)
        if 'patient_id' in FIELDS[table].split():
            database[table].create_index([('patient_id',1), ('created_at',-1)])
    database.users.create_index('email', unique=True)
    database.memberships.create_index('user_id', unique=True)
    database.invitations.create_index('token', unique=True)
    database.counters.update_one({'_id':'audit'}, {'$setOnInsert': {'value':0}}, upsert=True)
