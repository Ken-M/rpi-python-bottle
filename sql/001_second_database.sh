#!/bin/bash

echo "CREATE DATABASE IF NOT EXISTS \`integrated_measurement\` ;" | "$tempSqlFile"
echo "GRANT ALL ON \`integrated_measurement\`.* TO '"$MYSQL_USER"'@'%' ;" | "$tempSqlFile"
echo 'FLUSH PRIVILEGES ;' | "$tempSqlFile"

"$tempSqlFile" < /docker-entrypoint-initdb.d/instantaneous_create_table.sql_
"$tempSqlFile" < /docker-entrypoint-initdb.d/integrated_create_table.sql_