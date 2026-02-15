-- 新建流水线概览表 pipeline_overview
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `pipeline_overview` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `batch` varchar(100) DEFAULT NULL COMMENT '轮次',
  `subtask` varchar(100) DEFAULT NULL COMMENT '组别（一个机器一个组，也是Jenkins上的任务名称）',
  `result` varchar(25) DEFAULT NULL COMMENT '本轮该组执行结果（全部通过：passed，未全部通过：failed）',
  `case_num` varchar(25) DEFAULT NULL COMMENT '本轮该组执行的所有用例数量',
  `batch_start` datetime DEFAULT NULL COMMENT '本轮该组开始执行时间',
  `batch_end` datetime DEFAULT NULL COMMENT '本轮该组执行结束时间',
  `reports_url` varchar(150) DEFAULT NULL COMMENT '测试报告URL',
  `log_url` varchar(150) DEFAULT NULL COMMENT '日志URL',
  `screenshot_url` varchar(150) DEFAULT NULL COMMENT '截图URL',
  `pipeline_url` varchar(150) DEFAULT NULL COMMENT 'Jenkins流水线URL',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `passed_num` int(11) DEFAULT NULL COMMENT '本轮该组所有执行通过的用例数量',
  `failed_num` int(11) DEFAULT NULL COMMENT '本轮该组所有未执行通过的用例数量',
  `platform` varchar(255) DEFAULT NULL COMMENT '平台名称',
  `code_branch` varchar(255) DEFAULT NULL COMMENT '本轮执行时使用的IDE代码分支',
  PRIMARY KEY (`id`),
  KEY `idx_batch_subtask` (`batch`, `subtask`),
  KEY `idx_subtask` (`subtask`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
