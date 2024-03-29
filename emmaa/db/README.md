# EMMAA Databases

This directory contains code for creating and managing the EMMAA databases.
This document describes the databases schemas and managers as well as ways to
set up new instances of the databases and testing and debugging tips.

EMMAA currently uses two databases:

- Query database that stores the queries and their results as well as
information about the users and their subscriptions. This is set up as an
RDS database.

- Statements database that stores the statements JSONs per model and date and
the path counts for each statement. This is set up as a local postgres database
on EMMAA server.

## EmmaaDatabaseManager
manager.py in this directory contains the code for EmmaaDatabaseManager class
and its subclasses: QueryDatabaseManager and StatementsDatabaseManager.
The parent class allows programmatically create and drop database tables. Each
child class provides methods for adding or querying data in the corresponding
database.

## Queries database

Query database stores the queries and their results as well as
information about the users and their subscriptions.

### Schema
Queries database contains the following tables:

- User - contains user ID and email. Important thing to note here is that the
primary key (user_id) is actually generated by a different database - 
indralab users database - to support user registration across multiple
projects (e.g. INDRA DB and EMMAA). To find more about the indralab users
database, see ui_util.indralab_auth_tools. The user_id is detected by auth
tools when user logs in on EMMAA website and is passed to the queries database
to register user's queries.

- Query - contains query hash, model ID (name), query JSON and query type.
All queries in this table are unique.

- UserQuery - contains user ID, query hash, date (the query was first run by
this user), subscription status and count (number of times the query was
requested by this user). Note that we do not require a user to be logged in
to run a query, so the user ID can be null. For subscribing to a query, the
log in is required.

- UserModel - contains user ID, model ID (name), date, subscription status.
This table is used to keep track of the models a user is subscribed to. Note
that this type of subscription is different from the query subscription, here
a user can subscribe to a model general updates about new statements or
new test results rather than a specific query.

- Result - contains query hash, date, result JSON, type of model used to find
this result (e.g. "pysb", "pybel", "signed_graph", "unsigned_graph").
Result JSON here is represented as a dictionary of results keyed by their hashes.
Each subresult could be a different path or a result of a simulation. To find
more about how results are generated or hashed look at 
emmaa.model_tests.ModelManager code. Additional fields in this table are: 
"all_result_hashes" - a set of hashes of all results in the current result;
"delta" - a set of new result hashes that were not present in the previous
version of result for this query.
These fields are added in the db.put_results() method and are used to detect
"new" results.

### How is database populated?
Whenever a user runs a query through a web interface or via REST API, the
query and its results are stored. If the identity of a user is known, it is
stored too and linked to the query. If the query has subscribed users, it will
be rerun automatically by a Batch job after a daily model update. All new
results to subscribed queries are also stored.

### Setting up the database from scratch

In case there's ever a need to reinstantiate the database, the following
steps should be followed:

1) Create a new RDS database
2) Set the configuration in db_config.ini file or alternatively as an
environment variable.

Config in db_config.ini file should have the following format:
```
[<db_name>]
dialect = postgres
driver =
username = <username>
password = <password>
host = <host>
port =
name = emmaa_db
type = query
```

The environment variable should have the name EMMAADB<db_name>
(e.g. EMMAADBPRIMARY) and the value should be in the format
`postgresql://<username>:<password>@<host>/<name>`
Also set this environment variable in Batch job definition for jobs that need
to access the database.

3) Then run the DatabaseManager method to create tables (this is less error
prone than creating them manually).
```
from emmaa.db import get_db
db = get_db(<db_name>)
db.create_tables()
```

### Testing and debugging

1) Set up the local small instance of the  database.

The easiest way to test QueryDatabaseManager code is to set up a local instance
of a database. 

```
from emmaa.tests.db_setup import setup_query_db, _get_test_db
setup_query_db()
db = _get_test_db()
```

Then all the methods in QueryDatabaseManager can be tested with `db` object.

2) Use the remote dev instance of the queries database.

When making changes to database schema or related code, it could be useful to
test how it works over a period of time (e.g. make sure daily query runs on
Batch can load and run the queries and store the results and UI can display
them). To do this, we can modify the code where it connects to the database.

```
from emmaa.db import get_db
db = get_db('dev')
```

Where it could be relevant:

- emmaa_service/api.py - to test the UI with changes in the database.
  
  Replace
  ```
  qm = QueryManager()
  ```
  with
  ```
  db = get_db('dev')
  qm = QueryManager(db)
  ```

- script/answer_queries_from_s3.py - to test the code that runs queries from S3.

  Replace
  ```
  answer_queries_from_s3(args.model, db=None)
  ```
  with
  ```
  answer_queries_from_s3(args.model, db=get_db('dev'))
  ```

  This should be pushed to a branch on indralab.

- aws_lambda_functions/after_update.py - to run a Batch job from a branch with
modified code. NOTE: replace this on lambda through AWS console manually.

  Replace
  ```
  BRANCH = 'origin/master'
  ```
  with
  ```
  BRANCH = 'origin/<branch>'
  ```

