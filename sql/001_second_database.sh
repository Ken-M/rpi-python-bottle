#!/bin/sh

echo "CREATE DATABASE IF NOT EXISTS \`integrated_measurement\` ;" | "${mysql[@]}"
echo "GRANT ALL ON \`integrated_measurement\`.* TO '"$MYSQL_USER"'@'%' ;" | "${mysql[@]}"
echo 'FLUSH PRIVILEGES ;' | "${mysql[@]}"

"${mysql[@]}" < /docker-entrypoint-initdb.d/instantaneous_create_table.sql_
"${mysql[@]}" < /docker-entrypoint-initdb.d/integrated_create_table.sql_