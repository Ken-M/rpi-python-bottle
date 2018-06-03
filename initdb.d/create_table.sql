USE measurement;

CREATE TABLE `instantaneous_value` (
  `id`           int(11) NOT NULL AUTO_INCREMENT,
  `server_id`    int(11) NOT NULL,
  `power`  int(11) NOT NULL,
  `created_at`   datetime NOT NULL,
  `created_user` int(11) NOT NULL,
  `updated_at`   datetime NOT NULL,
  `updated_user` int(11) NOT NULL,
  KEY `id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `integrated_value` (
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

INSERT INTO `instantaneous_value` 
  (`id`, `server_id`, `power`, `created_at`, `created_user`, `updated_at`, `updated_user`) 
  VALUES 
  (1, 1, 0, NOW(), 1, NOW(), 1);
  
  INSERT INTO `integrated_value` 
  (`id`, `server_id`, `integrated_power`, `power_delta`, `power_charge`, `created_at`, `created_user`, `updated_at`, `updated_user`) 
  VALUES 
  (1, 1, 0, NOW(), 1, NOW(), 1);