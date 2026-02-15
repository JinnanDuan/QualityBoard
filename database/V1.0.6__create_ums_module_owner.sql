-- 新建模块负责人表 ums_module_owner（依赖 ums_email 表）
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `ums_module_owner` (
  `module` varchar(40) NOT NULL COMMENT '测试用例主模块（测试代码中标记的第一个模块作为主模块，根据主模块来分配对应的开发责任人）',
  `owner` varchar(20) NOT NULL COMMENT '负责人工号',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `for_reference` varchar(255) DEFAULT NULL COMMENT '负责人姓名（辅助使用，没有其他地方用到这个字段）',
  PRIMARY KEY (`module`),
  KEY `owner` (`owner`),
  CONSTRAINT `ums_module_owner_ibfk_1` FOREIGN KEY (`owner`) REFERENCES `ums_email` (`employee_id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
