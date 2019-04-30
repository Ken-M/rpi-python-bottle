CREATE DATABASE IF NOT EXISTS `integrated_measurement` ;
GRANT ALL ON `integrated_measurement`.* TO 'bottle'@'%' ;
FLUSH PRIVILEGES ;
USE integrated_measurement;
CREATE TABLE IF NOT EXISTS `integrated_value` (  `server_id`    int(11) NOT NULL,  `integrated_power`  double(20,3) NOT NULL, `power_delta`  double(20,3) NOT NULL,  `power_type` int(11) NOT NULL, `power_charge`  double(20,3) NOT NULL,  `created_at`   datetime NOT NULL PRIMARY KEY,  `created_user` int(11) NOT NULL,  `updated_at`   datetime NOT NULL,  `updated_user` int(11) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8;

