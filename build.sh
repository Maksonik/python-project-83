#!/usr/bin/env bash

# Postgres позволяет подключиться к удаленной базе указав ссылку на нее после флага -d
make install && psql -a -d $DATABASE_URL -f database.sql