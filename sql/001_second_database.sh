#!/bin/bash

echo "CREATE DATABASE IF NOT EXISTS \`integrated_measurement\` ;" >> "$tempSqlFile"
echo "GRANT ALL ON \`integrated_measurement\`.* TO '"$MYSQL_USER"'@'%' ;" >> "$tempSqlFile"
echo 'FLUSH PRIVILEGES ;' >> "$tempSqlFile"

cat /docker-entrypoint-initdb.d/instantaneous_create_table.sql_ >> "$tempSqlFile"
cat /docker-entrypoint-initdb.d/integrated_create_table.sql_ >> "$tempSqlFile"