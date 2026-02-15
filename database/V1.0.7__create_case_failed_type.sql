-- 新建用例失败类型表 case_failed_type
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `case_failed_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `failed_reason_type` varchar(255) NOT NULL COMMENT '失败原因分类',
  `owner` varchar(255) DEFAULT NULL COMMENT '该失败类型的默认跟踪人',
  `creator` varchar(255) NOT NULL COMMENT '创建者',
  `updater` varchar(255) NOT NULL COMMENT '更新者',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_failed_reason_type` (`failed_reason_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
