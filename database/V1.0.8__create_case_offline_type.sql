-- 新建用例下线类型表 case_offline_type
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `case_offline_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `offline_reason_type` varchar(500) NOT NULL COMMENT '用例下线原因分类',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_offline_reason_type` (`offline_reason_type`(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
