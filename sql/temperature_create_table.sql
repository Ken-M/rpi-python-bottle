CREATE DATABASE IF NOT EXISTS `temperature` ;
GRANT ALL ON `temperature`.* TO 'bottle'@'%' ;
FLUSH PRIVILEGES ;
USE temperature;
CREATE TABLE IF NOT EXISTS `temperature_value` (  `server_id`    int(11) NOT NULL,  `temperature`  double(20,3) NOT NULL,  `created_at`   datetime NOT NULL PRIMARY KEY,  `created_user` int(11) NOT NULL,  `updated_at`   datetime NOT NULL,  `updated_user` int(11) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8;

