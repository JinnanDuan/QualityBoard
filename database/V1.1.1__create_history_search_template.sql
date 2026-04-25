-- 新建历史页搜索模板表 history_search_template（按工号绑定，与 JWT sub 一致）
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `history_search_template` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `employee_id` varchar(20) NOT NULL COMMENT '工号，与 JWT sub、ums_email 一致',
  `name` varchar(100) NOT NULL COMMENT '模板名称',
  `query_json` text NOT NULL COMMENT '筛选条件 JSON（与 HistoryQuery 字段一致）',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hst_employee_name` (`employee_id`,`name`),
  KEY `idx_hst_employee_id` (`employee_id`),
  CONSTRAINT `fk_hst_employee` FOREIGN KEY (`employee_id`) REFERENCES `ums_email` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
