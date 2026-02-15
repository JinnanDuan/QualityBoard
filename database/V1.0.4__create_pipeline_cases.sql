-- 新建流水线用例表 pipeline_cases
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `pipeline_cases` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `case_name` varchar(255) DEFAULT NULL COMMENT '用例名称',
  `case_level` varchar(255) DEFAULT NULL COMMENT '用例级别（如P0/P1/P2等）',
  `case_type` varchar(25) DEFAULT NULL COMMENT '用例类型',
  `test_type` varchar(25) DEFAULT NULL COMMENT '测试类型（如API/UI等）',
  `is_online` varchar(25) DEFAULT NULL COMMENT '是否在线运行（建议未来重构为tinyint）',
  `state` varchar(30) DEFAULT NULL COMMENT '用例当前状态',
  `state_detail` varchar(255) DEFAULT NULL COMMENT '状态详情/备注',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `platform` varchar(50) DEFAULT NULL COMMENT '平台名称',
  `change_history` varchar(500) DEFAULT NULL COMMENT '变更历史记录',
  `recover_batch` varchar(50) DEFAULT NULL COMMENT '恢复轮次',
  `offline_reason_detail` varchar(500) DEFAULT NULL COMMENT '下线原因详细说明',
  `pkg_type` varchar(255) DEFAULT NULL COMMENT '包类型',
  `offline_reason_type` varchar(500) DEFAULT NULL COMMENT '下线原因分类',
  `offline_case_owner` varchar(255) DEFAULT NULL COMMENT '下线用例责任人',
  PRIMARY KEY (`id`),
  KEY `idx_case_name` (`case_name`),
  KEY `idx_state` (`state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
