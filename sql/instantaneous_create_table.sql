USE instantaneous_measurement;

CREATE TABLE IF NOT EXISTS `instantaneous_value` (
  `id`           int(11) NOT NULL PRIMARY KEY AUTO_INCREMENT,
  `server_id`    int(11) NOT NULL,
  `power`  int(11) NOT NULL,
  `created_at`   datetime NOT NULL,
  `created_user` int(11) NOT NULL,
  `updated_at`   datetime NOT NULL,
  `updated_user` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

