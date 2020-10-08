# EMMAA Testing

In EMMAA, we use the `nosetests` framework to run tests. Tests are 
automatically detected in the usual ways, such as by the prefix `test_` on
files and functions.

## Test Database
Some tests require access to a database to test the part of the EMMAA framework
that relies on postgres database storage. Nosetests fixtures are used to
create this database and drop it when needed. To enable this on your local
computer, you must first install postgres.

### Instructions for Mac
On Mac, download and install the postgres app:
https://postgresapp.com/downloads.html, then launch the app, and click
Initialize. After this is done, you should be able to run the tests.

### Instructions for Linux
On Linux, start by installing postgres:

```bash
sudo apt-get update
sudo apt-get install postgresql
```

You should then edit the the host-based authentication (HBA) config file:
`pg_hba.conf`, which will likely require `sudo`. For me, this file is located
at `/etc/postgresql/<version>/main/pg_hba.conf`. For the sake of this test
setup you should got to the bottom where you see several lines of the form:
```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
```
Change `peer` or `md5` in the `METHOD` section to be `trust`. This will allow
you to access the test databases without a password. *Note that you should
**not** do this when the database could be exposed to the outside or multiple
users may be using the same machine*. After changing the file, you will need to
reboot your computer. After this is done, you can try running the tests.

You should not be prompted to enter a password to run the tests. If so, revisit
the changes made to the `pg_hba.conf` file, and again make sure you rebooted
after making the changes. You can then test that the database works as expected
by entering

```bash		
psql -U postgres		
```		
At which point you should see a prompt like this:		
```		
psql (10.9 (Ubuntu 10.9-1.pgdg16.04+1), server 9.6.14)		
Type "help" for help.		
 postgres=# 		
 ```		
Enter `\q` to exit the prompt, and you should be all set to run the tests.
