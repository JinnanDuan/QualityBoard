-- 新建系统审计日志表 sys_audit_log
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `sys_audit_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `operator` varchar(50) NOT NULL COMMENT '操作人工号',
  `action` varchar(100) NOT NULL COMMENT '操作类型',
  `target_type` varchar(50) DEFAULT NULL COMMENT '操作对象类型',
  `target_id` varchar(100) DEFAULT NULL COMMENT '操作对象ID',
  `detail` text COMMENT '操作详情（JSON）',
  `ip_address` varchar(50) DEFAULT NULL COMMENT '操作人IP',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_sal_operator` (`operator`),
  KEY `idx_sal_action` (`action`),
  KEY `idx_sal_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