## Statements database

Statements database that stores the statements JSONs per model and date and
the path counts for each statement. This is set up as a local postres database
on EMMAA server. The main goal of statements database is to provide the
statements evidence (sorted and filtered in different ways if requested)
to EMMAA service endpoints. This was previously done by loading the statements
into memory from S3 and then filtering/sorting them which was inefficient and
caused out of memory errors. 

### Schema

The statements database at the moment contains one table:

- Statements - contains model ID (name), statement hash, statement JSON,
date and path counts for this statement. Path counts is defined as a total
number of paths in test results (across test corpora for a given model)
that include this statement. It might be worth considering separating the path
counts into a separate table since they are populated in a separate process and
it could be more efficient to update them in separate tables. 
The reason for keeping them in the same table is that it is easier to sort
the statements by path counts (this is used in all statements page on EMMAA
website).

### How is database populated?

The database is populated during daily model updates by Batch in two steps:

1) After the model manager is updated, the newly assembled statements are
stored both on S3 and in the statements database.
2) The last job in the update cycle for each model is notifications job that
aggregates the statistics from multiple stats files for the model (e.g. model
stats and test stats across test corpora) and sends Tweets and emails to
subscribed users. One of the steps in this process is to aggregate the path
counts for each statement in the model and to update them in the Statements
table.

At any moment in time, the statements database only contains the statements
for a short window of time (e.g. 3 days). When new statements are added to
the database, the oldest statements are deleted.

### Setting up the database from scratch

This database can be easily rebuilt at any time if needed. It also should not
cause many interruptions to the service since the database doesn't store more
than a few days worth of statements. In addition, the API is backward
compatible and can load statements from S3 in case database is not available.
To rebuild the database, the following steps should be followed:

1) On the remote server where EMMAA web service is running, get a postgres
base docker image.
2) Set environment file with POSTGRES_PASSWORD and PGDATA variables.
3) Run the docker with the environment file.
4) Set up the database configuration in db_config.ini file or alternatively
as an environment variable.

Config in db_config.ini file should have the following format:
```
[<db_name>]
dialect = postgres
driver =
username = <username>
password = <password>
host = <host>
port =
name = 
type = statement
```
The environment variable should have the name EMMAADB<db_name>
(e.g. EMMAADBSTMT) and the value should be in the format
`postgresql://<username>:<password>@<host>;statement`
Also set this environment variable in Batch job definition for jobs that need
to access the database.

5) Then run the DatabaseManager method to create tables (this is less error
prone than creating them manually).
```
from emmaa.db import get_db
db = get_db(<db_name>)
db.create_tables()
```

6) Then run the DatabaseManager method to populate the database with statements
from S3.
```
db.build_from_s3()
```

### Testing and debugging

1) Set up the local small instance of the statements database

The easiest way to test StatementDatabaseManager code is to set up a local
instance of a database. 

```
from emmaa.tests.db_setup import setup_stmt_db, _get_test_db
setup_stmt_db()
db = _get_test_db()
```

Then all the methods in StatementDatabaseManager can be tested with `db` object.

2) Use the dev version of the statements database (running on EMMAA dev server).

When making changes to database schema or related code, it could be useful to
test how it works over a period of time (e.g. make sure daily updates can
upload new assembled statements and path counts to the database and that UI
evidence and all_statements pages load without errors).
The database is already set up on the EMMAA dev server in addition to main
server (make sure the instance is running) but if needed, it can be set up
on any other server using the steps described in the previous section.
To test the new database over time, we can modify the code where it connects
to the database.


Where it could be relevant:

- emmaa/model_tests.py in "save_assembled_statements" - to test the code that
uploads statements to the database.

  Replace
  ```
  if save_to_db:
      db = get_db('stmt')
  ```
  with
  ```
  if save_to_db:
      db = get_db('stmt_dev')
  ```

- emmaa/subscription/notifications.py in "update_path_counts" - to test the
code that updates path counts in the database.

  Replace
  ```
  db = get_db('stmt')
  path_count_dict = Counter()
  ```
  with
  ```
  db = get_db('stmt_dev')
  path_count_dict = Counter()
  ```
- emmaa_service/api.py in "load_stmts" and "load_path_counts" - to test the UI
with changes in the database.
  
  Replace
  ```
  emmaa_db = get_db('stmt')
  ```
  with
  ```
  emmaa_db = get_db('stmt_dev')
  ```

These changes should be pushed to a branch on indralab.

- aws_lambda_functions/model_manager_update.py - to run a Batch job from a 
branch with modified code (upload statements part). NOTE: replace this on
lambda through AWS console manually.

  Replace
  ```
  BRANCH = 'origin/master'
  ```
  with
  ```
  BRANCH = 'origin/<branch>'
  ```

- aws_lambda_functions/after_update.py - to run a Batch job from a branch with
modified code (update path counts part). NOTE: replace this on lambda through 
AWS console manually.

  Replace
  ```
  BRANCH = 'origin/master'
  ```
  with
  ```
  BRANCH = 'origin/<branch>'
  ```
