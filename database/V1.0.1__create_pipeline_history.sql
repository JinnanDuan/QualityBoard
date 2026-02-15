-- 新建流水线历史表 pipeline_history
-- 符合 MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `pipeline_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `start_time` varchar(50) DEFAULT NULL COMMENT '轮次（等同于batch）',
  `subtask` varchar(100) DEFAULT NULL COMMENT '组别（一个机器一个组，也是Jenkins上的任务名称）',
  `reports_url` varchar(255) DEFAULT NULL COMMENT '测试报告的URL',
  `log_url` varchar(250) NOT NULL COMMENT '日志URL',
  `screenshot_url` varchar(250) NOT NULL COMMENT '截图URL',
  `module` varchar(40) DEFAULT NULL COMMENT '测试用例代码中标记的模块名',
  `case_name` varchar(255) DEFAULT NULL COMMENT '用例名称',
  `case_result` varchar(50) DEFAULT NULL COMMENT '本轮执行结果',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `pipeline_url` varchar(200) DEFAULT NULL COMMENT 'Jenkins流水线URL',
  `case_level` varchar(100) NOT NULL DEFAULT '' COMMENT '用例级别',
  `main_module` varchar(100) NOT NULL DEFAULT '' COMMENT '测试用例主模块（测试代码中标记的第一个模块作为主模块，根据主模块来分配对应的开发责任人）',
  `owner_history` varchar(255) DEFAULT NULL COMMENT '用例责任人（开发）变更记录',
  `owner` varchar(255) DEFAULT NULL COMMENT '用例责任人（开发）',
  `platform` varchar(255) DEFAULT NULL COMMENT '平台名称',
  `code_branch` varchar(255) DEFAULT NULL COMMENT '本轮执行时使用的IDE代码分支',
  `analyzed` tinyint(1) DEFAULT '0' COMMENT '是否给失败用例分配了失败原因（是：1，否：0），给rolling管理员用的字段',
  PRIMARY KEY (`id`),
  KEY `idx_timentask` (`start_time`,`subtask`),
  KEY `idx_main_module` (`main_module`) USING BTREE,
  KEY `idx_start_time_case` (`start_time`,`case_name`) USING BTREE,
  KEY `idx_casename_platform_batch` (`case_name`,`platform`,`start_time`) USING BTREE,
  KEY `idx_created_at_desc` (`created_at`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
