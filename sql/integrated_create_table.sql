
CREATE DATABASE IF NOT EXISTS `integrated_measurement` ;
GRANT ALL ON `integrated_measurement`.* TO '$MYSQL_USER'@'%' ;
FLUSH PRIVILEGES ;

USE integrated_measurement;

CREATE TABLE IF NOT EXISTS `integrated_value` (
  `id`           int(11) NOT NULL AUTO_INCREMENT,
  `server_id`    int(11) NOT NULL,
  `integrated_power`  int(11) NOT NULL,
  `power_delta`  int(11) NOT NULL,
  `power_charge`  int(11) NOT NULL,
  `created_at`   datetime NOT NULL PRIMARY KEY,
  `created_user` int(11) NOT NULL,
  `updated_at`   datetime NOT NULL,
  `updated_user` int(11) NOT NULL,
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

