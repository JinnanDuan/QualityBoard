-- 新建流水线失败原因表 pipeline_failure_reason
-- MySQL 5.7，字符集 utf8mb4，排序规则 utf8mb4_unicode_ci

CREATE TABLE `pipeline_failure_reason` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `case_name` varchar(255) DEFAULT NULL COMMENT '用例名称',
  `failed_batch` varchar(200) DEFAULT NULL COMMENT '失败轮次',
  `owner` varchar(100) DEFAULT NULL COMMENT '失败用例跟踪人',
  `reason` text COMMENT '详细失败原因',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `failed_type` varchar(100) DEFAULT NULL COMMENT '失败原因分类',
  `recover_batch` varchar(200) DEFAULT NULL COMMENT '恢复轮次',
  `platform` varchar(255) DEFAULT NULL COMMENT '用例平台',
  `analyzer` varchar(255) DEFAULT NULL COMMENT '失败用例的失败原因分析人',
  `dts_num` varchar(255) DEFAULT NULL COMMENT 'dts单号',
  PRIMARY KEY (`id`),
  KEY `idx_pfr_failedbatch_case` (`failed_batch`,`case_name`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
